"""Embedding interface and the offline embedder.

Two implementations exist by design (ADR-0004): a hosted model for normal
operation and a deterministic local one that needs no network, no key and no
model weights. The local one is not a placeholder - it is what makes the test
suite runnable offline and what retrieval degrades to when the provider is down.

Their vectors are NOT comparable. ADR-0005 makes that structural: the model name
travels with every vector, and a lookup under a different model is a miss rather
than a cross-space comparison. Nothing in this module may erase `model`.
"""

from __future__ import annotations

import math
import zlib
from typing import Protocol, runtime_checkable

DIM = 768
"""Fixed at 768 to match the hosted model. The dimension is part of the storage
contract, so the offline embedder projects into the same space size even though
its space means something entirely different."""


@runtime_checkable
class Embedder(Protocol):
    @property
    def model(self) -> str:
        """Identifier stored alongside every vector this embedder produces."""

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _char_ngrams(token: str, n: int = 4) -> list[str]:
    if len(token) <= n:
        return [token]
    padded = f"^{token}$"
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


class HashingEmbedder:
    """Deterministic hashed bag-of-features projected into `DIM` dimensions.

    Signed hashing keeps unrelated features from accumulating in the same
    direction. Character n-grams sit alongside whole tokens so that `restarts`
    and `restart` land near each other without a stemmer.

    `zlib.crc32` rather than the builtin `hash()`: Python salts string hashing per
    process, so `hash()` would make these vectors stable within one run and
    different in the next - and a vector store written by one process and queried
    by another would silently return nonsense.
    """

    model = "hashing-v1"
    dim = DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        from meridian_agent.retrieval.tokenize import tokenize

        vector = [0.0] * DIM
        features: list[str] = []
        for token in tokenize(text):
            features.append(token)
            features.extend(_char_ngrams(token))

        counts: dict[str, int] = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1

        for feature, count in counts.items():
            digest = zlib.crc32(feature.encode("utf-8"))
            index = digest % DIM
            sign = 1.0 if (digest >> 16) & 1 else -1.0
            # Sublinear term frequency: a term appearing 40 times is not 40 times
            # more indicative than one appearing once.
            vector[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b, strict=True))
