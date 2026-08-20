"""Cross-encoder re-ranking at serving time.

A bi-encoder scores query and passage independently and compares vectors. A
cross-encoder reads both together, so it can weigh how the question's terms
interact with the passage's - which is the distinction retrieval keeps getting
wrong here, where a question about one entity's property retrieves the passage
stating that property for a DIFFERENT entity.

Serving is ONNX plus the Rust tokenizer core (ADR-0009). `transformers` and
`torch` are training-time only: torch alone is ~1GB installed against ~50MB for
onnxruntime, and neither is importable from this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime
from tokenizers import Tokenizer

MODEL_DIR = Path(__file__).resolve().parent / "reranker"
ONNX_PATH = MODEL_DIR / "reranker.onnx"
TOKENIZER_PATH = MODEL_DIR / "tokenizer.json"
METRICS_PATH = MODEL_DIR / "metrics.json"
MAX_LENGTH = 256


class RerankerUnavailableError(RuntimeError):
    """The trained artefact is missing.

    Raised rather than silently returning the input order. A re-ranker that
    quietly does nothing is worse than one that is absent, because the ranking
    still looks re-ranked.
    """


@dataclass(frozen=True, slots=True)
class Scored:
    index: int
    score: float


def is_available() -> bool:
    return ONNX_PATH.exists() and TOKENIZER_PATH.exists()


@lru_cache(maxsize=1)
def _tokenizer() -> Tokenizer:
    if not TOKENIZER_PATH.exists():
        raise RerankerUnavailableError(f"missing {TOKENIZER_PATH}; run training/train_reranker.py")
    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    tokenizer.enable_truncation(max_length=MAX_LENGTH)
    tokenizer.enable_padding(length=None)
    return tokenizer


@lru_cache(maxsize=1)
def _session() -> onnxruntime.InferenceSession:
    if not ONNX_PATH.exists():
        raise RerankerUnavailableError(f"missing {ONNX_PATH}; run training/train_reranker.py")
    options = onnxruntime.SessionOptions()
    # One thread. The container has 2 vCPU shared with request handling, and a
    # thread pool contending with the API server costs more than it recovers.
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return onnxruntime.InferenceSession(str(ONNX_PATH), options)


def score(query: str, passages: list[str]) -> list[float]:
    """Relevance logit per passage. Higher is more relevant."""
    if not passages:
        return []

    encodings = _tokenizer().encode_batch([(query, passage) for passage in passages])
    inputs = {
        "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
    }
    session = _session()
    expected = {i.name for i in session.get_inputs()}
    logits = session.run(None, {k: v for k, v in inputs.items() if k in expected})[0]
    return np.asarray(logits).reshape(-1).astype(float).tolist()


def rerank(query: str, passages: list[str], top_k: int | None = None) -> list[Scored]:
    """Reorder passages by cross-encoder relevance.

    Returns indices into the input list rather than the passages themselves, so
    the caller keeps whatever it had attached to each one - chunk id, document,
    retrieval scores - without this module needing to know about any of it.
    """
    scores = score(query, passages)
    ordered = sorted(
        (Scored(index=i, score=s) for i, s in enumerate(scores)),
        key=lambda s: (-s.score, s.index),
    )
    return ordered[:top_k] if top_k else ordered


def metrics() -> dict[str, object]:
    """Measured performance of the shipped artefact.

    Read from the file written at training time, so the numbers quoted anywhere
    else come from the run that produced this model rather than from memory.
    """
    if not METRICS_PATH.exists():
        raise RerankerUnavailableError(f"missing {METRICS_PATH}")
    result: dict[str, object] = json.loads(METRICS_PATH.read_text())
    return result
