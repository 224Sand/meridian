"""Load the simulated estate and the retrieval corpus into Postgres.

Idempotent: re-running replaces content rather than duplicating it, because a
seed loader that can only be run once is a seed loader nobody dares run.

Embeddings are written with their model name attached (ADR-0005). Loading under
a second embedding model adds rows rather than overwriting the first, and the
unique constraint on (chunk_id, model) is what makes that safe.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from meridian_agent.retrieval.corpus import Chunk, Document, chunk_corpus, load_corpus
from meridian_agent.retrieval.embedding import Embedder, HashingEmbedder
from meridian_agent.seed import estate


@dataclass(frozen=True, slots=True)
class LoadReport:
    services: int
    dependencies: int
    documents: int
    chunks: int
    embeddings: int
    embedding_model: str


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def load_estate(conn: psycopg.Connection) -> tuple[int, int]:
    with conn.cursor() as cur:
        for service in estate.services():
            cur.execute(
                """
                INSERT INTO service (id, name, tier, owner_team, runtime, region)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name, tier = EXCLUDED.tier,
                    owner_team = EXCLUDED.owner_team, runtime = EXCLUDED.runtime,
                    region = EXCLUDED.region
                """,
                (
                    service.id,
                    service.name,
                    int(service.tier),
                    service.owner_team,
                    service.runtime,
                    service.region,
                ),
            )
        for dependency in estate.dependencies():
            cur.execute(
                """
                INSERT INTO service_dependency (upstream_id, downstream_id, kind)
                VALUES (%s, %s, %s)
                ON CONFLICT (upstream_id, downstream_id) DO UPDATE SET kind = EXCLUDED.kind
                """,
                (dependency.upstream_id, dependency.downstream_id, dependency.kind),
            )
    return len(estate.services()), len(estate.dependencies())


def load_corpus_into(
    conn: psycopg.Connection, documents: list[Document], chunks: list[Chunk]
) -> tuple[int, int]:
    with conn.cursor() as cur:
        for document in documents:
            cur.execute(
                """
                INSERT INTO document (id, kind, title, source_uri)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    kind = EXCLUDED.kind, title = EXCLUDED.title,
                    source_uri = EXCLUDED.source_uri
                """,
                (document.id, document.kind, document.title, document.source_uri),
            )
        # Chunks are UPSERTED, and only genuine orphans are then deleted.
        #
        # The first version deleted every chunk for a document and reinserted
        # them. Simpler, and it destroys data: chunk_embedding cascades on chunk
        # deletion, so reloading under a second embedding model wiped the first
        # model's vectors and left 87 rows where ADR-0005 requires 174.
        #
        # CI caught it against the pgvector container. It could not be caught by
        # a local run, because the destructive-test guard skips these tests
        # against a managed host - so the container is the only place this path
        # is ever exercised.
        for chunk in chunks:
            cur.execute(
                """
                INSERT INTO chunk (id, document_id, ordinal, heading, body, token_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    ordinal = EXCLUDED.ordinal,
                    heading = EXCLUDED.heading,
                    body = EXCLUDED.body,
                    token_count = EXCLUDED.token_count
                """,
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.ordinal,
                    chunk.heading,
                    chunk.body,
                    chunk.token_count,
                ),
            )

        # Remove chunks a document no longer produces. Boundaries move when the
        # chunker or a document changes, and a stale ordinal that survives is a
        # passage retrieval can still return and cite.
        by_document: dict[str, list[str]] = {}
        for chunk in chunks:
            by_document.setdefault(chunk.document_id, []).append(chunk.id)
        for document in documents:
            cur.execute(
                "DELETE FROM chunk WHERE document_id = %s AND NOT (id = ANY(%s))",
                (document.id, by_document.get(document.id, [])),
            )
    return len(documents), len(chunks)


def load_embeddings(conn: psycopg.Connection, chunks: list[Chunk], embedder: Embedder) -> int:
    vectors = embedder.embed([chunk.body for chunk in chunks])
    with conn.cursor() as cur:
        for chunk, vector in zip(chunks, vectors, strict=True):
            cur.execute(
                """
                INSERT INTO chunk_embedding (chunk_id, model, dim, vec)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chunk_id, model) DO UPDATE SET
                    vec = EXCLUDED.vec, dim = EXCLUDED.dim
                """,
                (chunk.id, embedder.model, embedder.dim, _vector_literal(vector)),
            )
    return len(chunks)


def seed(conn: psycopg.Connection, embedder: Embedder | None = None) -> LoadReport:
    embedder = embedder or HashingEmbedder()
    documents = load_corpus()
    chunks = chunk_corpus(documents)

    services, dependencies = load_estate(conn)
    document_count, chunk_count = load_corpus_into(conn, documents, chunks)
    embeddings = load_embeddings(conn, chunks, embedder)
    conn.commit()

    return LoadReport(
        services=services,
        dependencies=dependencies,
        documents=document_count,
        chunks=chunk_count,
        embeddings=embeddings,
        embedding_model=embedder.model,
    )
