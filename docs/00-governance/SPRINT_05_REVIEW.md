# Sprint 5 — Review & Retrospective

**Sprint:** 5 — Console · **Closed:** 2026-08-20 · **Release:** 0.5.0 · **Gate:** UAT

---

## 1. Sprint goal

> Make it watchable. A visitor triggers a triage run and sees the agent reason,
> retrieve, cite, refuse and stop for approval as it happens.

**Met.** All six stories plus a smoke layer that was not in the plan and should
have been in Sprint 1.

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S5-API | FastAPI surface | 5 | Bearer auth, constant-time compare, fail-fast on bad config |
| S5-BFF | Next.js BFF | 8 | SSE proxy, fail-closed rate limiting, CSP, no token in the browser |
| S5-STREAM | Live triage | 8 | Node events, citations, refusals streaming as they happen |
| S5-TRACE | Trace waterfall | 8 | Per-node spans and the spend ledger |
| S5-APPROVE | Approval gate | 5 | Decision opens a continuation; the gated run is never resumed |
| S5-MEM | Session memory | 5 | Salted-hash identity, capped newest-first recall |
| S5-SMOKE | Assembled-system test | — | **Unplanned.** DoD item 7, four sprints late |

**447 tests.** Smoke 8/8. 14 approval and memory tests verified against Neon.

## 3. What running it actually found

Six defects, all in one sprint, none by review:

| | |
|---|---|
| **D-005** | The retry loop re-sent an identical prompt and could never succeed |
| **D-006** | The semantic cache served the previous answer to a correction retry (0.886 vs a 0.60 threshold) |
| **D-007** | `RUN_BUDGET_USD=0` killed every run mid-stream |
| **D-008** | The CSP blocked React hydration in development; every button was inert HTML |
| **D-009** | The console displayed assessments the governance layer had refused to emit |
| **D-010** | The spend reservation under-reserved 4x when failover reached a costlier provider |

**D-006 is the one that could not have been found any other way.** Both
components had correct tests. The cache's asks whether two different *questions*
collide — 0.208, correctly no. Nobody asks whether a prompt collides with its
own *correction* until the two are wired together and run.

**D-010 was found by reading a trace the product renders about itself**, a
category of finding that did not exist before this sprint.

## 4. Measured

| | |
|---|---|
| Deterministic nodes | 7 spans, **25.4 ms combined** |
| Total run | 41 s |
| Cost per run | $0.0005 – $0.0012 |
| Reservation vs actual | **1.50x** — bounded, not wildly over-reserved |

The governance layer is essentially free and the model calls are everything.
That is the argument for deciding as much as possible with typed rules, stated
as a number rather than a preference.

## 5. Retrospective

**What worked.** The Sprint 4 improvements were binding rather than advisory,
and asserting an anchor before a text replacement caught **four** silent no-ops
this sprint. Each would have reported success.

Writing acceptance criteria before the console existed meant acceptance is
judged against criteria rather than against whatever got built.

**What did not.** The QA role had a Definition of Done item — *demonstrable, not
described* — written at Sprint 0 and enforced zero times across five reviews.
Its own test strategy scheduled end-to-end for "Pre-release", deferring the only
layer that exercises the assembled system to Sprint 8. Four sprints and 412
passing tests produced a system that had never once been run, and the first
execution found three defects in ten minutes.

`TEST_PLAN.md` and `DEFECT_LOG.md` were named as QA deliverables at Sprint 0.
The defect log was created in Sprint 5, with three defects already found, fixed
and written up without ever being logged as defects.

**Also.** Two intermediate runs *looked* like a fix had landed when it had not —
they completed because the model happened to cite well, not because the retry
path executed. Live runs are good at finding bugs and bad at proving fixes.

**Improvements committed for Sprint 6.**
1. A fix is not confirmed by a live run. It is confirmed by a deterministic test
   that fails without it.
2. Any role that produces no artifact for two consecutive sprints is raised at
   the sprint review as an impediment rather than noticed later.

## 6. Gate

**UAT** — pending Product Owner, against the 12 criteria in
`ACCEPTANCE_CRITERIA_CONSOLE.md`.
