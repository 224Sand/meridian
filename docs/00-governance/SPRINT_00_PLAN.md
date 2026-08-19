# Sprint 0 — Inception

**Sprint goal:** Produce a signed-off, traceable requirements and architecture
baseline, and a repository whose CI pipeline is green before any product code
exists.

**Opened:** 2026-08-20 · **Scrum Master:** SM · **Gate:** Requirements Sign-off (Product Owner)
**Gate depth elected by PO:** FULL ARTIFACT REVIEW

---

## Sprint backlog

| ID | Story | Role | Pts | DoR | Status |
|---|---|---|---|---|---|
| **S0-01** | As the delivery team, we need governance so every task has an owner and a gate | TPM | 3 | ✅ | ✅ Done |
| **S0-02** | As the PO, I need business requirements captured so scope is unambiguous | BA | 5 | ✅ | ⬜ |
| **S0-03** | As the PO, I need a product definition so we build the right thing | PM | 5 | ✅ | ⬜ |
| **S0-04** | As the team, we need an architecture baseline so implementation has a target | Architect | 8 | ✅ | ⬜ |
| **S0-05** | As the team, we need decisions recorded immutably so reversals are visible | Architect | 3 | ✅ | ⬜ |
| **S0-06** | As the PO, I need the product name to be changeable without a refactor (FR-001) | Architect | 2 | ✅ | ⬜ |
| **S0-07** | As QA, I need a test strategy so Definition of Done is enforceable | QA Lead | 3 | ✅ | ⬜ |
| **S0-08** | As Security, I need a threat model so abuse controls are designed, not bolted on | Security | 3 | ✅ | ⬜ |
| **S0-09** | As the team, we need a repo with green CI so quality gates exist from commit one | DevOps | 5 | ✅ | ⬜ |
| **S0-10** | As the PO, I need every requirement traced to a story and a test | BA | 3 | ✅ | ⬜ |

**Committed:** 40 points.

## Out of scope for Sprint 0

Any product source code. Any deployment. Any LLM call. Sprint 0 produces
documents, repository scaffolding, and pipeline configuration only.

## Capacity note

Cadence is work-session based per the charter (§4). Burndown for this sprint is
derived from real commit timestamps in `.github/` history, not from estimates.

## Impediments

| ID | Impediment | Raised by | Status |
|---|---|---|---|
| IMP-01 | Docker unavailable on host — container cannot be validated locally | DevOps | Accepted, mitigated (R-07) |
| IMP-02 | Product name undecided — blocks branding assets, not code | PO | Mitigated by S0-06 |
