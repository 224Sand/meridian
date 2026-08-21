# Sprint 6 — Review & Retrospective

**Sprint:** 6 — Experience · **Closed:** 2026-08-21 · **Release:** 0.6.0 ·
**Gate:** Design Review + UAT

> **Backfilled**, with the plan. See the note in `SPRINT_06_PLAN.md`.

## 1. Sprint goal

**Met.** The landing surface leads with the refusal claim rather than with the
author, and the console is one click from it. The video budget held.

## 2. Delivered

All six stories. 28 points committed, 28 delivered.

| Asset | Budget | Actual |
|---|---|---|
| Hero video | 2.5 MB | **0.90 MB** |
| Hero poster | — | 78 KB |
| Clip length | 4 s | 4 s |

Attribution for the single stock clip (Pexels 7140928, MrColo) is committed in
`public/media/CREDITS.json` alongside the byte counts, and
`scripts/fetch-media.mjs` re-derives both files from the Pexels id, so the assets
are reproducible rather than pasted in.

`ScrollScrubbed` performs **one seek per animation frame**. The obvious
implementation seeks on every scroll event, which on a trackpad fires far faster
than the decoder can serve and degrades into stutter under exactly the conditions
a reviewer will use.

## 3. What running it actually found

**D-008 — the CSP blocked React hydration in development.** Every button on the
page was inert HTML. A policy that is correct in production made development
impossible, and it presented as a styling bug rather than a security one. The
policy is environment-aware now.

Nothing else in this sprint was found by running it, which is itself worth
noting: this was the first sprint whose output is judged by looking rather than
by executing, and the defect it produced was the one that *could* be executed.

## 4. Measured

- Video 0.90MB / 2.5MB budget; poster 78KB
- Below 768px or under reduced motion the poster **replaces** the video — the
  element is not merely paused, so no bytes are spent to show a still
- No content on any surface is reachable only by animating

## 5. Retrospective

**What worked.** Treating the budget as fixed and the asset as variable. Had the
clip been chosen first, every later decision would have been an argument for
relaxing the ceiling.

**What did not — and this is the finding of the sprint.** *The sprint was never
opened.* No planning ceremony ran, no plan document existed, and the work shipped
under a sprint number that appeared only in defect-log entries. The charter names
Sprint Planning as the ceremony that opens a sprint and the TPM as its owner; the
role produced no artifact for two consecutive sprints and nothing raised it —
even though the Sprint 5 retrospective had committed, in writing, to raising
exactly that as an impediment. **A commitment recorded in a retrospective and
then not honoured is worse than one never made**, because it consumed the
attention that would have gone to a real control.

That is the second time this project has produced a claim with no artifact behind
it. The first was the traceability matrix (D-014). Both were caught only when
someone looked directly at them.

**Improvements committed for Sprint 7.**
1. A sprint number may not appear in any artifact — defect log included — before
   `SPRINT_NN_PLAN.md` exists. **Enforced by `scripts/check-sprints.mjs` in CI,
   not by intent.** The Sprint 5 commitment failed precisely because it relied on
   someone remembering.
2. The Sprint 5 improvement stands and is restated: a fix is confirmed by a
   deterministic test that fails without it, never by a live run that looks right.

## 6. Gate

**Design Review + UAT** — pending Product Owner. The design criteria are the two
Definition of Done additions above; the UAT criteria remain the twelve in
`ACCEPTANCE_CRITERIA_CONSOLE.md`.
