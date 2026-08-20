"""Semantic cache.

Two tiers. The exact tier keys on a normalised prompt and answers the common
case - the same question asked twice - at no similarity cost. The semantic tier
catches paraphrases.

ADR-0005 is enforced here rather than assumed: the embedding model is part of
the key. A lookup performed under a different embedding model is a MISS. It is
never a comparison, because a cosine between a Gemini vector and a locally
computed one is arithmetically valid and semantically meaningless, and would
return a confidently wrong cached answer with no error raised anywhere.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol

from sandscope_agent.retrieval.embedding import Embedder, cosine
from sandscope_agent.router.providers import Message, ModelTier

#: There is deliberately no module-level threshold constant. The threshold
#: belongs to the embedder (ADR-0008): each embedding space has its own
#: distribution, and a number derived in one space is wrong in another in the
#: silent direction. `SemanticCache` reads `embedder.similarity_threshold`.

_WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Fold away differences that cannot change the answer.

    Case and whitespace only. Punctuation is deliberately preserved: in
    operational prose "restart?" and "restart!" carry different intent, and
    `db.pool.wait_ms` must not lose its dots.
    """
    return _WHITESPACE.sub(" ", text.strip().lower())


def prompt_hash(messages: list[Message], tier: ModelTier, temperature: float) -> str:
    parts = [f"{m.role}:{normalise(m.content)}" for m in messages]
    parts.append(f"tier={tier}")
    # Temperature is part of the key. A cached deterministic answer must not be
    # served to a request that explicitly asked for variation.
    parts.append(f"temperature={temperature:.2f}")
    return hashlib.sha256(" ".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheEntry:
    prompt_hash: str
    embedding_model: str
    model_tier: ModelTier
    prompt_vec: list[float]
    response: str
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True, slots=True)
class CacheHit:
    response: str
    tokens_in: int
    tokens_out: int
    tier: str
    similarity: float


class CacheStore(Protocol):
    def get_exact(
        self, prompt_hash: str, embedding_model: str, model_tier: ModelTier
    ) -> CacheEntry | None: ...

    def candidates(self, embedding_model: str, model_tier: ModelTier) -> list[CacheEntry]: ...

    def put(self, entry: CacheEntry) -> None: ...

    def record_hit(self, prompt_hash: str) -> None: ...


@dataclass(slots=True)
class InMemoryCacheStore:
    """Reference implementation and the one used in tests.

    A Postgres-backed store lands with the seed loader; the protocol exists now
    so the cache's logic is testable without a database (IMP-04).
    """

    entries: dict[tuple[str, str, str], CacheEntry] = field(default_factory=dict)
    hits: dict[str, int] = field(default_factory=dict)

    def get_exact(
        self, prompt_hash: str, embedding_model: str, model_tier: ModelTier
    ) -> CacheEntry | None:
        return self.entries.get((prompt_hash, embedding_model, model_tier))

    def candidates(self, embedding_model: str, model_tier: ModelTier) -> list[CacheEntry]:
        return [
            entry
            for (_, model, tier), entry in self.entries.items()
            if model == embedding_model and tier == model_tier
        ]

    def put(self, entry: CacheEntry) -> None:
        self.entries[(entry.prompt_hash, entry.embedding_model, entry.model_tier)] = entry

    def record_hit(self, prompt_hash: str) -> None:
        self.hits[prompt_hash] = self.hits.get(prompt_hash, 0) + 1


@dataclass(slots=True)
class CacheStats:
    lookups: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    tokens_avoided: int = 0

    @property
    def hit_rate(self) -> float:
        return 0.0 if self.lookups == 0 else (self.exact_hits + self.semantic_hits) / self.lookups


@dataclass(slots=True)
class SemanticCache:
    embedder: Embedder
    store: CacheStore = field(default_factory=InMemoryCacheStore)
    #: None means "use the embedder's own measured threshold", which is the
    #: correct default. An explicit override exists for experiments and is not
    #: expected in production.
    threshold_override: float | None = None
    stats: CacheStats = field(default_factory=CacheStats)

    @property
    def threshold(self) -> float:
        if self.threshold_override is not None:
            return self.threshold_override
        return self.embedder.similarity_threshold

    def _key_text(self, messages: list[Message]) -> str:
        return "\n".join(normalise(m.content) for m in messages)

    def lookup(
        self, messages: list[Message], *, tier: ModelTier, temperature: float
    ) -> CacheHit | None:
        self.stats.lookups += 1
        digest = prompt_hash(messages, tier, temperature)

        exact = self.store.get_exact(digest, self.embedder.model, tier)
        if exact is not None:
            self.store.record_hit(digest)
            self.stats.exact_hits += 1
            self.stats.tokens_avoided += exact.tokens_in + exact.tokens_out
            return CacheHit(exact.response, exact.tokens_in, exact.tokens_out, "exact", 1.0)

        candidates = self.store.candidates(self.embedder.model, tier)
        if not candidates:
            self.stats.misses += 1
            return None

        query = self.embedder.embed([self._key_text(messages)])[0]
        best: CacheEntry | None = None
        best_score = -1.0
        for entry in candidates:
            score = cosine(query, entry.prompt_vec)
            if score > best_score:
                best, best_score = entry, score

        if best is not None and best_score >= self.threshold:
            self.store.record_hit(best.prompt_hash)
            self.stats.semantic_hits += 1
            self.stats.tokens_avoided += best.tokens_in + best.tokens_out
            return CacheHit(best.response, best.tokens_in, best.tokens_out, "semantic", best_score)

        self.stats.misses += 1
        return None

    def store_response(
        self,
        messages: list[Message],
        *,
        tier: ModelTier,
        temperature: float,
        response: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        self.store.put(
            CacheEntry(
                prompt_hash=prompt_hash(messages, tier, temperature),
                embedding_model=self.embedder.model,
                model_tier=tier,
                prompt_vec=self.embedder.embed([self._key_text(messages)])[0],
                response=response,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        )
