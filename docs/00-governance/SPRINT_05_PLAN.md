# Sprint 5 — Console

**Sprint goal:** Make it watchable. A visitor triggers a triage run and sees the
agent reason, retrieve, cite, refuse and stop for approval as it happens — with
the full execution trace inspectable afterwards.

**Opened:** 2026-08-20 · **Release target:** 0.5.0 · **Gate:** **UAT** (first user-facing gate)

| Lens | Position |
|---|---|
| Product stage | **MVP** |
| SDLC | Implementation, Testing |
| PDLC | Development, UAT |
| **AIDLC** | **8** Observability & continuous evaluation |
| Agile | Sprint 5 of 9 |

---

## Why this sprint changes what the product is

Four sprints have produced a well-tested Python library: 412 tests, a governed
orchestrator, a trained classifier, measured thresholds. None of it can be
watched. Every claim so far is verified by reading a test.

This sprint is the first where a person can form their own judgement.

## Sprint backlog

| ID | Story | Role | Pts | FR |
|---|---|---|---|---|
| **S5-BFF** | Next.js 16 on Vercel; SSE proxy; per-IP rate limit via Redis, failing closed | DEV + DevOps | 8 | NFR-004 |
| **S5-API** | FastAPI surface on the agent runtime; bearer auth, constant-time compare | DEV | 5 | AC-001 |
| **S5-STREAM** | Live triage: node events, retrieval hits, citations, refusals as they happen | DEV | 8 | FR-004 |
| **S5-TRACE** | OpenTelemetry spans across both runtimes, rendered as a waterfall | DEV | 8 | FR-013, BR-005 |
| **S5-APPROVE** | Approval gate as UI; decision creates the continuation run | DEV | 5 | FR-007 |
| **S5-MEM** | Session memory panel: what was written, what was recalled | DEV | 5 | FR-008 |

**Committed: 39 points.** Demonstrated velocity: 41, 36, 40, 36.

## Definition of Done additions

Carried from Sprint 4's retrospective:

- **A test asserts one thing, and reaches the gate its name promises.** A test
  named for the risk gate that is actually stopped by the evidence gate is a
  test that has been silently repurposed without failing.

Specific to this sprint:

- **The browser never holds the inter-service token.** Asserted by a test that
  greps the client bundle.
- **Rate limiting fails CLOSED.** A test simulates an unreachable Redis and
  asserts the request is denied, not allowed (ADR-0007).
- **A trace must cross both runtimes.** A span tree containing only Python spans
  means `traceparent` propagation is broken, and the waterfall would look
  correct while showing half the request.
- **No secret reaches a trace attribute.** Asserted on the span exporter.

## Explicitly out of scope

The visual design surface. This sprint makes the console *work*; Sprint 6 makes
it look like the reference standard (DR-001). Building both at once produces a
half-finished version of each, which R-05 exists to prevent.

## Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted; the HF build is the container integration test |
| IMP-06 | Data stores are in three regions, none of them the one the agent will run in | **OPEN** — see below |

### IMP-06 — regional placement

Measured round trips from the development machine:

| Store | Region | Client p50 | Server p50 |
|---|---|---|---|
| Neon Postgres | `ap-southeast-1` | 52.2 ms | 0.06 ms |
| Upstash Redis | `ap-south-1` | 106.6 ms | — |
| Upstash Vector | `eu-west-1` | 519.4 ms | — |

These numbers are from India and are **not** the ones that matter. In production
the only client is the agent runtime on Hugging Face Spaces, so the latency that
counts is HF → each store, not laptop → each store.

Decision needed before Sprint 8 deployment, not before this sprint.
