# Postmortem — the refusal gate I reported as working has a 57% false-answer rate

**Date:** 2026-08-20 · **Sprint:** 3 · **Severity:** 1 (would be, in production)
**Status:** Confirmed, quantified, replacement measured · **Author:** QA Lead

> Published because `/delivery` renders our own defects. This one contradicts a
> claim made at a sprint gate that the Product Owner accepted, so it is stated
> at the top rather than buried.

## Summary

At the Sprint 2 review I reported that the evidence gate produced **zero
unanswerable questions marked SUFFICIENT** and described that as the product
failure never occurring.

That measurement was taken on **22 hand-written questions**.

Measured on **534 questions with labels true by construction**, the same
unchanged gate marks **150 of 265 unanswerable questions as SUFFICIENT — a
false-answer rate of 56.6% [50.6%, 62.4%]**.

The gate does not work. The Sprint 2 result was not wrong about the 22
questions; it was wrong about what those 22 questions could support.

## The numbers

| | Sprint 2 claim (n=22) | Sprint 3 measurement (n=534) |
|---|---|---|
| Unanswerable marked SUFFICIENT | 0 | **150 / 265** |
| False-answer rate | 0% | **56.6% [50.6, 62.4]** |
| ROC AUC of the combined score | not measured | **0.631 [0.584, 0.676]** |

An AUC of 0.63 is a weak signal. 0.5 is a coin flip.

The hand-picked band edges are worse than the summary suggests:

| Threshold | Chosen as | True-positive rate | False-positive rate | Youden's J |
|---|---|---|---|---|
| `INSUFFICIENT_BELOW = 1.5` | "clearly too weak" | 0.978 | **0.943** | **0.034** |
| `SUFFICIENT_ABOVE = 3.0` | "clearly strong enough" | 0.758 | 0.574 | 0.185 |
| Youden optimum | — | 0.550 | 0.272 | 0.278 |

`INSUFFICIENT_BELOW = 1.5` sits at J = 0.034. That is the diagonal. It is
almost exactly as informative as a coin.

## Root cause

**The test set was too small and too easy, and it was written by the person who
also wrote the thing it tested.**

The 22 questions were assembled by hand while building the gate. Ten were
vocabulary-absent cases — disk exhaustion, DNS, Kubernetes — where the corpus
contains none of the relevant words. Those are trivially separable and they made
the gate look sound.

The generated set contains 265 unanswerable questions, most of which are the
*hard* class: property transfer and false-presupposition cases, where every term
in the question appears in the corpus and the answer does not. The gate was never
able to handle those. It was only ever asked the easy ones.

This is the same root cause as the postmortem two days earlier, at a larger
scale, and the earlier one already named it: *"Test sets assembled from the easy
version of a failure make a gate look sound."* It was written and it did not
change what happened next, because nothing in the process forced the test set to
grow before the result was reported.

## Contributing factor: no interval was ever reported

Every Sprint 2 number was a point estimate from one small sample. A confidence
interval on the false-answer rate at n=22 would have been wide enough to make
"zero" obviously uninformative. None was computed, so "0 of 10" read as certainty
rather than as an absence of evidence.

## What the replacement measures

The same features, fitted rather than hand-weighted, cross-validated with folds
**grouped by source document**:

| Model | ROC AUC | Recall at a 5% false-positive budget |
|---|---|---|
| Heuristic (`dense x lexical`) | 0.631 [0.584, 0.676] | 0.186 |
| Logistic regression | 0.661 [0.619, 0.705] | 0.223 |
| **Gradient boosting** | **0.788 [0.749, 0.824]** | **0.431** |

**2.3x the recall at the same false-positive rate.** McNemar on paired decisions:
the model is right and the heuristic wrong on 91 cases, the reverse on 28,
**p = 5.8e-09**. Accuracy 0.689 [0.649, 0.727] against 0.571 [0.529, 0.612].

The improvement is real and it is not close to the significance boundary.

## What this does not fix

**0.788 is better, not good.** At a 5% false-positive budget it recalls 43% of
answerable questions, so more than half still route to adjudication. The
adjudication step is not a nicety on top of a working gate; it is load-bearing,
and this measurement is what establishes that.

**The linear model recovers almost none of the gain.** ADR-0009 requires serving
without the training framework, and a logistic regression ships as a vector of
coefficients in pure Python. Gradient boosting does not. Shipping logistic means
0.661 instead of 0.788 — most of the improvement discarded for a deployment
constraint. That trade is a decision for the Product Owner, not a default.

## Corrective actions

1. Sprint 2's stated result is corrected in the record rather than left
   standing. **Done** — this document.
2. Thresholds are selected by an operating-point rule against a
   false-positive budget, never by hand. **Done.**
3. Every reported rate carries a Wilson interval. **Done.**
4. A gate result from fewer than 100 labelled examples may not be reported as a
   result. It is a smoke test. **Adopted as a Definition of Done item.**
5. Champion selection and the serving-format decision are separated, so the
   better model is identified even when it cannot ship. **Done.**

## Lesson

The earlier postmortem identified the cause and did not prevent the recurrence,
because it produced a lesson and not a constraint. Item 4 above is a constraint.

The measurement that mattered here took two hours and could have been run in
Sprint 2. It was not run because the gate appeared to work, and it appeared to
work because the only evidence available was evidence chosen by the author.
