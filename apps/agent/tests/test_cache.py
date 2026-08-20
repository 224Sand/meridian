"""Semantic cache behaviour, and the measurement its threshold rests on.

The threshold test is not decoration. A cache threshold chosen by feel is the
kind of number that looks reasonable, passes review, and silently returns the
wrong answer to a fraction of requests forever.
"""

from __future__ import annotations

import pytest

from meridian_agent.retrieval.embedding import DIM, HashingEmbedder, cosine
from meridian_agent.router.cache import (
    InMemoryCacheStore,
    SemanticCache,
    normalise,
    prompt_hash,
)
from meridian_agent.router.providers import Message

PARAPHRASE_PAIRS = [
    (
        "the connection pool is exhausted on orders-db",
        "orders-db connection pool has been exhausted",
    ),
    ("cache hit ratio collapsed after a deploy", "the cache hit ratio fell after we deployed"),
    ("why did the certificate expire", "the certificate has expired, why"),
    ("consumer lag is growing on events-bus", "events-bus consumer lag keeps growing"),
    ("heap memory keeps climbing on fraud-scoring", "fraud-scoring heap memory is climbing"),
]

DISTINCT_PAIRS = [
    ("the connection pool is exhausted on orders-db", "the certificate expired at the edge"),
    ("cache hit ratio collapsed after a deploy", "consumer lag is growing on events-bus"),
    ("why did the certificate expire", "queries per request jumped after deploy"),
    ("heap memory keeps climbing", "search shard imbalance on catalog-search"),
    ("what is the checkout SLO", "the connection pool is exhausted"),
]


def cache(**kwargs) -> SemanticCache:
    return SemanticCache(embedder=HashingEmbedder(), store=InMemoryCacheStore(), **kwargs)


def ask(text: str) -> list[Message]:
    return [Message("user", text)]


class TestThreshold:
    """ADR-0008. These tests re-derive the threshold rather than trusting it."""

    @pytest.mark.parametrize(("a", "b"), PARAPHRASE_PAIRS)
    def test_paraphrases_sit_above_the_threshold(self, a: str, b: str) -> None:
        embedder = HashingEmbedder()
        assert cosine(*embedder.embed([a, b])) >= embedder.similarity_threshold

    @pytest.mark.parametrize(("a", "b"), DISTINCT_PAIRS)
    def test_distinct_questions_sit_below_the_threshold(self, a: str, b: str) -> None:
        embedder = HashingEmbedder()
        assert cosine(*embedder.embed([a, b])) < embedder.similarity_threshold

    def test_the_separation_has_real_margin(self) -> None:
        """A threshold wedged between two touching distributions is not a
        decision boundary, it is a coin flip with extra steps."""
        embedder = HashingEmbedder()
        lowest_paraphrase = min(cosine(*embedder.embed([a, b])) for a, b in PARAPHRASE_PAIRS)
        highest_distinct = max(cosine(*embedder.embed([a, b])) for a, b in DISTINCT_PAIRS)
        assert lowest_paraphrase - highest_distinct > 0.30, (
            f"margin collapsed: paraphrase floor {lowest_paraphrase:.3f}, "
            f"distinct ceiling {highest_distinct:.3f}"
        )

    def test_threshold_is_biased_toward_missing_not_toward_hitting(self) -> None:
        embedder = HashingEmbedder()
        highest_distinct = max(cosine(*embedder.embed([a, b])) for a, b in DISTINCT_PAIRS)
        assert embedder.similarity_threshold > highest_distinct * 2

    def test_there_is_no_module_level_threshold_constant(self) -> None:
        """ADR-0008: a shared constant is wrong for any embedder but one."""
        import meridian_agent.router.cache as cache_module

        assert not hasattr(cache_module, "SIMILARITY_THRESHOLD")


class TestNormalisation:
    def test_case_and_whitespace_are_folded(self) -> None:
        assert normalise("  The  Pool   is Exhausted ") == "the pool is exhausted"

    def test_identifiers_keep_their_dots(self) -> None:
        assert "db.pool.wait_ms" in normalise("Check DB.POOL.WAIT_MS")

    def test_punctuation_is_preserved(self) -> None:
        """'restart?' and 'restart!' are different intents in a runbook."""
        assert normalise("restart?") != normalise("restart!")


