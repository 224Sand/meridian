# Sprint 7 — Proof Surfaces

**Sprint goal:** Publish what the system gets wrong, in a form a stranger can
check. The claim "this is production-grade" is worthless from the person who
built it; the evidence has to be inspectable without taking anyone's word.

**Opened:** 2026-08-21 · **Release target:** 0.7.0 · **Gate:** UAT

> **Backfilled**, like Sprint 6, and for the same reason. See D-016.

## Why this sprint exists

Everything measured so far — error rates, model AUC, the defect distribution —
lives in JSON files and markdown nobody outside the repository will read. A
reviewer spends minutes, not hours. If the evidence is not on a surface, it does
not exist.

The governing constraint, carried from `/delivery`: **no number on these pages is
typed by a human.** A hand-written figure is a claim that drifts the moment the
underlying value moves, and the entire argument of these surfaces is that their
numbers can be checked.

## Sprint backlog

| ID | Story | Pts | Acceptance |
|---|---|---|---|
| S7-REL | `/reliability` — measured error rates against their budgets | 8 | Every figure derived; intervals shown, not just point estimates |
| S7-WEAK | Publish the checks that are currently FAILING | 5 | The probe suite renders as a first-class section, not a footnote |
| S7-ARCH | `/architecture` — request path and all ADRs | 5 | Diagram drawn from the real path; ADR list parsed, not transcribed |
| S7-DERIVE | `derive-surfaces.mjs` — one source for both pages | 5 | Fails the build rather than emitting a page with a blank |
| S7-MOBILE | Both surfaces usable on a phone | 3 | No page-level horizontal overflow at 390px |
| S7-GOV | A sprint number cannot precede its plan | 3 | Enforced in CI (Sprint 6 improvement 1) |

**Committed: 29 points.**

## Definition of Done additions

9. A guard is not trusted until it has been run against the defect it claims to
   catch and observed to **fail**.

## Explicitly out of scope

Deployment. The manifests may be written and tested, but publishing to Hugging
Face and Vercel is Sprint 8 and needs credentials this sprint does not hold.

## Impediments

### IMP-08 — the evidence is unflattering

`/reliability` publishes a false-answer interval that crosses its own budget and
three checks that fail on every push. The temptation to show only the point
estimate is real and was resolved against: the interval is the honest statement,
and a reviewer who spots a hidden one stops believing everything else.
