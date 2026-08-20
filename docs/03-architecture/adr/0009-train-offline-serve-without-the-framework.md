# ADR-0009 — Models are trained offline and served without their training framework

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect
**Relates to:** ADR-0003 (HF Spaces), ADR-0004 (no local neural embedding model)

## Context

Sprint 3 introduces trained models. ADR-0004 excluded `torch` from the runtime
image because it is 2–3 GB, which breaks build times on the free tier and
violates NFR-002. That reasoning still holds and is not being reversed.

But ADR-0004 was about the **runtime image**, and it was quietly read as
"no machine learning in this project" — which is not what it says, and is a
worse constraint than the one that was actually decided. Training does not
happen in the serving container.

## Decision

Training runs offline, on a development machine, with whatever framework suits
the model. Serving runs in the container with the smallest artefact that
reproduces the trained behaviour.

| Model | Trained with | Served with | Runtime cost |
|---|---|---|---|
| Evidence-sufficiency classifier | scikit-learn | Exported coefficients / a small pickled estimator | negligible |
| Cross-encoder re-ranker | PyTorch | ONNX Runtime | ~50 MB |
| Telemetry anomaly detector (if built) | TensorFlow or scikit-learn | ONNX Runtime | shared |

Every trained artefact is versioned, checksummed, and accompanied by the
evaluation that justified shipping it. A model in the repository without its
evaluation is not deployable.

## Consequences

**Positive.** The runtime image stays small and ADR-0003's constraints hold. The
split is the standard production pattern rather than a workaround, so it
survives scrutiny. Training frameworks never become a deployment dependency, and
a framework can be swapped without touching the serving path.

**Negative.** An export step exists between training and serving, and export is
where numerical behaviour can silently change. A test asserts that the ONNX
output matches the PyTorch output within tolerance on a fixed sample; without
it, "the model is deployed" and "the trained model is deployed" are different
claims that look identical.

**Also negative.** Training is not reproducible in CI, because CI will not carry
the training frameworks. Training scripts pin their seeds and record their
environment, and the artefact's checksum is what CI verifies.
