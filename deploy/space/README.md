---
title: SandScope Agent Runtime
emoji: 🛰️
colorFrom: gray
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Evidence-gated agent runtime with deterministic provider failover
---

# SandScope — agent runtime

The FastAPI service behind [SandScope](https://sandscope.vercel.app). The web
console calls it; this Space is the runtime that actually executes runs.

## What it does

An incident-intelligence agent over a fixed corpus of architecture, policy and
change-management documents. Given a question it retrieves evidence, decides
whether the evidence is sufficient to answer at all, and either answers with
citations or declines.

The part worth looking at is the declining.

## Evidence gate

Retrieval returns a score; the score maps to one of three bands:

| Band | Behaviour |
|---|---|
| `SUFFICIENT` | answer, every claim cited |
| `AMBIGUOUS` | answer, flagged as partial |
| `INSUFFICIENT` | refuse — no draft is emitted |

The two thresholds are not taste. They are derived from stated error budgets —
2% false refusals, 5% false answers — measured over a labelled question set.
An earlier build reported a 0% false-answer rate on 22 questions; the real rate
on 534 was 56.6%. Deriving the bands from budgets rather than from a good-looking
sample took it to 3.8%.

## Provider failover

Groq → Gemini → Cerebras → OpenRouter → Mistral, in that fixed order. A provider
that rate-limits is disabled for a bounded interval, not for the process
lifetime, and the clock is injected so the expiry is tested rather than waited
on. Every completion goes through one chokepoint that reserves spend against the
worst-case surviving provider before the call, so a run cannot exceed its budget
by racing.

## Endpoints

| Method | Path | Auth |
|---|---|---|
| `GET` | `/healthz` | none |
| `GET` | `/v1/providers` | bearer |
| `GET` | `/v1/workloads` | bearer |
| `POST` | `/v1/runs/stream` | bearer — SSE |
| `GET` | `/v1/runs/{id}/approval` | bearer |
| `POST` | `/v1/runs/{id}/approve` | bearer |
| `GET` | `/v1/sessions/{id}/memory` | bearer |

`/healthz` is deliberately unauthenticated so liveness can be probed without a
token. Everything else requires `Authorization: Bearer <AGENT_SERVICE_TOKEN>`.

## Configuration

Set as Space secrets — never baked into the image:

`DATABASE_URL` · `AGENT_SERVICE_TOKEN` · `GROQ_API_KEY` · `GEMINI_API_KEY` ·
`UPSTASH_REDIS_REST_URL` · `UPSTASH_REDIS_REST_TOKEN` · `UPSTASH_VECTOR_REST_URL` ·
`UPSTASH_VECTOR_REST_TOKEN` · `RUN_BUDGET_USD`

`RUN_BUDGET_USD` fails fast at startup if set to 0 — a zero budget used to kill
runs mid-stream instead of refusing to boot.

## Runtime closure

Serving installs ONLY the runtime dependencies. Training frameworks (torch,
transformers, scikit-learn) are excluded by design: models are trained offline
and shipped as ONNX, so inference needs onnxruntime and a Rust tokenizer rather
than 2-3GB of framework. That decision is ADR-0009, and it turned out to be a
security boundary too — the training extra carries 4 known RCE advisories, and
the runtime closure audits clean.
