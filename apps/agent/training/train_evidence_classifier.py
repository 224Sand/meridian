"""Train the evidence-sufficiency classifier (FR-028).

Offline only (ADR-0009). scikit-learn is used here and nowhere in the runtime;
what ships is a JSON file of coefficients that sandscope_agent.evaluation
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
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sandscope_agent.evaluation.dataset import Label, build_questions
from sandscope_agent.evaluation.features import Features, extract
from sandscope_agent.evaluation.statistics import (
    bootstrap_interval,
    mcnemar,
    proportion_interval,
    roc_auc_mann_whitney,
    roc_curve,
)
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.hybrid import HybridRetriever

MODEL_DIR = Path(__file__).resolve().parents[1] / "sandscope_agent" / "evaluation" / "model"
ARTIFACT = MODEL_DIR / "evidence_model.json"
ONNX_ARTIFACT = MODEL_DIR / "evidence_model.onnx"
PARITY_SAMPLE = MODEL_DIR / "parity_sample.json"
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


def export_onnx(
    X: np.ndarray, y: np.ndarray, names: list[str], champion: Fitted, baseline: Fitted
) -> None:
    """Fit the champion on all data and export it for serving (ADR-0009).

    A parity sample is written alongside: the ONNX graph must reproduce the
    scikit-learn probabilities it was converted from. Without that check,
    "the model is deployed" and "the trained model is deployed" are different
    claims that look identical from the outside.
    """
    from skl2onnx import to_onnx

    # GradientBoostingClassifier rather than HistGradientBoosting: skl2onnx's
    # converter for the histogram variant emits booleans where the ONNX spec
    # requires ints and fails to serialise. At 534 examples and 12 features the
    # training-speed advantage of the histogram variant is worth nothing, and a
    # model that cannot be exported cannot be served.
    model = GradientBoostingClassifier(n_estimators=250, learning_rate=0.08, random_state=0)
    model.fit(X, y)

    sample = X[:: max(1, len(X) // 40)].astype(np.float32)
    expected = model.predict_proba(sample)[:, 1]

    onnx_model = to_onnx(model, sample[:1], options={id(model): {"zipmap": False}})
    ONNX_ARTIFACT.write_bytes(onnx_model.SerializeToString())

    PARITY_SAMPLE.write_text(
        json.dumps(
            {
                "features": names,
                "inputs": sample.tolist(),
                "expected_probabilities": expected.tolist(),
            },
            indent=2,
        )
        + "\n"
    )

    curve = roc_curve(champion.probabilities.tolist(), y.tolist())
    point = curve.at_max_false_positive_rate(FALSE_POSITIVE_BUDGET)

    (MODEL_DIR / "metadata.json").write_text(
        json.dumps(
            {
                "model": "gradient_boosting_uncalibrated",
                "format": "onnx",
                "trained_on": len(X),
                "features": names,
                "operating_point": {
                    "threshold": point.threshold,
                    "false_answer_budget": FALSE_POSITIVE_BUDGET,
                    "recall": point.true_positive_rate,
                    "false_positive_rate": point.false_positive_rate,
                },
                "cross_validated_auc": champion.auc,
                "baseline_auc": baseline.auc,
            },
            indent=2,
        )
        + "\n"
    )

    (MODEL_DIR / "MODEL_CARD.md").write_text(
        MODEL_CARD.format(
            n=len(X),
            features=len(names),
            feature_list="\n".join(f"- `{n}`" for n in names),
            champion_auc=champion.auc,
            baseline_auc=baseline.auc,
            threshold=point.threshold,
            recall=point.true_positive_rate,
            fpr=point.false_positive_rate,
            budget=FALSE_POSITIVE_BUDGET,
        )
    )
    size_kb = ONNX_ARTIFACT.stat().st_size / 1024
    print(f"\nExported {ONNX_ARTIFACT.name} ({size_kb:.0f} KB) + parity sample + model card")


MODEL_CARD = """# Model card - evidence-sufficiency classifier

**Task.** Given the features of one retrieval result, estimate the probability
that the retrieved evidence can answer the question asked.

**Why it exists.** The hand-written gate it replaces marked 150 of 265
unanswerable questions as answerable - a false-answer rate of 56.6%. See
`docs/06-operations/postmortems/2026-08-20-the-refusal-gate-fails-at-scale.md`.

