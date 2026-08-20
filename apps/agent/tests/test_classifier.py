"""The trained classifier as served.

The parity test is the one that matters. ADR-0009 splits training from serving,
and an export step is where numerical behaviour changes silently: without a
check, "the model is deployed" and "the trained model is deployed" are different
claims that look identical from outside.

These tests import onnxruntime, which is a RUNTIME dependency. They do not
import scikit-learn, which is not.
"""

from __future__ import annotations

import json

import pytest

from meridian_agent.evaluation.classifier import (
    METADATA_PATH,
    ONNX_PATH,
    Features,
    ModelUnavailableError,
    _vector,
    is_available,
    load_metadata,
    predict,
    predict_proba,
)

PARITY_SAMPLE = ONNX_PATH.parent / "parity_sample.json"

pytestmark = pytest.mark.skipif(
    not is_available(), reason="trained artefact absent; run training/train_evidence_classifier.py"
)


class TestParityWithTraining:
    """ADR-0009: the exported graph must reproduce what it was converted from."""

    def test_onnx_matches_scikit_learn_on_the_recorded_sample(self) -> None:
        import numpy as np
        import onnxruntime

        sample = json.loads(PARITY_SAMPLE.read_text())
        session = onnxruntime.InferenceSession(str(ONNX_PATH))
        rows = np.array(sample["inputs"], dtype=np.float32)
        produced = np.asarray(session.run(None, {session.get_inputs()[0].name: rows})[1])[:, 1]

        for got, expected in zip(produced, sample["expected_probabilities"], strict=True):
            assert float(got) == pytest.approx(expected, abs=1e-5)

    def test_the_parity_sample_is_not_trivially_small(self) -> None:
        sample = json.loads(PARITY_SAMPLE.read_text())
        assert len(sample["inputs"]) >= 20

    def test_the_parity_sample_spans_a_real_range_of_probabilities(self) -> None:
        """A sample where every row scores the same would pass parity while
        testing nothing."""
        probabilities = json.loads(PARITY_SAMPLE.read_text())["expected_probabilities"]
        assert max(probabilities) - min(probabilities) > 0.3


class TestMetadata:
    def test_the_threshold_travels_with_the_model(self) -> None:
        """A model and the threshold it was calibrated at are one artefact.
        Separating them lets a redeploy pair new probabilities with an old
        cut-off and nothing complains."""
        metadata = load_metadata()
        assert 0.0 < metadata.threshold < 1.0
        assert metadata.false_answer_budget == pytest.approx(0.05)

    def test_the_model_beats_the_heuristic_it_replaces(self) -> None:
        metadata = load_metadata()
        assert metadata.auc > metadata.baseline_auc

    def test_the_model_card_records_the_limitation(self) -> None:
        """The card must state that the model is better rather than good."""
        card = (ONNX_PATH.parent / "MODEL_CARD.md").read_text()
        assert "better, not good" in card
        assert "Limitations" in card

    def test_metadata_and_graph_agree_on_the_feature_count(self) -> None:
        import onnxruntime

        session = onnxruntime.InferenceSession(str(ONNX_PATH))
        shape = session.get_inputs()[0].shape
        assert shape[1] == len(load_metadata().features)


class TestFeatureOrdering:
    def test_features_are_selected_by_name_not_by_position(self) -> None:
        """A feature inserted or reordered upstream would otherwise feed the
        model a permuted vector and produce confident nonsense."""
        names = load_metadata().features
        features = Features(
            top_dense=0.5,
            top_lexical=10.0,
            combined=5.0,
            mean_dense_top3=0.4,
            mean_lexical_top3=8.0,
            lexical_margin=2.0,
            dense_margin=0.1,
            score_entropy=1.2,
            term_coverage=0.8,
            demands_value=1.0,
            value_present=0.0,
            hit_count=6.0,
            query_terms=7.0,
            degraded=0.0,
        )
        vector = _vector(features, names)
        assert len(vector) == len(names)
        assert vector[names.index("top_dense")] == 0.5
        assert vector[names.index("top_lexical")] == 10.0

    def test_a_missing_feature_raises_rather_than_padding(self) -> None:
        features = Features(
            top_dense=0.5,
            top_lexical=1.0,
            combined=0.5,
            mean_dense_top3=0.4,
            mean_lexical_top3=1.0,
            lexical_margin=0.1,
            dense_margin=0.1,
            score_entropy=0.1,
            term_coverage=0.5,
            demands_value=0.0,
            value_present=0.0,
            hit_count=1.0,
            query_terms=3.0,
            degraded=0.0,
        )
        with pytest.raises(ModelUnavailableError, match="features this build does not produce"):
            _vector(features, ("top_dense", "a_feature_that_does_not_exist"))


