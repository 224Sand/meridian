# Sprint 0 — Review & Retrospective

**Sprint:** 0 — Inception · **Closed:** 2026-08-20 · **Scrum Master:** SM

---

## 1. Sprint goal

> Produce a signed-off, traceable requirements and architecture baseline, and a
> repository whose CI pipeline is green before any product code exists.

**Met.** All three governance gates pass. 52 requirements are declared, traced
to a story and a named test, and mapped to a sprint.

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S0-01 | Governance | 3 | `WAYS_OF_WORKING.md` — 12 delivery roles, 5 stakeholder roles, 7-item DoD, 9-risk register |
| S0-02 | Business requirements | 5 | `BRD.md` — 11 business requirements, 15 constraints, 4 personas |
| S0-03 | Product definition | 5 | `PRD.md` — 23 features, user stories, success metrics, release plan |
| S0-04 | Architecture baseline | 8 | `TECH_SPEC.md` — C4 views, data model, contract, 8 failure modes |
| S0-05 | Decision records | 3 | ADR-0001 … ADR-0007 |
| S0-06 | Name as configuration | 2 | `product.config.json` + `rename.mjs`, round-trip verified |
| S0-07 | Test strategy | 3 | `TEST_STRATEGY.md` — 13 named regression tests, two golden suites |
| S0-08 | Threat model | 3 | `THREAT_MODEL.md` — STRIDE, 11 threats |
| S0-09 | Repo & CI | 5 | 3 blocking gates, CI workflow, secret scanning |
| S0-10 | Traceability | 3 | 52 requirements, zero orphans |

**Velocity: 40 / 40 points committed and completed.**

## 3. Demonstrated, not described

- `check-docs.mjs` was written **before** the documents it governs and observed
  failing with 22 errors. It now passes with 52 requirements traced.
- `rename.mjs` was executed against a live copy: `MERIDIAN → VANTAGE → MERIDIAN`,
  with schema validation passing at each step.
- `check-secrets.mjs` scans its own tree; it is constructed so that it cannot
  match its own source, because a gate that trips on itself teaches people to
  bypass gates.

## 4. Retrospective

**What worked.** Writing the quality gate before the artifact produced a real
red-to-green transition rather than a claim of one. The single-source-of-truth
name config took under an hour and removed an entire category of future churn.
Carrying forward specific prior failures — the approval node that controlled
nothing, the refusal check reading a score that measured nothing — meant the ADRs
document decisions with evidence behind them rather than preferences.

**What did not.** `check-docs.mjs` was written to read requirement declarations
from the charter alone. The moment the BA and PM introduced 36 new IDs, the gate
would have called them orphans. The gate was too narrow because it was written
against the only document that existed at the time.

**Improvement committed for Sprint 1.** When a gate encodes an assumption about
which documents exist, that assumption gets stated in a comment at the point of
the assumption. The widened `DECLARING_DOCS` list now carries exactly that
comment.

## 5. Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | Docker unavailable on host | Accepted. Native `uvicorn` dev loop; HF build is the container integration test (R-07, TECH_SPEC §9) |
| IMP-02 | Product name undecided | Neutralised by S0-06. Rename is one command; no longer blocks any sprint |
| IMP-03 | `npm` workspaces glob pointed at empty directories | Resolved — field removed, returns in Sprint 3 with `apps/web` |

## 6. Gate

**Requirements Sign-off** — pending Product Owner. Sprint 1 does not open until
it is granted.
