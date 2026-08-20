# Sprint 3 — Review & Retrospective

**Sprint:** 3 — Applied ML & Evaluation Science · **Closed:** 2026-08-20 · **Release:** 0.3.0

| Lens | Position |
|---|---|
| Product stage | MVP |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| AIDLC | 2 Knowledge · 4 Grounding · 5 Evaluation |

---

## 1. Sprint goal

> Replace judgement with measurement. Every threshold becomes a defended
> operating point, and the decision the heuristics cannot make gets a trained,
> calibrated model — evaluated honestly enough that "it did not help" is a
> publishable result.

**Met.** All six stories delivered, including one that *is* a publishable "it did
not help".

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S3-DATA | Labelled dataset | 8 | 715 questions, six mechanisms, labels true by construction |
| S3-STATS | Statistical evaluation | 8 | ROC/PR, Youden, bootstrap, Wilson, exact McNemar, power — 91 tests against sklearn/scipy |
| S3-MODEL | Trained classifier | 8 | AUC 0.808 vs heuristic 0.609, served as 133 KB ONNX |
| S3-RERANK | Cross-encoder re-ranker | 8 | Built, measured, **inconclusive and published as such** |
| S3-ANN | ANN benchmark | 5 | ADR-0011: exact search until ~5,000 chunks |
| S1-09 | Seed loader (carried) | 3 | Loaded into live Neon; idempotent |

**Velocity: 40/40.** 373 tests. IMP-04 closed.

## 3. What measurement actually found

**The shipped refusal gate had a 56.6% false-answer rate.** Reported at the
Sprint 2 gate as zero, on 22 hand-written questions. On 534 generated ones it
marked 150 of 265 unanswerable questions answerable. Corrected to 3.8% by
deriving both band edges from error budgets.

**Three thresholds chosen by judgement were wrong.** The cache constant 0.86, the
sufficiency threshold 3.0, and a bare `\d` value-detector that matched "Tier 0".
Each looked reasonable and each was caught by measurement, not review.

**Calibration cost 0.2 AUC.** Platt scaling collapsed the classifier from 0.796
to 0.599. I hypothesised leakage, measured it, and was wrong: `CalibratedClassifierCV`
averages one calibrator per internal fold, and averaging saturating sigmoids does
not preserve ranking. Shipping uncalibrated restored 0.796 *and* gave exact ONNX
parity.

**An ANN index earns nothing at this corpus size.** 0.48 ms against 0.48 ms at 87
chunks. Crossover measured at roughly 5,000.

**Recall@10 understated both ANN indexes badly.** 0.370 for HNSW at 20k looks
like severe loss; the distance ratio is 1.0076 — the neighbours were 0.76%
further away. In 768 dimensions almost every disagreement is a broken tie.

**A null result was two bugs.** See the postmortem: a NaN-producing checkpoint
(NaN sorts as a no-op, so "re-ranked" was the input order) and a saturated
metric (document-level MRR 0.986, ceiling 0.014, while chunk level sat at 0.528).

## 4. Retrospective

**What worked.** Measuring before choosing, every time. Five separate numbers
that looked reasonable were wrong, and none was caught by reading the code.

Publishing the inconclusive re-ranker result rather than the point estimate. The
+0.059 MRR gain is real in the sample and its CI includes zero, and 811 examples
per arm would be needed to settle it. That number exists because the power
analysis was built in the same sprint.

**What did not.** A written-down lesson did not prevent its own recurrence. The
classifier's parity test contains
`test_the_parity_sample_spans_a_real_range_of_probabilities`, written days
earlier for exactly this reason. The re-ranker's parity sample shipped with four
copies of one pair anyway.

Separately, three source edits silently no-opped because the formatter had
rewrapped the anchor text being matched. Each reported success. One was caught
only by re-running the measurement.

**Improvements committed for Sprint 4.**
1. A behavioural change is not complete until a test or measurement demonstrates
   the new behaviour. "The edit succeeded" is not evidence.
2. When a fix is applied by text replacement, the anchor's presence is asserted
   before the write. Adopted mid-sprint; it caught the fourth occurrence.
3. Any metric reported for a component is reported at every level it has, or the
   omission is justified in writing.

## 5. Carried into Sprint 4

The re-ranker is **not wired into the request path**. A component whose benefit
is unestablished does not get to add latency to every query on a point estimate.
Revisit when gold-chunk examples exceed 200 per arm.

## 6. Gate

Sprint Review — pending Product Owner.
