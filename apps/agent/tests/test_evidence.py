"""Hybrid retrieval and the evidence gate.

The class of bug these tests exist to prevent is specific: a refusal check
reading a signal that does not distinguish the two classes. Such a check passes
review, produces plausible logs, and cannot refuse anything however carefully
its threshold is chosen. It is invisible until someone measures it.

So the suite measures it, on every run.
"""

from __future__ import annotations

import pytest

from meridian_agent.retrieval.corpus import chunk_corpus, load_corpus
from meridian_agent.retrieval.embedding import HashingEmbedder
from meridian_agent.retrieval.evidence import (
    EvidenceVerdict,
    assess,
    combined_score,
    term_coverage,
)
from meridian_agent.retrieval.hybrid import HybridRetriever

ANSWERABLE = [
    "db.pool.wait_ms is climbing and available connections hit zero",
    "cache hit ratio collapsed with mass eviction",
    "tls handshake failures, certificate expired",
    "consumer group lag growing while throughput falls",
    "heap memory climbing and gc pause time increasing",
    "queries per request jumped sharply after a deploy",
    "search shard imbalance causing p99 latency",
    "should I restart the cache during a stampede",
    "what severity is a tier 0 outage",
    "when is rollback the first response",
]

#: Drawn from corpus/GAPS.md. Each is genuinely unsupported by the corpus.
UNANSWERABLE = [
    "what is the checkout availability SLO",
    "how long are heap dumps retained",
    "what is the disaster recovery failover procedure",
    "the disk is full on the host",
    "what is the pool ceiling on sessions-cache",
    "who is on call for edge-gateway overnight",
    "how do we handle a DNS resolution failure",
    "what is the data retention obligation",
    "what are the kubernetes scheduler settings",
    "what is the rate limit for external API consumers",
]


@pytest.fixture(scope="module")
def retriever() -> HybridRetriever:
    r = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
    r.build_vectors()
    return r


@pytest.fixture(scope="module")
def lexical_only() -> HybridRetriever:
    return HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=None)


class TestTheFusedScoreIsUnusableForRefusal:
    """Locks in WHY the gate does not read the fused score.

    Without this test, a later change that gates refusal on `top_score` would
    look entirely reasonable and would silently disable refusal.
    """

    def test_normalised_fused_score_does_not_separate_the_classes(
        self, retriever: HybridRetriever
    ) -> None:
        answerable = [retriever.search(q).top_score for q in ANSWERABLE]
        unanswerable = [retriever.search(q).top_score for q in UNANSWERABLE]
        assert min(answerable) <= max(unanswerable), (
            "the fused score now separates the classes; if that is genuinely "
            "true, re-derive the gate deliberately rather than assuming it"
        )

    def test_combined_score_uses_unnormalised_inputs(self, retriever: HybridRetriever) -> None:
        result = retriever.search(ANSWERABLE[0])
        assert result.top_score == pytest.approx(1.0), "top hit normalises to 1.0 by construction"
        assert combined_score(result) != pytest.approx(1.0)


class TestNoSingleSignalSeparates:
    """The measurement the design rests on. If it changes, the design should."""

    def test_dense_alone_does_not_separate(self, retriever: HybridRetriever) -> None:
        a = min(retriever.search(q).top_dense for q in ANSWERABLE)
        u = max(retriever.search(q).top_dense for q in UNANSWERABLE)
        assert a <= u + 0.05, f"dense margin unexpectedly wide: {a:.3f} vs {u:.3f}"

    def test_coverage_alone_does_not_separate(self, retriever: HybridRetriever) -> None:
        """'data retention obligation' scores 1.00 against a sentence saying
        retention is not covered."""
        worst = max(term_coverage(q, retriever.search(q)) for q in UNANSWERABLE)
        assert worst >= 0.9, (
            f"expected an unanswerable question at near-full coverage, got {worst:.2f}"
        )


class TestTheProductFailure:
    """Answering something the corpus cannot support is the failure this
    product exists to prevent. It is asserted first and separately."""

    @pytest.mark.parametrize("question", UNANSWERABLE)
    def test_no_unanswerable_question_is_ever_marked_sufficient(
        self, retriever: HybridRetriever, question: str
    ) -> None:
        assessment = assess(question, retriever.search(question))
        assert assessment.verdict is not EvidenceVerdict.SUFFICIENT, (
            f"{question!r} would have been answered: {assessment.rationale}"
        )
        assert not assessment.permits_answering

    @pytest.mark.parametrize("question", ANSWERABLE)
    def test_no_answerable_question_is_flatly_refused(
        self, retriever: HybridRetriever, question: str
    ) -> None:
        """Over-refusal is the acceptable direction, but the deterministic layer
        should not refuse anything the corpus genuinely covers."""
        assessment = assess(question, retriever.search(question))
        assert assessment.verdict is not EvidenceVerdict.INSUFFICIENT, assessment.rationale


