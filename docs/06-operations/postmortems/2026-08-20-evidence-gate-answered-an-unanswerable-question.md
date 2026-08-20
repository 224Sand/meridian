# Postmortem — the evidence gate would have answered an unanswerable question

**Date:** 2026-08-20 · **Sprint:** 2 · **Severity:** would have been 1 in production
**Status:** Fixed, with a regression test · **Author:** QA Lead

> This is a real defect found during this build, not an illustration. It is
> published because `/delivery` renders our own defects, and a delivery record
> that only contains successes is not evidence of anything.

## Summary

Expanding the retrieval corpus from 60 to 87 chunks caused the evidence gate to
classify a genuinely unanswerable question as **SUFFICIENT**. In a running
system the agent would have answered it, confidently and with citations, from
material that does not contain the answer.

The defect was caught by re-running the measurement after the corpus changed. No
test failed. No error was raised. The gate reported normal operation throughout.

## Impact

None reached a user; the system is not deployed. Had it shipped, the failure
mode is the exact one this product exists to prevent: a confident, well-cited,
wrong answer.

## What happened

The corpus was expanded with change-management documents. Re-measuring the
evidence gate afterwards showed:

```
how long is the observation period between regions   ->  8.85  SUFFICIENT
```

8.85 is nearly three times the sufficiency threshold. The corpus states that an
observation period exists between regional rollout steps, explains why it
exists, and **never states its duration**. Every term in the question is present
in the retrieved text. Both retrieval signals and term coverage all read as a
strong match.

## Root cause

Every signal the gate used was a **similarity** signal, and similarity cannot
distinguish "this material answers the question" from "this material is about
the same subject as the question".

The original ten unanswerable test questions were all *vocabulary-absent* cases
— disk exhaustion, DNS, Kubernetes — where the corpus contains none of the
relevant words. Those are easy, and they made the gate look sound. The expansion
introduced the *vocabulary-present, answer-absent* class, which similarity
scores cannot see at all.

This is the same shape as the defect recorded in ADR-0004's lineage: a refusal
check reading a signal that does not vary between the classes it is supposed to
separate.

## Contributing factor: a fix that was reported and not applied

The first attempt at the fix was applied by string replacement against the
source file. `ruff format` had already rewrapped the target call across multiple
lines, so the replacement matched nothing. The script printed a success message.
The constant and the helper function landed; **the call site did not**, leaving
`_contains_a_value` defined and never called.

Re-running the measurement is what surfaced it. Nothing else would have: the
code compiled, the linter passed, the type checker passed, and every existing
test passed.

## Contributing factor: an incorrect entry in the gap list

`GAPS.md` listed "who approves an emergency change during an incident" as
unanswerable. The corpus states that emergency changes are governed by the
incident commander, which answers it. The gate was right and the gap list was
wrong. The entry has been removed and the correction is recorded in the file
rather than deleted silently, because a gap list is itself a claim about the
corpus.

## Fix

A **value-demand discriminator**. Where a question asks for a specific quantity
and the retrieved evidence states no quantity, the verdict is downgraded from
SUFFICIENT to **AMBIGUOUS** — routing it to adjudication rather than answering it.

The downgrade goes to AMBIGUOUS and never to INSUFFICIENT. The check is a
heuristic about the shape of a question, and a heuristic is not entitled to
refuse on its own authority.

The first implementation of the value detector was a bare `\d` match. It matched
"Tier 0" and "Severity 1" — labels, not measurements — which appear throughout
this corpus, so it reported a value present in effectively every chunk and
caught nothing. It now requires a number carrying a unit, or a multi-digit
figure. A test asserts that tier and severity labels do not qualify.

## Corrective actions

1. Value-demand discriminator, with the downgrade to AMBIGUOUS. **Done.**
2. Both value-demanding unanswerable questions added to the permanent question
   set. **Done.**
3. Test asserting tier and severity labels are not read as stated values. **Done.**
4. `GAPS.md` corrected, with the correction left visible. **Done.**
5. The deterministic-resolution ratio is now asserted as a ratio with a recorded
   history (14/20 → 13/20 → 13/22) rather than a fixed count, so that drift is
   visible instead of being absorbed by editing the number. **Done.**

## What we are deliberately not doing

**Not raising the sufficiency threshold.** Raising it until this question fell
below the band would have suppressed one symptom and refused legitimate
questions across the corpus. The problem was never the threshold's position; it
was that the signals underneath it cannot see this class of failure.

**Not claiming this class is now solved.** The discriminator catches questions
that ask for a quantity. A question asking for a procedure the corpus discusses
but never specifies would still score highly and would still not be caught by
any similarity signal. That case routes to adjudication in Sprint 3 and belongs
in the probe suite, which is expected to warn on every run rather than be tuned
until it stops.

## Lesson

Test sets assembled from the easy version of a failure make a gate look sound.
The gate did not get worse when the corpus grew — it was always this weak, and
the original questions were not hard enough to show it.
