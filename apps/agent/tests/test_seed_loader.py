"""Loading the estate and corpus into Postgres.

Integration-marked: runs in CI against the pgvector service container, skipped
against any managed host by the destructive-test guard.

The property worth testing is idempotence. A seed loader that can only be run
once is a seed loader nobody dares run, so it gets run once and then diverges
from the corpus forever.
"""

from __future__ import annotations

import os

import pytest

from meridian_agent.db.engine import apply_migrations, connect
from meridian_agent.db.seed_loader import seed
from meridian_agent.retrieval.embedding import HashingEmbedder
from tests.test_schema_integration import _is_disposable

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set")
    if not _is_disposable(url) and os.environ.get("MERIDIAN_ALLOW_DESTRUCTIVE_TESTS") != "1":
        pytest.skip("refusing to seed a non-disposable host")
    with connect() as c:
        with c.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        c.commit()
        apply_migrations(c)
        c.commit()
        yield c


def count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed table names
        return int(cur.fetchone()[0])


class TestLoad:
    def test_loads_the_estate_and_corpus(self, conn) -> None:
        report = seed(conn)
        assert report.services == count(conn, "service") == 19
        assert report.dependencies == count(conn, "service_dependency") == 27
        assert report.documents == count(conn, "document") == 19
        assert report.chunks == count(conn, "chunk") > 50
        assert report.embeddings == count(conn, "chunk_embedding")

    def test_is_idempotent(self, conn) -> None:
        first = seed(conn)
        second = seed(conn)
        assert (first.services, first.chunks) == (second.services, second.chunks)
        assert count(conn, "chunk") == second.chunks
        assert count(conn, "chunk_embedding") == second.embeddings

    def test_every_chunk_has_an_embedding_under_the_active_model(self, conn) -> None:
        report = seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM chunk c LEFT JOIN chunk_embedding e "
                "ON e.chunk_id = c.id AND e.model = %s WHERE e.chunk_id IS NULL",
                (report.embedding_model,),
            )
            assert int(cur.fetchone()[0]) == 0

    def test_embeddings_carry_the_declared_dimension(self, conn) -> None:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT dim FROM chunk_embedding")
            assert [r[0] for r in cur.fetchall()] == [768]

    def test_a_second_embedding_model_adds_rows_rather_than_replacing(self, conn) -> None:
        """ADR-0005: two models coexist; neither overwrites the other."""

        class SecondEmbedder:
            model = "second-v1"
            dim = 768
            similarity_threshold = 0.6

            def embed(self, texts: list[str]) -> list[list[float]]:
                return HashingEmbedder().embed(texts)

        first = seed(conn)
        seed(conn, embedder=SecondEmbedder())
        assert count(conn, "chunk_embedding") == first.chunks * 2

        with conn.cursor() as cur:
            cur.execute("SELECT model, count(*) FROM chunk_embedding GROUP BY model ORDER BY model")
            assert dict(cur.fetchall()) == {"hashing-v1": first.chunks, "second-v1": first.chunks}

    def test_reloading_replaces_stale_chunks(self, conn) -> None:
        """Chunk boundaries move when the chunker or a document changes, so a
        reload must not leave orphaned ordinals behind."""
        seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chunk (id, document_id, ordinal, body, token_count) "
                "SELECT 'stale#99', id, 99, 'stale body', 2 FROM document LIMIT 1"
            )
        conn.commit()
        assert count(conn, "chunk") > seed(conn).chunks - 1

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunk WHERE id = 'stale#99'")
            assert int(cur.fetchone()[0]) == 0

    def test_dependencies_reference_loaded_services(self, conn) -> None:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM service_dependency d "
                "LEFT JOIN service s ON s.id = d.downstream_id WHERE s.id IS NULL"
            )
            assert int(cur.fetchone()[0]) == 0
