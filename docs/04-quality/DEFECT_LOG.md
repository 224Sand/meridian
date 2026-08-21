# Defect Log

**Owner:** QA Lead · **Opened:** 2026-08-20 (Sprint 5)

> Named as a QA Lead deliverable in the charter at Sprint 0 and **not created
> until Sprint 5**. Three defects had already been found, fixed and written up
> in postmortems without ever being logged as defects. Backfilled below rather
> than started clean, because a log that begins the day it is noticed hides the
> period it was missing.

| ID | Found | Sprint | Severity | Description | Root cause class | Status |
|---|---|---|---|---|---|---|
| D-001 | Sprint 3 | 2 | **1** | Refusal gate marked 150/265 unanswerable questions answerable — a 56.6% false-answer rate reported at the Sprint 2 gate as zero | Test set too small and too easy, written by the implementer | Fixed, guarded |
| D-002 | Sprint 3 | 3 | 2 | Evidence gate answered a value-demanding question the corpus never answers, scoring 8.85 | Similarity signals cannot distinguish "about this subject" from "answers this question" | Fixed, guarded |
| D-003 | Sprint 3 | 3 | 3 | Re-ranker experiment returned a null result that was two bugs: a NaN checkpoint and a saturated metric | NaN sorts as a no-op; document-level MRR was already 0.986 | Fixed, guarded |
| D-004 | Sprint 4 | 1 | 2 | Seed loader destroyed one embedding model's vectors when reloading under another | `chunk_embedding` cascades on chunk delete | Fixed, guarded |
| D-005 | Sprint 5 | 4 | 2 | Retry loop re-sent an identical prompt, so it could never succeed | Design oversight: the edge existed, the feedback did not | Fixed, guarded |
| D-006 | Sprint 5 | 4 | **1** | Semantic cache served the previous answer to a correction retry (0.886 similarity vs 0.60 threshold) | **Emergent interaction between two individually correct, individually measured components** | Fixed, guarded |
| D-007 | Sprint 5 | 4 | 2 | `RUN_BUDGET_USD=0` killed every run mid-stream with an unhandled error | Fail-fast not applied to configuration | Fixed, guarded |
| D-008 | Sprint 5 | 5 | 2 | CSP blocked React hydration in development; every button was inert HTML | A policy correct for production made development impossible | Fixed, guarded |
| D-009 | Sprint 5 | 5 | **1** | The console displayed assessments the governance layer had refused to emit | Rendering ignored the run outcome | Fixed, guarded |
| D-010 | Sprint 5 | 4 | **1** | Spend reservation priced against `providers[0]`, under-reserving 4x when failover reached a costlier provider | The guard assumed the cheapest candidate would serve | Fixed, guarded |
| D-011 | Sprint 6 | 6 | 3 | A comment inside a backslash continuation truncated the Semgrep invocation; the scan ran without its exclusion, printed success, and the shell exited 127 on the orphaned flag | Shell semantics: a comment ends a continuation. Every visible signal pointed elsewhere | Fixed, guarded |

## Where these were found, which is the finding

| Found by | Count |
|---|---|
| Running the assembled system | **5** (D-005, D-006, D-007, D-008, D-009) |
| Measuring against a large labelled set | 2 (D-001, D-002) |
| CI against a real database | 1 (D-004) |
| Re-running a measurement after a change | 1 (D-003) |
| Reading a trace the product renders about itself | 1 (D-010) |
| CI reporting a failure whose visible cause was wrong | 1 (D-011) |
| **Code review** | **0** |
| **Unit tests written before the defect** | **0** |

Not one of these was caught by review or by the existing test suite. Every one
was caught by executing something — the system, a measurement, or a container.

D-006 is the one that could not have been caught any other way. Both components
had correct tests. The cache's test asks whether two different *questions*
collide (0.208, correctly no). Nobody asks whether a prompt collides with its
own *correction* (0.886, yes) until the two are wired together and run.

## Policy

A defect is logged here when found, before it is fixed, with its root cause
class. A defect that reaches a deployed environment additionally gets a
postmortem in `docs/06-operations/postmortems/`.

## D-011 in detail — when every visible signal points the wrong way

**Found:** 2026-08-21, CI (Security workflow), after the fix for D-010's sibling failures.
**Severity:** Medium — the gate reported failure, but for a reason that pointed nowhere.

**What happened.** Excluding a Semgrep rule meant adding a `--exclude-rule` flag to a
backslash-continued `semgrep scan` invocation. The justification was written as comment
lines directly above the new flag, inside the continuation. Bash ends a continuation at a
comment, so the shell ran `semgrep scan` *without* the new flag, printed a complete and
entirely plausible scan report, and then tried to execute
`--exclude-rule=trailofbits...` as a program:

    line 21: --exclude-rule=trailofbits...: not found
    ##[error]Process completed with exit code 127

**Why it cost a round trip.** Every visible signal was misleading. Semgrep printed
`Scan completed successfully`, the finding it was supposed to suppress still appeared, and
the exit code (127) belongs to the shell, not to the scanner. The obvious reading — "the
exclusion flag doesn't work" — was wrong; the flag was never passed.

**Fix.** Moved all commentary above the invocation so the continued flags are contiguous.

**Guard.** `scripts/check-workflow-shell.mjs`, run in CI's governance job, parses every
`run:` block in `.github/workflows` and fails on (a) a comment line following a line ending
in `\`, and (b) any block that fails `bash -n`. It was verified against the broken file
before being trusted: it reports `security.yml:129`, the exact line that produced the 127.

**Class.** Same family as the silent no-op string replacements logged earlier: an edit that
appears to have applied, produces confident output, and changes nothing. The standing
response is unchanged — assert the anchor before writing, and prove the guard fails on the
bug it claims to catch.
