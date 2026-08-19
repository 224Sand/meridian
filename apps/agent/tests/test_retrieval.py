"""Corpus loading, chunking, lexical retrieval and the offline embedder.

All offline. The retrieval layer is the part of the system that must work with
no network and no key, so a test suite that needed either would be testing the
wrong thing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from meridian_agent.retrieval.bm25 import BM25Index
from meridian_agent.retrieval.corpus import (
    CorpusError,
    chunk_corpus,
    chunk_document,
    load_corpus,
    load_document,
    parse_front_matter,
)
from meridian_agent.retrieval.embedding import DIM, Embedder, HashingEmbedder, cosine
from meridian_agent.retrieval.tokenize import tokenize
from meridian_agent.seed.faults import PATTERNS


@pytest.fixture(scope="module")
def documents():
    return load_corpus()


@pytest.fixture(scope="module")
def chunks(documents):
    return chunk_corpus(documents)


@pytest.fixture(scope="module")
def index(chunks):
    return BM25Index.build({c.id: c.body for c in chunks})


class TestCorpusIntegrity:
    def test_corpus_loads(self, documents) -> None:
        assert len(documents) >= 15

    def test_every_fault_pattern_has_its_runbook(self, documents) -> None:
        """A pattern pointing at a runbook that does not exist is an incident
        the agent can never resolve."""
        ids = {d.id for d in documents}
        for pattern in PATTERNS:
            assert pattern.runbook_id in ids, (
                f"{pattern.id} references missing {pattern.runbook_id}"
            )

    def test_document_ids_are_unique(self, documents) -> None:
        assert len({d.id for d in documents}) == len(documents)

    def test_gaps_file_is_not_indexed(self, documents) -> None:
        """GAPS.md describes what the corpus lacks. Indexing it would let the
        system answer questions about its blind spots from a list of them."""
        assert all("GAPS" not in d.source_uri for d in documents)

    def test_source_uri_points_at_a_real_file(self, documents) -> None:
        root = Path(__file__).resolve().parents[1]
        for document in documents:
            assert (root / document.source_uri).exists(), document.source_uri


class TestFrontMatter:
    def test_parses_scalar_fields(self) -> None:
        fields, body = parse_front_matter(
            '---\nid: x\nkind: policy\ntitle: "A title"\n---\nBody here.', source="t.md"
        )
        assert fields == {"id": "x", "kind": "policy", "title": "A title"}
        assert body == "Body here."

    def test_missing_front_matter_raises(self) -> None:
        with pytest.raises(CorpusError, match="missing front matter"):
            parse_front_matter("Just a body.", source="t.md")

    def test_malformed_line_raises_rather_than_being_dropped(self) -> None:
        with pytest.raises(CorpusError, match="not `key: value`"):
            parse_front_matter("---\nid x\n---\nBody", source="t.md")

    def test_unknown_kind_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "d.md"
        path.write_text("---\nid: d\nkind: memo\ntitle: T\n---\nBody", encoding="utf-8")
        with pytest.raises(CorpusError, match="is not one of"):
            load_document(path)

    def test_missing_id_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "d.md"
        path.write_text("---\nkind: policy\ntitle: T\n---\nBody", encoding="utf-8")
        with pytest.raises(CorpusError, match="missing `id`"):
            load_document(path)

    def test_empty_body_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "d.md"
        path.write_text("---\nid: d\nkind: policy\ntitle: T\n---\n\n", encoding="utf-8")
        with pytest.raises(CorpusError, match="no body"):
            load_document(path)


class TestChunking:
    def test_chunks_carry_their_document_and_ordinal(self, documents) -> None:
        document = documents[0]
        produced = chunk_document(document)
        assert [c.ordinal for c in produced] == list(range(len(produced)))
        assert all(c.document_id == document.id for c in produced)

    def test_chunk_ids_are_unique_across_the_corpus(self, chunks) -> None:
        assert len({c.id for c in chunks}) == len(chunks)

    def test_no_chunk_is_empty(self, chunks) -> None:
        assert all(c.body.strip() for c in chunks)

    def test_token_counts_are_positive(self, chunks) -> None:
        assert all(c.token_count > 0 for c in chunks)

    def test_short_sections_merge_backwards(self) -> None:
        """A retrieved chunk must carry evidence, not just a heading."""
        from meridian_agent.retrieval.corpus import Document

        document = Document(
            id="d",
            kind="policy",
            title="T",
            source_uri="corpus/x/d.md",
            body="## One\n\n" + ("body " * 60) + "\n\n## Two\n\nshort.",
        )
        produced = chunk_document(document)
        assert len(produced) == 1, "a two-word section should not stand alone"
        assert "short." in produced[0].body


class TestTokenizer:
    def test_identifiers_survive_whole_and_split(self) -> None:
        tokens = tokenize("db.pool.wait_ms is climbing")
        assert "db.pool.wait_ms" in tokens, "the identifier an operator would search for"
        assert "pool" in tokens and "wait" in tokens, "and its parts, for looser queries"

    def test_negations_are_not_stopped(self) -> None:
        """'do not restart the cache' must not tokenise to 'restart the cache'."""
        tokens = tokenize("do not restart the cache")
        assert "not" in tokens

    def test_single_characters_are_dropped(self) -> None:
        assert tokenize("a b see") == ["see"]

    def test_is_case_insensitive(self) -> None:
        assert tokenize("Checkout API") == tokenize("checkout api")


class TestBM25:
    def test_index_covers_every_chunk(self, index, chunks) -> None:
        assert len(index) == len(chunks)

    @pytest.mark.parametrize(
        ("query", "expected_document"),
        [
            ("db.pool.wait_ms climbing and available at zero", "rb-database-connection-pool"),
            ("cache hit ratio collapsed with mass eviction", "rb-cache-stampede"),
            ("tls handshake failures certificate expired", "rb-tls-certificate"),
            ("consumer group lag growing throughput falling", "rb-stream-consumer-lag"),
            ("heap growing gc pause time increasing", "rb-memory-pressure"),
            ("queries per request jumped after deploy", "rb-query-amplification"),
            ("shard imbalance p99 search latency", "rb-search-shard-imbalance"),
            ("timeout cascade thread pool queue depth", "rb-timeout-and-retry"),
        ],
    )
    def test_each_fault_reaches_its_runbook(self, index, query, expected_document) -> None:
        top = index.search(query, 3)
        assert any(doc_id.startswith(expected_document) for doc_id, _ in top), (
            f"{expected_document} not in top 3 for {query!r}: {[d for d, _ in top]}"
        )

    def test_scores_separate_answerable_from_unanswerable(self, index) -> None:
        """The property the refusal gate depends on.

        A ranking signal that reads the same for both classes cannot refuse
        anything, however carefully the threshold is chosen.
        """
        answerable = index.search("db.pool.wait_ms climbing and available at zero", 1)[0][1]
        unanswerable = index.search("what is the checkout availability SLO", 1)
        unanswerable_score = unanswerable[0][1] if unanswerable else 0.0
        assert answerable > unanswerable_score * 2, (
            f"answerable {answerable:.2f} vs unanswerable {unanswerable_score:.2f} "
            "- too close to gate refusal on"
        )

    def test_empty_query_returns_nothing(self, index) -> None:
        assert index.search("") == []

    def test_ties_break_deterministically(self, index) -> None:
        assert index.search("cache", 5) == index.search("cache", 5)

    def test_empty_index_is_safe(self) -> None:
        assert BM25Index.build({}).search("anything") == []


class TestHashingEmbedder:
    def test_satisfies_the_embedder_protocol(self) -> None:
        assert isinstance(HashingEmbedder(), Embedder)

    def test_produces_the_contracted_dimension(self) -> None:
        assert len(HashingEmbedder().embed(["hello world"])[0]) == DIM

    def test_vectors_are_unit_length(self) -> None:
        vector = HashingEmbedder().embed(["connection pool exhaustion"])[0]
        assert abs(sum(v * v for v in vector) - 1.0) < 1e-9

    def test_is_deterministic_within_a_process(self) -> None:
        embedder = HashingEmbedder()
        assert embedder.embed(["same text"]) == embedder.embed(["same text"])

    def test_is_deterministic_across_processes(self) -> None:
        """Built-in hash() is salted per process; a store written by one worker
        and queried by another would return nonsense."""
        script = (
            "from meridian_agent.retrieval.embedding import HashingEmbedder;"
            "print(round(sum(HashingEmbedder().embed(['pool exhaustion'])[0][:32]), 9))"
        )
        results = {
            subprocess.run(  # noqa: S603
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                check=True,
                env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            ).stdout.strip()
            for seed in ("0", "1", "9999")
        }
        assert len(results) == 1, f"vectors varied with PYTHONHASHSEED: {results}"

    def test_related_text_scores_above_unrelated(self) -> None:
        embedder = HashingEmbedder()
        a, b, c = embedder.embed(
            [
                "connection pool exhaustion on the database",
                "the database connection pool is exhausted",
                "search shard imbalance in the catalog index",
            ]
        )
        assert cosine(a, b) > cosine(a, c)

    def test_morphological_variants_are_close(self) -> None:
        """Character n-grams stand in for a stemmer."""
        embedder = HashingEmbedder()
        restart, restarts, unrelated = embedder.embed(["restart", "restarts", "certificate"])
        assert cosine(restart, restarts) > cosine(restart, unrelated)

    def test_empty_text_yields_a_zero_vector_not_a_crash(self) -> None:
        assert HashingEmbedder().embed([""])[0] == [0.0] * DIM

    def test_cosine_rejects_a_dimension_mismatch(self) -> None:
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine([1.0, 0.0], [1.0, 0.0, 0.0])
