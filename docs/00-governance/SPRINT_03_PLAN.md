# Sprint 3 — Applied ML & Evaluation Science

**Sprint goal:** Replace judgement with measurement. Every threshold in the
system becomes a defended operating point, and the decision the heuristics
cannot make gets a trained, calibrated model — evaluated honestly enough that
"it did not help" is a publishable result.

**Opened:** 2026-08-20 · **Release target:** 0.3.0 · **Gate:** Sprint Review

| Lens | Position |
|---|---|
| Product stage | **MVP** |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| **AIDLC** | **2** Knowledge curation · **4** Retrieval & grounding · **5** Evaluation design |
| Agile | Sprint 3 of 9 |

---

## Why this sprint exists

The Product Owner observed that after three sprints the system contained no
trained model and no statistical rigour. Every threshold in it had been set from
the minimum and maximum of a 20-question set.

That is a reasonable way to start and it is not evidence that any threshold is
correct. Two of those thresholds have already been shown wrong by measurement
(the cache constant of 0.86; the bare digit match for stated values), which is
the argument for doing this properly rather than the argument against it.

It runs **before** the orchestrator so that the calibrated operating points and
the classifier exist before the graph is built around them.

## Sprint backlog

| ID | Story | Role | Pts | AIDLC | FR |
|---|---|---|---|---|---|
| **S3-DATA** | Question generator: ~600 examples, labels true by construction, document-level splits | DEV | 8 | 2 | FR-026 |
| **S3-STATS** | ROC and PR curves, Youden's J operating point, bootstrap CIs, McNemar between configurations, power analysis | DEV | 8 | 5 | FR-027 |
| **S3-MODEL** | Feature extraction, logistic-regression baseline, gradient-boosted challenger, probability calibration, model card | DEV | 8 | 5 | FR-028 |
| **S3-RERANK** | Cross-encoder fine-tuned in PyTorch, ONNX export, parity test, latency budget | DEV | 8 | 4 | FR-029 |
| **S3-ANN** | pgvector HNSW vs IVFFlat vs exact vs managed vector store: recall@k, latency percentiles, build time, memory | DEV | 5 | 4 | FR-030 |
| **S1-09** | Seed loader (carried) | DEV | 3 | 2 | — |

**Committed: 40 points.** Demonstrated velocity: 41, 36.

## Definition of Done additions

- **No label is assigned by a model** (ADR-0010). A test asserts the generation
  path makes no model call.
- **Every split is by document, not by question.** A test asserts no document
  appears in both train and test.
- **Every reported metric carries an interval.** A point estimate from a single
  split is not a result.
- **A negative result ships.** If the trained classifier does not beat the
  heuristic, that is written up and the heuristic stays. The sprint is not
  considered failed; a model adopted without evidence would be the failure.
- **ONNX output is asserted equal to PyTorch output** within tolerance on a
  fixed sample (ADR-0009). Otherwise "deployed" and "the trained model is
  deployed" are different claims that look identical.

## Explicitly out of scope

Any model in the request path that has not been measured against the baseline it
replaces. Any use of an LLM to produce ground truth. Retraining in CI — CI
verifies artefact checksums, it does not train.

## Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted |
| IMP-04 | No managed Postgres or Redis credentials | **OPEN** — blocks S1-09 and S3-ANN's pgvector arm |
