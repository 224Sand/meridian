"""BM25 Okapi ranking.

Pure Python and dependency-free, so lexical retrieval is available in every
environment including one with no network and no API key. That matters beyond
convenience: when the embedding provider is unavailable, this is what retrieval
degrades to (ADR-0004), and a degradation path that itself has dependencies is
not a degradation path.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from sandscope_agent.retrieval.tokenize import tokenize

K1 = 1.5
B = 0.75


@dataclass(slots=True)
class BM25Index:
    """An in-memory index over chunk bodies.

    Rebuilt at startup from the database rather than persisted: the runtime's
    disk is ephemeral (NFR-005), and for a corpus this size the build is
    milliseconds.
    """

    doc_ids: list[str] = field(default_factory=list)
    _term_frequencies: list[Counter[str]] = field(default_factory=list)
    _lengths: list[int] = field(default_factory=list)
    _document_frequency: Counter[str] = field(default_factory=Counter)
    _average_length: float = 0.0

    @classmethod
    def build(cls, documents: dict[str, str]) -> BM25Index:
        index = cls()
        for doc_id in sorted(documents):
            tokens = tokenize(documents[doc_id])
            counts = Counter(tokens)
            index.doc_ids.append(doc_id)
            index._term_frequencies.append(counts)
            index._lengths.append(len(tokens))
            for term in counts:
                index._document_frequency[term] += 1

        index._average_length = sum(index._lengths) / len(index._lengths) if index._lengths else 0.0
        return index

    def __len__(self) -> int:
        return len(self.doc_ids)

    def _idf(self, term: str) -> float:
        n = len(self.doc_ids)
        df = self._document_frequency.get(term, 0)
        # Probabilistic IDF with the +1 shift, which keeps the value positive for
        # terms appearing in more than half the corpus. Without it those terms
        # score negative and actively push relevant chunks down.
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> dict[str, float]:
        terms = tokenize(query)
        if not terms or not self.doc_ids:
            return {}

        scores: dict[str, float] = {}
        for position, doc_id in enumerate(self.doc_ids):
            counts = self._term_frequencies[position]
            length = self._lengths[position]
            total = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency == 0:
                    continue
                denominator = frequency + K1 * (
                    1 - B + B * (length / self._average_length if self._average_length else 1.0)
                )
                total += self._idf(term) * (frequency * (K1 + 1)) / denominator
            if total > 0.0:
                scores[doc_id] = total
        return scores

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Top `limit` matches, ties broken by id so results are reproducible."""
        scores = self.score(query)
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
