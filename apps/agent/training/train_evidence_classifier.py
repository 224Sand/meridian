"""Train the evidence-sufficiency classifier (FR-028).

Offline only (ADR-0009). scikit-learn is used here and nowhere in the runtime;
what ships is a JSON file of coefficients that meridian_agent.evaluation
.classifier evaluates in pure Python.

Cross-validation is GROUPED by source document. Two questions generated from one
chunk share nearly all their features, so an ungrouped split puts near-duplicates
on both sides and every score comes out inflated with nothing to reveal it.

    python training/train_evidence_classifier.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from meridian_agent.evaluation.dataset import Label, build_questions
from meridian_agent.evaluation.features import Features, extract
from meridian_agent.evaluation.statistics import (
    bootstrap_interval,
    mcnemar,
    proportion_interval,
    roc_auc_mann_whitney,
    roc_curve,
)
from meridian_agent.retrieval.corpus import chunk_corpus, load_corpus
from meridian_agent.retrieval.embedding import HashingEmbedder
from meridian_agent.retrieval.hybrid import HybridRetriever

ARTIFACT = Path(__file__).resolve().parents[1] / "meridian_agent" / "evaluation" / "evidence_model.json"
#: Answering something the corpus cannot support is the expensive error, so the
#: false-positive rate is a constraint rather than something to trade away.
FALSE_POSITIVE_BUDGET = 0.05


@dataclass
class Fitted:
    name: str
    probabilities: np.ndarray
    auc: float


def build_matrix() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    retriever = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
    retriever.build_vectors()

    questions = build_questions()
    rows, labels, groups = [], [], []
    for question in questions:
        result = retriever.search(question.text)
        rows.append(extract(question.text, result).as_vector())
        labels.append(1 if question.label is Label.ANSWERABLE else 0)
        groups.append(question.group)

    return np.array(rows), np.array(labels), np.array(groups), Features.names()


def drop_constant(X: np.ndarray, names: list[str]) -> tuple[np.ndarray, list[str]]:
    """A feature with no variance carries no information and destabilises the
    scaler. Dropping it is bookkeeping, not tuning."""
    keep = [i for i in range(X.shape[1]) if len(np.unique(X[:, i])) > 1]
    dropped = [names[i] for i in range(len(names)) if i not in keep]
    if dropped:
        print(f"  dropped constant features: {', '.join(dropped)}")
    return X[:, keep], [names[i] for i in keep]


def evaluate(name: str, probabilities: np.ndarray, y: np.ndarray) -> Fitted:
    scores = probabilities.tolist()
    labels = y.tolist()
    interval = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=1200)
    print(f"  {name:<24} AUC {interval}")
    return Fitted(name, probabilities, interval.point)


def main() -> None:
    print("Building feature matrix...")
    X, y, groups, names = build_matrix()
    X, names = drop_constant(X, names)
    print(f"  {X.shape[0]} examples, {X.shape[1]} features, {len(set(groups))} groups")
    print(f"  answerable {int(y.sum())} / unanswerable {int((1 - y).sum())}\n")

    splitter = GroupKFold(n_splits=5)
    print("Cross-validated (grouped by source document, 5 folds):")

    # Baseline: the shipped heuristic's own score, as a predictor.
    combined_index = names.index("combined")
    baseline = evaluate("heuristic (combined)", X[:, combined_index], y)

    logistic = Pipeline(
        [("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=2000, C=1.0))]
    )
    logistic_probs = cross_val_predict(
        logistic, X, y, groups=groups, cv=splitter, method="predict_proba"
    )[:, 1]
    fitted_logistic = evaluate("logistic regression", logistic_probs, y)

    boosted = CalibratedClassifierCV(
        HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, random_state=0),
        method="isotonic",
        cv=3,
    )
    boosted_probs = cross_val_predict(
        boosted, X, y, groups=groups, cv=splitter, method="predict_proba"
    )[:, 1]
    fitted_boosted = evaluate("gradient boosting", boosted_probs, y)

    champion = max([fitted_logistic, fitted_boosted], key=lambda f: f.auc)
    print(f"\nChampion: {champion.name}")

    print(f"\nOperating point at a {FALSE_POSITIVE_BUDGET:.0%} false-positive budget:")
    results = {}
    for fitted in (baseline, fitted_logistic, fitted_boosted):
        curve = roc_curve(fitted.probabilities.tolist(), y.tolist())
        try:
            point = curve.at_max_false_positive_rate(FALSE_POSITIVE_BUDGET)
        except ValueError:
            print(f"  {fitted.name:<24} unreachable")
            continue
        results[fitted.name] = (fitted, point)
        print(
            f"  {fitted.name:<24} threshold {point.threshold:.4f}  "
            f"recall {point.true_positive_rate:.3f}  FPR {point.false_positive_rate:.3f}"
        )

    # Is the champion's improvement real, or is it noise?
    if baseline.name in results and champion.name in results:
        _, base_point = results[baseline.name]
        _, champ_point = results[champion.name]
        base_correct = [
            (p >= base_point.threshold) == bool(t)
            for p, t in zip(baseline.probabilities, y, strict=True)
        ]
        champ_correct = [
            (p >= champ_point.threshold) == bool(t)
            for p, t in zip(champion.probabilities, y, strict=True)
        ]
        test = mcnemar(champ_correct, base_correct)
        print(
            f"\nMcNemar, champion vs heuristic at the same budget:\n"
            f"  champion only correct {test.only_a_correct}, "
            f"heuristic only correct {test.only_b_correct}, p = {test.p_value:.2e}"
        )
        print(f"  {'SIGNIFICANT' if test.is_significant() else 'NOT significant'} at alpha 0.05")
        print(f"  heuristic accuracy {proportion_interval(sum(base_correct), len(y))}")
        print(f"  champion accuracy  {proportion_interval(sum(champ_correct), len(y))}")

    # Export the LOGISTIC model regardless of which won on AUC: a linear model
    # serves as a vector of coefficients in pure Python, which is what ADR-0009
    # requires. If the boosted model wins by enough to matter, that is an ONNX
    # export decision and belongs in its own change.
    logistic.fit(X, y)
    scaler: StandardScaler = logistic.named_steps["scale"]
    model: LogisticRegression = logistic.named_steps["clf"]
    curve = roc_curve(logistic_probs.tolist(), y.tolist())
    point = curve.at_max_false_positive_rate(FALSE_POSITIVE_BUDGET)

    ARTIFACT.write_text(
        json.dumps(
            {
                "model": "logistic_regression",
                "trained_on": int(X.shape[0]),
                "features": names,
                "mean": scaler.mean_.tolist(),
                "scale": scaler.scale_.tolist(),
                "coefficients": model.coef_[0].tolist(),
                "intercept": float(model.intercept_[0]),
                "operating_point": {
                    "threshold": point.threshold,
                    "false_positive_budget": FALSE_POSITIVE_BUDGET,
                    "recall_at_threshold": point.true_positive_rate,
                    "false_positive_rate": point.false_positive_rate,
                },
                "cross_validated_auc": fitted_logistic.auc,
                "baseline_auc": baseline.auc,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nWrote {ARTIFACT.relative_to(ARTIFACT.parents[2])}")

    print("\nLogistic coefficients (standardised, so magnitudes compare):")
    for name, weight in sorted(
        zip(names, model.coef_[0], strict=True), key=lambda kv: -abs(kv[1])
    ):
        print(f"  {name:<20} {weight:+.3f}")


if __name__ == "__main__":
    main()
