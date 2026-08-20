# Sprint 4 — Agent Core II

**Sprint goal:** One orchestration graph runs two workloads under governance. A
risky action cannot execute without a human decision, and no model call can
happen without a budget open first.

**Opened:** 2026-08-20 · **Release target:** 0.4.0 · **Gate:** Sprint Review

| Lens | Position |
|---|---|
| Product stage | **MVP** |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| **AIDLC** | **3** Context & task engineering · **5** Evaluation · **6** Guardrails & governance |
| Agile | Sprint 4 of 9 |

---

## Sprint backlog

| ID | Story | Role | Pts | AIDLC | FR |
|---|---|---|---|---|---|
| **S4-WORKLOAD** | Workload abstraction: incident triage and change review on ONE graph | DEV | 5 | 3 | FR-025 |
| **S4-GRAPH** | LangGraph orchestrator; `await_approval` terminal by construction | DEV | 8 | 3 | FR-004, FR-007 |
| **S4-ADJUDICATE** | Grounding adjudicator for the ambiguous band, one cheap model call | DEV | 5 | 6 | FR-006 |
| **S4-CITE** | Citation extraction and the uncited-claim verify loop | DEV | 5 | 6 | FR-005 |
| **S4-SPEND** | Spend guard at the single chokepoint, priced pre-flight, ledgered after | DEV | 5 | 6 | FR-014 |
| **S4-EVAL** | Eval harness: `golden/core` blocking, `golden/probe` warning | DEV | 8 | 5 | FR-015, FR-016 |

**Committed: 36 points.** Demonstrated velocity: 41, 36, 40.

## Definition of Done additions

Carried forward from the Sprint 3 retrospective, all three binding:

- **A behavioural change is not complete until a test or a measurement
  demonstrates the new behaviour.** "The edit succeeded" is not evidence.
- **A text-replacement fix asserts its anchor exists before writing.** Three
  edits silently no-opped in Sprint 3 and each reported success.
- **A metric is reported at every level the component has**, or the omission is
  justified in writing. Document-level MRR was saturated at 0.986 while chunk
  level sat at 0.528, and reading only the first produced a false conclusion.

Plus, specific to this sprint:

- **`await_approval` has no outgoing edge.** Asserted by enumerating the compiled
  graph's edges, not by reading the builder (ADR-0006).
- **No live model call may execute without an open budget.** Asserted by a test
  that opens none and expects a refusal (ADR-0007).
- **Both workloads must run the same compiled graph object.** A second graph
  would be easier and would prove nothing about the control plane being
  workload-agnostic.

## Explicitly out of scope

Wiring the cross-encoder re-ranker into the request path. Its benefit is
unestablished (paired CI includes zero) and an unestablished benefit does not get
to add latency to every query. Revisit above 200 gold-chunk examples per arm.

## Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted; HF build is the container integration test |
| IMP-04 | Managed Postgres and Redis | **CLOSED** — Neon and Upstash live |
| IMP-05 | Upstash Vector index not provisioned | Open; blocks only the managed-store arm of the ANN benchmark |