class TestBands:
    def test_most_decisions_cost_no_model_call(self, retriever: HybridRetriever) -> None:
        """Principle 3: if a typed rule can decide it, no token is spent."""
        decided = sum(
            assess(q, retriever.search(q)).verdict is not EvidenceVerdict.AMBIGUOUS
            for q in ANSWERABLE + UNANSWERABLE
        )
        assert decided >= 14, f"only {decided}/20 resolved deterministically"

    def test_ambiguous_does_not_permit_answering(self, retriever: HybridRetriever) -> None:
        """AMBIGUOUS is not a soft yes. Reading it as one collapses the
        three-state assessment back into the two-state one it replaced."""
        ambiguous = [
            a
            for q in ANSWERABLE + UNANSWERABLE
            if (a := assess(q, retriever.search(q))).verdict is EvidenceVerdict.AMBIGUOUS
        ]
        assert ambiguous, "expected the corpus to produce genuinely ambiguous cases"
        assert all(not a.permits_answering for a in ambiguous)
        assert all(a.requires_adjudication for a in ambiguous)

    def test_a_question_with_no_shared_vocabulary_is_insufficient(
        self, retriever: HybridRetriever
    ) -> None:
        question = "what is the airspeed velocity of an unladen swallow"
        assert assess(question, retriever.search(question)).verdict is EvidenceVerdict.INSUFFICIENT

    def test_empty_retrieval_is_insufficient_not_ambiguous(
        self, retriever: HybridRetriever
    ) -> None:
        from meridian_agent.retrieval.hybrid import RetrievalResult

        empty = RetrievalResult(query="q", hits=(), degraded=False)
        assert assess("q", empty).verdict is EvidenceVerdict.INSUFFICIENT


class TestDegradation:
    def test_lexical_only_retrieval_is_labelled_degraded(
        self, lexical_only: HybridRetriever
    ) -> None:
        result = lexical_only.search(ANSWERABLE[0])
        assert result.degraded
        assert result.degraded_reason
        assert result.hits, "degraded must still return results, just labelled"

    def test_degraded_retrieval_is_ambiguous_not_insufficient(
        self, lexical_only: HybridRetriever
    ) -> None:
        """Degraded evidence is unresolved, not weak. Treating a missing dense
        score as a low dense score would refuse everything during an outage."""
        assessment = assess(ANSWERABLE[0], lexical_only.search(ANSWERABLE[0]))
        assert assessment.verdict is EvidenceVerdict.AMBIGUOUS
        assert "degraded" in assessment.rationale

    def test_embedder_failure_degrades_rather_than_raising(self) -> None:
        class BrokenEmbedder:
            model = "broken-v1"
            dim = 768
            similarity_threshold = 0.6

            def embed(self, texts: list[str]) -> list[list[float]]:
                raise RuntimeError("provider timeout")

        r = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
        r.build_vectors()
        r.embedder = BrokenEmbedder()  # type: ignore[assignment]
        result = r.search(ANSWERABLE[0])
        assert result.degraded
        assert "provider timeout" in result.degraded_reason
        assert result.hits

    def test_degraded_never_mixes_embedding_spaces(self) -> None:
        """ADR-0005: the fallback is lexical-only, never a different space."""
        r = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=None)
        result = r.search(ANSWERABLE[0])
        assert all(hit.dense_score == 0.0 for hit in result.hits)


class TestRetrievalQuality:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("db.pool.wait_ms climbing", "rb-database-connection-pool"),
            ("cache hit ratio collapsed", "rb-cache-stampede"),
            ("certificate expired handshake failures", "rb-tls-certificate"),
            ("consumer lag growing", "rb-stream-consumer-lag"),
        ],
    )
    def test_hybrid_reaches_the_right_runbook(
        self, retriever: HybridRetriever, query: str, expected: str
    ) -> None:
        top = retriever.search(query, limit=3)
        assert any(hit.document_id == expected for hit in top.hits)

    def test_results_are_deterministic(self, retriever: HybridRetriever) -> None:
        first = [h.chunk.id for h in retriever.search(ANSWERABLE[0]).hits]
        second = [h.chunk.id for h in retriever.search(ANSWERABLE[0]).hits]
        assert first == second