class TestKeying:
    def test_temperature_is_part_of_the_key(self) -> None:
        """A deterministic cached answer must not serve a request that asked
        for variation."""
        assert prompt_hash(ask("q"), "fast", 0.0) != prompt_hash(ask("q"), "fast", 0.9)

    def test_tier_is_part_of_the_key(self) -> None:
        assert prompt_hash(ask("q"), "fast", 0.0) != prompt_hash(ask("q"), "large", 0.0)

    def test_whitespace_variants_share_a_key(self) -> None:
        assert prompt_hash(ask("a  b"), "fast", 0.0) == prompt_hash(ask("a b"), "fast", 0.0)


class TestLookup:
    def test_cold_cache_misses(self) -> None:
        assert cache().lookup(ask("anything"), tier="fast", temperature=0.0) is None

    def test_exact_repeat_hits_the_exact_tier(self) -> None:
        c = cache()
        c.store_response(
            ask("why is the pool exhausted"),
            tier="fast",
            temperature=0.0,
            response="hold time rose",
            tokens_in=10,
            tokens_out=4,
        )
        hit = c.lookup(ask("why is the pool exhausted"), tier="fast", temperature=0.0)
        assert hit is not None
        assert hit.tier == "exact"
        assert hit.response == "hold time rose"

    def test_paraphrase_hits_the_semantic_tier(self) -> None:
        c = cache()
        c.store_response(
            ask("the connection pool is exhausted on orders-db"),
            tier="fast",
            temperature=0.0,
            response="hold time rose",
            tokens_in=10,
            tokens_out=4,
        )
        hit = c.lookup(
            ask("orders-db connection pool has been exhausted"), tier="fast", temperature=0.0
        )
        assert hit is not None
        assert hit.tier == "semantic"
        assert hit.similarity >= HashingEmbedder().similarity_threshold

    def test_an_unrelated_question_does_not_hit(self) -> None:
        c = cache()
        c.store_response(
            ask("the connection pool is exhausted on orders-db"),
            tier="fast",
            temperature=0.0,
            response="hold time rose",
            tokens_in=10,
            tokens_out=4,
        )
        assert c.lookup(ask("what is the checkout SLO"), tier="fast", temperature=0.0) is None

    def test_a_different_tier_does_not_hit(self) -> None:
        c = cache()
        c.store_response(
            ask("q"), tier="fast", temperature=0.0, response="r", tokens_in=1, tokens_out=1
        )
        assert c.lookup(ask("q"), tier="large", temperature=0.0) is None


class TestEmbeddingModelIsolation:
    """ADR-0005 at the cache layer."""

    def test_an_entry_written_under_another_model_is_never_a_candidate(self) -> None:
        class OtherEmbedder:
            model = "other-v1"
            dim = DIM
            similarity_threshold = 0.60

            def embed(self, texts: list[str]) -> list[list[float]]:
                return HashingEmbedder().embed(texts)

        store = InMemoryCacheStore()
        written = SemanticCache(embedder=HashingEmbedder(), store=store)
        written.store_response(
            ask("the connection pool is exhausted"),
            tier="fast",
            temperature=0.0,
            response="written under hashing-v1",
            tokens_in=5,
            tokens_out=5,
        )

        # Same store, same text, identical vectors - and still a miss, because
        # the model differs. A cosine across spaces is a number, not a meaning.
        read = SemanticCache(embedder=OtherEmbedder(), store=store)
        assert (
            read.lookup(ask("the connection pool is exhausted"), tier="fast", temperature=0.0)
            is None
        )
        assert read.stats.misses == 1


class TestStats:
    def test_hit_rate_and_tokens_avoided_are_tracked(self) -> None:
        c = cache()
        c.store_response(
            ask("q"), tier="fast", temperature=0.0, response="r", tokens_in=30, tokens_out=12
        )
        c.lookup(ask("q"), tier="fast", temperature=0.0)
        c.lookup(ask("something else entirely"), tier="fast", temperature=0.0)
        assert c.stats.exact_hits == 1
        assert c.stats.misses == 1
        assert c.stats.hit_rate == 0.5
        assert c.stats.tokens_avoided == 42

    def test_hit_rate_of_an_unused_cache_is_zero_not_an_error(self) -> None:
        assert cache().stats.hit_rate == 0.0
