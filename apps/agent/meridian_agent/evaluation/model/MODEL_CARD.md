# Model card - evidence-sufficiency classifier

**Task.** Given the features of one retrieval result, estimate the probability
that the retrieved evidence can answer the question asked.

**Why it exists.** The hand-written gate it replaces marked 150 of 265
unanswerable questions as answerable - a false-answer rate of 56.6%. See
`docs/06-operations/postmortems/2026-08-20-the-refusal-gate-fails-at-scale.md`.

## Training data

534 questions with labels true by construction (ADR-0010). No label was
assigned by a model; a test asserts the generation path makes no network call.
Answerable questions are generated FROM a specific chunk. Unanswerable ones come
from topics verified absent from the corpus, from properties documented for a
different entity, and from faults a service's runtime cannot exhibit.

## Features (12)

- `top_dense`
- `top_lexical`
- `combined`
- `mean_dense_top3`
- `mean_lexical_top3`
- `lexical_margin`
- `dense_margin`
- `score_entropy`
- `term_coverage`
- `demands_value`
- `value_present`
- `query_terms`

Deliberately excluded: the normalised fused retrieval score, which is 1.0 for
the top hit of every query by construction and carries no information about
whether the match was any good.

## Performance

Cross-validated with folds **grouped by source document**. Two questions
generated from one chunk share nearly all their features, and an ungrouped split
inflates every number with nothing to reveal it.

| Model | ROC AUC |
|---|---|
| Heuristic baseline (`dense x lexical`) | 0.631 |
| **This model** | **0.796** |

Operating point at a 5% false-answer budget: threshold
0.9932, recall 0.335, false-positive rate 0.045.

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
