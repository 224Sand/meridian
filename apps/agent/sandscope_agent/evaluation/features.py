"""Features describing what retrieval returned for one question.

These are the inputs a decision about answerability can be made from, whether
that decision is a hand-written band or a fitted model. Keeping extraction in
one place means the heuristic and the classifier are compared on identical
information, which is the only way the comparison says anything.

Nothing here is normalised across a result set. Sprint 2 established that the
normalised fused score is 1.0 for the top hit of every query by construction and
therefore carries no information about whether the match was any good.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

from sandscope_agent.retrieval.evidence import (
    _CONTAINS_A_VALUE,
    _DEMANDS_A_VALUE,
    term_coverage,
)
from sandscope_agent.retrieval.hybrid import HybridRetriever, RetrievalResult
from sandscope_agent.retrieval.tokenize import tokenize


@dataclass(frozen=True, slots=True)
class Features:
    #: Raw top-1 signals. The pair the Sprint 2 gate used.
    top_dense: float
    top_lexical: float
    combined: float

    #: Depth: a single strong hit and three strong hits mean different things.
    mean_dense_top3: float
    mean_lexical_top3: float

    #: Separation between the best hit and the runner-up. A question the corpus
    #: genuinely answers tends to have one clear best match; a question it does
    #: not tends to have several equally mediocre ones. This is the feature the
    #: hand-written gate never had.
    lexical_margin: float
    dense_margin: float

    #: Concentration of the score mass. Low entropy means the evidence points
    #: somewhere specific.
    score_entropy: float

    term_coverage: float
    demands_value: float
    value_present: float

    hit_count: float
    query_terms: float
    degraded: float

    def as_vector(self) -> list[float]:
        return [getattr(self, f.name) for f in fields(self)]

    @staticmethod
    def names() -> list[str]:
        return [f.name for f in fields(Features)]


def _entropy(values: list[float]) -> float:
    positive = [v for v in values if v > 0]
    total = sum(positive)
    if total <= 0 or len(positive) < 2:
        return 0.0
    return -sum((v / total) * math.log(v / total) for v in positive)


def extract(query: str, result: RetrievalResult) -> Features:
    lexical = [hit.lexical_score for hit in result.hits]
    dense = [hit.dense_score for hit in result.hits]

    top_lexical = lexical[0] if lexical else 0.0
    top_dense = max(dense) if dense else 0.0

    return Features(
        top_dense=top_dense,
        top_lexical=top_lexical,
        combined=top_dense * top_lexical,
        mean_dense_top3=sum(dense[:3]) / max(1, len(dense[:3])),
        mean_lexical_top3=sum(lexical[:3]) / max(1, len(lexical[:3])),
        lexical_margin=(lexical[0] - lexical[1]) if len(lexical) > 1 else top_lexical,
        dense_margin=(dense[0] - dense[1]) if len(dense) > 1 else top_dense,
        score_entropy=_entropy(lexical),
        term_coverage=term_coverage(query, result),
        demands_value=1.0 if _DEMANDS_A_VALUE.search(query) else 0.0,
        value_present=1.0
        if any(_CONTAINS_A_VALUE.search(hit.chunk.body) for hit in result.hits[:2])
        else 0.0,
        hit_count=float(len(result.hits)),
        query_terms=float(len(tokenize(query))),
        degraded=1.0 if result.degraded else 0.0,
    )


def extract_for(retriever: HybridRetriever, query: str, limit: int = 6) -> Features:
    return extract(query, retriever.search(query, limit=limit))