class TestPrediction:
    def make(self, **overrides: float) -> Features:
        base = dict(
            top_dense=0.2,
            top_lexical=3.0,
            combined=0.6,
            mean_dense_top3=0.15,
            mean_lexical_top3=2.0,
            lexical_margin=0.5,
            dense_margin=0.05,
            score_entropy=1.5,
            term_coverage=0.4,
            demands_value=0.0,
            value_present=1.0,
            hit_count=6.0,
            query_terms=6.0,
            degraded=0.0,
        )
        base.update(overrides)
        return Features(**base)  # type: ignore[arg-type]

    def test_probability_is_a_probability(self) -> None:
        assert 0.0 <= predict_proba(self.make()) <= 1.0

    def test_prediction_reports_the_threshold_it_used(self) -> None:
        prediction = predict(self.make())
        assert prediction.threshold == load_metadata().threshold
        assert prediction.sufficient == (prediction.probability >= prediction.threshold)

    def test_stronger_evidence_scores_higher(self) -> None:
        weak = predict_proba(self.make(top_dense=0.05, top_lexical=1.0, combined=0.05))
        strong = predict_proba(
            self.make(
                top_dense=0.6,
                top_lexical=20.0,
                combined=12.0,
                mean_dense_top3=0.5,
                mean_lexical_top3=15.0,
            )
        )
        assert strong > weak

    def test_inference_is_deterministic(self) -> None:
        features = self.make()
        assert predict_proba(features) == predict_proba(features)

    def test_margin_is_signed_relative_to_the_threshold(self) -> None:
        prediction = predict(self.make())
        assert (prediction.margin >= 0) == prediction.sufficient


class TestNoTrainingFrameworkAtRuntime:
    def test_the_serving_module_does_not_import_a_training_framework(self) -> None:
        """ADR-0009.

        Checked by parsing the import statements, not by searching the text. The
        first version of this test grepped for substrings and failed on its own
        module's docstring, which says scikit-learn is not imported here. A test
        that cannot tell prose from code will be deleted rather than fixed.
        """
        import ast
        import inspect

        from meridian_agent.evaluation import classifier

        tree = ast.parse(inspect.getsource(classifier))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        forbidden = {"sklearn", "torch", "tensorflow", "skl2onnx", "scipy", "pandas"}
        assert not (imported & forbidden), f"serving module imports {imported & forbidden}"
        assert "onnxruntime" in imported, "serving must go through the runtime, not a shim"

    def test_the_graph_is_small_enough_to_ship(self) -> None:
        size_kb = ONNX_PATH.stat().st_size / 1024
        assert size_kb < 2048, f"{size_kb:.0f} KB is larger than a control-plane model should be"

    def test_a_missing_artefact_raises_rather_than_degrading_silently(self, tmp_path) -> None:
        """Falling back to the heuristic without saying so would be the worst
        available behaviour: its measured false-answer rate is 56.6%."""
        import meridian_agent.evaluation.classifier as module

        original = module.METADATA_PATH
        module.load_metadata.cache_clear()
        module.METADATA_PATH = tmp_path / "absent.json"
        try:
            with pytest.raises(ModelUnavailableError, match="missing"):
                module.load_metadata()
        finally:
            module.METADATA_PATH = original
            module.load_metadata.cache_clear()
        assert METADATA_PATH.exists()