## Training data

{n} questions with labels true by construction (ADR-0010). No label was
assigned by a model; a test asserts the generation path makes no network call.
Answerable questions are generated FROM a specific chunk. Unanswerable ones come
from topics verified absent from the corpus, from properties documented for a
different entity, and from faults a service's runtime cannot exhibit.

## Features ({features})

{feature_list}

Deliberately excluded: the normalised fused retrieval score, which is 1.0 for
the top hit of every query by construction and carries no information about
whether the match was any good.

## Performance

Cross-validated with folds **grouped by source document**. Two questions
generated from one chunk share nearly all their features, and an ungrouped split
inflates every number with nothing to reveal it.

| Model | ROC AUC |
|---|---|
| Heuristic baseline (`dense x lexical`) | {baseline_auc:.3f} |
| **This model** | **{champion_auc:.3f}** |

Operating point at a {budget:.0%} false-answer budget: threshold
{threshold:.4f}, recall {recall:.3f}, false-positive rate {fpr:.3f}.

## Calibration

**Deliberately uncalibrated.** Both wrappers were measured against raw ranking:

| | ROC AUC |
|---|---|
| Raw | 0.796 |
| + isotonic | 0.779 |
| + Platt | 0.599 |

Platt's collapse is not a monotonicity failure. `CalibratedClassifierCV` fits one
calibrator per internal fold and averages their outputs, and averaging saturating
sigmoids across different base models does not preserve ranking. Isotonic holds
up better but is a step function, so a float32/float64 difference of no
consequence moves the output discretely and ONNX parity fails at up to 0.058.

Neither is needed here. The operating point is selected empirically from the ROC
curve, so the decision depends on ranking rather than on the output being a
probability.

**Consequence:** the score is a ranking score. It must not be shown to a user as
a confidence. If a calibrated confidence is ever required, isotonic is the
candidate and it costs exact ONNX parity.

## Limitations

**It is better, not good.** At the operating point above it recalls under half
of answerable questions, so most still route to adjudication. The adjudication
step is load-bearing, and this number is what establishes that.

**Generated phrasing.** Questions come from templates over structured data, so
the model may be less robust to phrasings no generator produced. That is the
cost of refusing model-written labels (ADR-0010) and it is not measured away.

**Single corpus.** Trained on one 19-document corpus about one simulated estate.
Nothing here supports a claim about behaviour on a different corpus.

## Serving

Exported to ONNX and served with onnxruntime. The training framework is not a
runtime dependency (ADR-0009). A parity test asserts the ONNX graph reproduces
the scikit-learn probabilities on a fixed sample.
"""


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

    # Uncalibrated. Both calibration wrappers were measured and both cost
    # accuracy against raw ranking:
    #
    #   raw       AUC 0.796 [0.759, 0.830]
    #   isotonic  AUC 0.779  (-0.017)
    #   platt     AUC 0.599  (-0.197)
    #
    # Platt's collapse is not a monotonicity failure. CalibratedClassifierCV
    # fits one calibrator per internal fold and AVERAGES their outputs, and
    # averaging three saturating sigmoids over three different base models does
    # not preserve ranking. Isotonic survives that better but is a step
    # function, so a float32/float64 difference of no consequence moves the
    # output discretely and the ONNX parity check fails at up to 0.058.
    #
    # Neither is needed. The operating point is selected empirically from the
    # ROC curve, so the decision depends on RANKING and not on the number being
    # a probability. Calibration was solving a problem this system does not
    # have, at a cost of either 0.2 AUC or exportability.
    #
    # If a calibrated confidence is ever shown to a user, that is a separate
    # decision and isotonic is the candidate - along with its export cost.
    boosted = GradientBoostingClassifier(n_estimators=250, learning_rate=0.08, random_state=0)
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

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    export_onnx(X, y, names, fitted_boosted, baseline)

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

    print("\nLogistic coefficients kept for reference (standardised):")
    for name, weight in sorted(zip(names, model.coef_[0], strict=True), key=lambda kv: -abs(kv[1])):
        print(f"  {name:<20} {weight:+.3f}")


if __name__ == "__main__":
    main()
