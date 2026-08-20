"""Hybrid retrieval: lexical and dense, fused.

Two signals, because they fail differently. BM25 finds exact identifiers and
misses paraphrase. Dense retrieval finds paraphrase and drifts on rare
identifiers - which in operational prose are exactly the terms that matter.

When the dense side is unavailable, retrieval runs lexical-only and SAYS SO.
It does not substitute a different embedding space (ADR-0005), and it does not
quietly return worse results while reporting normal operation. `degraded` is on
the result, travels into the run record, and is shown to the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sandscope_agent.retrieval.bm25 import BM25Index
from sandscope_agent.retrieval.corpus import Chunk
from sandscope_agent.retrieval.embedding import Embedder, cosine

#: Weight on the dense signal when both are available. Lexical is weighted
#: higher because identifiers carry more diagnostic information than phrasing in
#: this corpus, and because BM25's separation between answerable and
#: unanswerable was measured at better than 3x (Sprint 1 review).
DENSE_WEIGHT = 0.4
LEXICAL_WEIGHT = 0.6


@dataclass(frozen=True, slots=True)
class Retrieved:
    chunk: Chunk
    score: float
    lexical_score: float
    dense_score: float

    @property
    def document_id(self) -> str:
        return self.chunk.document_id


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    hits: tuple[Retrieved, ...]
    degraded: bool
    degraded_reason: str = ""

    @property
    def top_score(self) -> float:
        return self.hits[0].score if self.hits else 0.0

    @property
    def top_lexical(self) -> float:
        return self.hits[0].lexical_score if self.hits else 0.0

    @property
    def top_dense(self) -> float:
        return max((h.dense_score for h in self.hits), default=0.0)


def _normalise_scores(scores: dict[str, float]) -> dict[str, float]:
    """Scale to [0, 1] within this result set.

    BM25 is unbounded and cosine is bounded, so fusing the raw numbers would let
    BM25's scale decide every ranking. Normalising within the result set is the
    cheapest fusion that respects both, and it is why `top_lexical` is carried
    separately: the refusal gate needs the UNNORMALISED lexical score, since a
    normalised top score is 1.0 whether the match was excellent or terrible.
    """
    if not scores:
        return {}
    highest = max(scores.values())
    if highest <= 0:
        return dict.fromkeys(scores, 0.0)
    return {key: value / highest for key, value in scores.items()}


@dataclass(slots=True)
class HybridRetriever:
    chunks: list[Chunk]
    index: BM25Index = field(init=False)
    embedder: Embedder | None = None
    vectors: dict[str, list[float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.index = BM25Index.build({c.id: c.body for c in self.chunks})

    def build_vectors(self) -> None:
        """Embed the corpus with the configured embedder.

        Vectors are keyed by chunk id only because `self.embedder` is the single
        model in play for this retriever instance. Persisted vectors carry their
        model explicitly (chunk_embedding.model), which is where ADR-0005 is
        enforced across processes.
        """
        if self.embedder is None:
            return
        ordered = sorted(self.chunks, key=lambda c: c.id)
        embeddings = self.embedder.embed([c.body for c in ordered])
        self.vectors = {c.id: vec for c, vec in zip(ordered, embeddings, strict=True)}

    def search(self, query: str, limit: int = 6) -> RetrievalResult:
        by_id = {c.id: c for c in self.chunks}
        lexical_raw = self.index.score(query)
        lexical = _normalise_scores(lexical_raw)

        dense_raw: dict[str, float] = {}
        degraded = False
        reason = ""

        if self.embedder is None or not self.vectors:
            degraded = True
            reason = (
                "no embedder configured" if self.embedder is None else "corpus vectors not built"
            )
        else:
            try:
                query_vec = self.embedder.embed([query])[0]
            # Broad on purpose: an embedder can fail as a timeout, an auth
            # error, a malformed response or a library exception, and the
            # correct response to every one of them is the same - degrade to
            # lexical and say so.
            except Exception as error:
                degraded = True
                reason = f"embedding provider unavailable: {error}"
            else:
                dense_raw = {
                    chunk_id: cosine(query_vec, vec) for chunk_id, vec in self.vectors.items()
                }

        dense = _normalise_scores({k: v for k, v in dense_raw.items() if v > 0})

        if degraded:
            fused = lexical
        else:
            keys = set(lexical) | set(dense)
            fused = {
                key: LEXICAL_WEIGHT * lexical.get(key, 0.0) + DENSE_WEIGHT * dense.get(key, 0.0)
                for key in keys
            }

        ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        hits = tuple(
            Retrieved(
                chunk=by_id[chunk_id],
                score=score,
                lexical_score=lexical_raw.get(chunk_id, 0.0),
                dense_score=dense_raw.get(chunk_id, 0.0),
            )
            for chunk_id, score in ranked
            if score > 0
        )
        return RetrievalResult(query=query, hits=hits, degraded=degraded, degraded_reason=reason)
