"""Serving for the evidence-sufficiency classifier.

Loads an ONNX graph and evaluates it with onnxruntime. scikit-learn is not
imported here and is not a runtime dependency (ADR-0009): what ships is a
394 KB graph and a 50 MB runtime, against the 2-3 GB the training stack would
cost.

The operating threshold travels with the model in `metadata.json` rather than
living in code. A model and the threshold it was calibrated at are one artefact;
separating them lets a redeploy silently pair new probabilities with an old
cut-off.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime

from meridian_agent.evaluation.features import Features

MODEL_DIR = Path(__file__).resolve().parent / "model"
ONNX_PATH = MODEL_DIR / "evidence_model.onnx"
METADATA_PATH = MODEL_DIR / "metadata.json"


class ModelUnavailableError(RuntimeError):
    """The trained artefact is missing.

    Raised rather than falling back silently to the heuristic. The heuristic has
    a measured false-answer rate of 56.6%, so degrading to it without saying so
    would be the worst available behaviour.
    """


@dataclass(frozen=True, slots=True)
class Prediction:
    probability: float
    threshold: float
    sufficient: bool

    @property
    def margin(self) -> float:
        return self.probability - self.threshold


@dataclass(frozen=True, slots=True)
class Metadata:
    features: tuple[str, ...]
    threshold: float
    false_answer_budget: float
    auc: float
    baseline_auc: float
    trained_on: int


@lru_cache(maxsize=1)
def load_metadata() -> Metadata:
    if not METADATA_PATH.exists():
        raise ModelUnavailableError(
            f"missing {METADATA_PATH}; run training/train_evidence_classifier.py"
        )
    raw = json.loads(METADATA_PATH.read_text())
    point = raw["operating_point"]
    return Metadata(
        features=tuple(raw["features"]),
        threshold=float(point["threshold"]),
        false_answer_budget=float(point["false_answer_budget"]),
        auc=float(raw["cross_validated_auc"]),
        baseline_auc=float(raw["baseline_auc"]),
        trained_on=int(raw["trained_on"]),
    )


@lru_cache(maxsize=1)
def _session() -> onnxruntime.InferenceSession:
    if not ONNX_PATH.exists():
        raise ModelUnavailableError(
            f"missing {ONNX_PATH}; run training/train_evidence_classifier.py"
        )
    options = onnxruntime.SessionOptions()
    # Single-threaded: the container has 2 vCPU shared with the API, and a
    # 394 KB tree ensemble gains nothing from a thread pool while contending
    # with request handling.
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return onnxruntime.InferenceSession(str(ONNX_PATH), options)


def _vector(features: Features, names: tuple[str, ...]) -> list[float]:
    """Order the features exactly as training saw them.

    Built by name, never by dataclass field order. A feature reordered or
    inserted upstream would otherwise feed the model a silently permuted vector
    and produce confident nonsense with no error anywhere.
    """
    available = dict(zip(Features.names(), features.as_vector(), strict=True))
    missing = [n for n in names if n not in available]
    if missing:
        raise ModelUnavailableError(
            f"model expects features this build does not produce: {missing}"
        )
    return [available[name] for name in names]


def predict_proba(features: Features) -> float:
    metadata = load_metadata()
    session = _session()
    row = np.array([_vector(features, metadata.features)], dtype=np.float32)
    outputs = session.run(None, {session.get_inputs()[0].name: row})
    probabilities = outputs[1]
    return float(np.asarray(probabilities)[0][1])


def predict(features: Features) -> Prediction:
    metadata = load_metadata()
    probability = predict_proba(features)
    return Prediction(
        probability=probability,
        threshold=metadata.threshold,
        sufficient=probability >= metadata.threshold,
    )


def is_available() -> bool:
    return ONNX_PATH.exists() and METADATA_PATH.exists()
