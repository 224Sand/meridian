"""Cross-encoder re-ranking as served.

The serving path is ONNX plus the Rust tokenizer core. torch and transformers
are training-time only (ADR-0009) and a test parses this module's imports to
prove neither reaches the runtime.
"""

from __future__ import annotations

import json
import math

import pytest

from sandscope_agent.retrieval import reranker

pytestmark = pytest.mark.skipif(
    not reranker.is_available(), reason="trained artefact absent; run training/train_reranker.py"
)

POOL_QUESTION = "why is the connection pool exhausted"
POOL_PASSAGE = (
    "Callers hold connections longer than the pool can recycle them. Wait time "
    "climbs first, available connections reach zero."
)
CERT_PASSAGE = (
    "A certificate has expired. Clients refuse the handshake, and failure is "
    "total and instantaneous rather than gradual."
)


class TestParityWithTraining:
    """ADR-0009: the exported graph must reproduce what it was converted from."""

    def test_onnx_matches_torch_on_the_recorded_sample(self) -> None:
        import numpy as np
        import onnxruntime

        sample = json.loads((reranker.MODEL_DIR / "parity_sample.json").read_text())
        session = onnxruntime.InferenceSession(str(reranker.ONNX_PATH))
        feed = {i.name: np.array(sample[i.name], dtype=np.int64) for i in session.get_inputs()}
        produced = np.asarray(session.run(None, feed)[0]).reshape(-1)

        for got, expected in zip(produced, sample["expected_logits"], strict=True):
            assert float(got) == pytest.approx(expected, abs=1e-4)

    def test_the_parity_sample_spans_a_real_range(self) -> None:
        """Four copies of one pair produce four identical logits, and a parity
        check where every row scores the same passes while testing nothing."""
        logits = json.loads((reranker.MODEL_DIR / "parity_sample.json").read_text())[
            "expected_logits"
        ]
        assert max(logits) - min(logits) > 2.0, f"parity sample is degenerate: {logits}"


class TestScoring:
    def test_scores_are_finite(self) -> None:
        """A NaN-producing checkpoint silently ranked nothing for an entire
        training run: sorting NaN preserves input order, so every metric equalled
        the baseline and the run looked like a clean negative result."""
        scores = reranker.score(POOL_QUESTION, [POOL_PASSAGE, CERT_PASSAGE])
        assert all(math.isfinite(s) for s in scores), scores

    def test_the_relevant_passage_scores_higher(self) -> None:
        relevant, irrelevant = reranker.score(POOL_QUESTION, [POOL_PASSAGE, CERT_PASSAGE])
        assert relevant > irrelevant

    def test_scoring_is_deterministic(self) -> None:
        passages = [POOL_PASSAGE, CERT_PASSAGE]
        assert reranker.score(POOL_QUESTION, passages) == reranker.score(POOL_QUESTION, passages)

    def test_empty_input_is_handled(self) -> None:
        assert reranker.score(POOL_QUESTION, []) == []
        assert reranker.rerank(POOL_QUESTION, []) == []

    def test_scores_one_value_per_passage(self) -> None:
        passages = [POOL_PASSAGE, CERT_PASSAGE, POOL_PASSAGE]
        assert len(reranker.score(POOL_QUESTION, passages)) == 3


class TestRerank:
    def test_reorders_by_relevance(self) -> None:
        ordered = reranker.rerank(POOL_QUESTION, [CERT_PASSAGE, POOL_PASSAGE])
        assert ordered[0].index == 1, "the relevant passage should come first"

    def test_returns_indices_not_passages(self) -> None:
        """So the caller keeps whatever it had attached to each passage - chunk
        id, document, retrieval scores - without this module knowing about it."""
        ordered = reranker.rerank(POOL_QUESTION, [POOL_PASSAGE, CERT_PASSAGE])
        assert {s.index for s in ordered} == {0, 1}

    def test_top_k_truncates(self) -> None:
        ordered = reranker.rerank(POOL_QUESTION, [POOL_PASSAGE, CERT_PASSAGE], top_k=1)
        assert len(ordered) == 1

    def test_ties_break_on_index_for_reproducibility(self) -> None:
        ordered = reranker.rerank(POOL_QUESTION, [POOL_PASSAGE, POOL_PASSAGE])
        assert [s.index for s in ordered] == [0, 1]

    def test_scores_are_monotonically_ordered(self) -> None:
        ordered = reranker.rerank(POOL_QUESTION, [CERT_PASSAGE, POOL_PASSAGE, CERT_PASSAGE])
        scores = [s.score for s in ordered]
        assert scores == sorted(scores, reverse=True)


class TestMeasuredPerformance:
    def test_metrics_record_both_levels(self) -> None:
        """Document level is saturated at 0.986 MRR and chunk level is not.
        Recording only the first is how the first run concluded the re-ranker
        did not help."""
        metrics = reranker.metrics()
        assert "document_level" in metrics
        assert "chunk_level" in metrics

    def test_chunk_level_is_where_the_headroom_is(self) -> None:
        chunk = reranker.metrics()["chunk_level"]  # type: ignore[index]
        document = reranker.metrics()["document_level"]  # type: ignore[index]
        assert chunk["hybrid"]["mrr"] < document["hybrid"]["mrr"] - 0.2

    def test_latency_fits_a_request_budget(self) -> None:
        latency = reranker.metrics()["rerank_latency_p50_ms"]
        assert isinstance(latency, (int, float))
        assert latency < 100, f"{latency}ms for 20 candidates is too slow to sit in a request"


class TestNoTrainingFrameworkAtRuntime:
    def test_the_serving_module_imports_no_training_framework(self) -> None:
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(reranker))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        forbidden = {"torch", "transformers", "sklearn", "tensorflow"}
        assert not (imported & forbidden), f"serving module imports {imported & forbidden}"
        assert {"onnxruntime", "tokenizers"} <= imported

    def test_the_graph_is_small_enough_to_ship(self) -> None:
        megabytes = reranker.ONNX_PATH.stat().st_size / 1024 / 1024
        assert megabytes < 60, f"{megabytes:.0f} MB is too large for the container"

    def test_a_missing_artefact_raises_rather_than_passing_through(self, tmp_path) -> None:
        """A re-ranker that quietly returns the input order is worse than one
        that is absent, because the ranking still looks re-ranked."""
        original = reranker.ONNX_PATH
        reranker._session.cache_clear()
        reranker.ONNX_PATH = tmp_path / "absent.onnx"
        try:
            with pytest.raises(reranker.RerankerUnavailableError, match="missing"):
                reranker._session()
        finally:
            reranker.ONNX_PATH = original
            reranker._session.cache_clear()
