# Postmortem — a null result that was two bugs wearing a trench coat

**Date:** 2026-08-20 · **Sprint:** 3 · **Severity:** would have shipped a false conclusion
**Status:** Both causes fixed; the real result is honestly inconclusive · **Author:** QA Lead

## Summary

The cross-encoder re-ranker experiment returned a clean-looking null result:
metrics identical before and after fine-tuning, to every decimal place. The
obvious reading was "re-ranking does not help this system."

It was two independent bugs producing that appearance, and identical metrics to
the decimal should have been the tell. A real null result is noisy.

## Bug one: the model produced NaN, and NaN sorts as no-op

`cross-encoder/ms-marco-MiniLM-L-6-v2` loads with **zero NaN in any parameter**
and produces **NaN logits on a plain forward pass** on this machine.

Python's sort is stable, and comparisons against NaN are all false, so sorting
by a NaN score **returns the input order unchanged**. The "re-ranked" ranking was
the baseline ranking. Every metric matched exactly because they were the same
numbers.

Training also ran to completion, reporting `loss nan` for both epochs — visible
in the output and not acted on, because attention was on the metrics below it.

Ruled out along the way: torch 2.13 and 2.8; transformers 5.15 and 4.57;
Anaconda and Homebrew interpreters; the duplicate-`libomp` conflict.
`TinyBERT-L-2-v2` produces correct ordered logits under identical conditions, so
it is checkpoint-specific rather than environmental.

Three environment findings surfaced while isolating it, all real and none the
cause: torch 2.13 **SIGBUSes (exit 138)** with three copies of `libomp` present;
the project venv was built on Anaconda's interpreter; `KMP_DUPLICATE_LIB_OK`
stops the crash without fixing the numerics.

**Fix.** A guard raises on non-finite scores, with the reason in the message. A
test asserts scores are finite. Training moved to `.venv-train` on Homebrew
Python — isolated from serving, which is what ADR-0009 asks for anyway.

## Bug two: the metric was already saturated

Evaluation measured whether the gold **document** reached the top of the
ranking. Hybrid retrieval already scores **hit@1 0.971, MRR 0.986** there. The
maximum possible improvement was 0.014, so any re-ranker would have looked
useless.

The metric that matters is **chunk** level, because a citation points at a
chunk. There, hybrid retrieval scores **hit@1 0.333, MRR 0.528**.

The headroom was **0.472** and it was invisible for as long as the wrong metric
was being read.

**The ground truth already existed.** Section-derived question ids encode the
chunk they were generated from (`q-sec-<chunk id>-<index>`). It was never used.
`Question` now carries `gold_chunk_id` explicitly, and a heading-derived
generator covers every chunk rather than the 53 of 87 that matched a template.
Dataset 534 → 715; gold-chunk examples 93 → 220.

## The actual result, which is inconclusive

| Level | | hit@1 | hit@3 | MRR |
|---|---|---|---|---|
| Chunk | hybrid | 0.333 | 0.667 | 0.528 |
| Chunk | + fine-tuned CE | **0.400** | **0.733** | **0.587** |
| Document | hybrid | 0.971 | 1.000 | 0.986 |
| Document | + fine-tuned CE | 0.957 | 1.000 | 0.979 |

**The improvement is not established.** Paired bootstrap 95% CI on the MRR
difference is **[-0.024, +0.147]** — it includes zero. McNemar on hit@1 gives 3
discordant against 1, **p = 0.625**.

This is a **power** problem, not an effect problem. Detecting the observed
+0.067 at 80% power requires **811 examples per arm**. There are **30**.

Note also that document-level MRR *falls* under re-ranking, 0.986 → 0.979.
Re-ranking a saturated metric costs a little, which is the second reason the
first evaluation read as a null.

## What ships

The artefact ships, with the inconclusive finding written into its metrics file
rather than the point estimate quoted alone. It is served as ONNX plus the Rust
tokenizer core — 17 MB, 19 ms p50 for 20 candidates, no training framework at
runtime, parity 3.6e-06.

It is **not wired into the request path**. A component whose benefit is
unestablished does not get to add latency to every query on the strength of a
point estimate.

## A lesson that repeated inside one sprint

The re-ranker's ONNX parity sample originally used **four copies of one pair**,
producing four identical logits — a parity check that passes while testing
nothing. The classifier's parity test, written days earlier in this same sprint,
already contains a test named
`test_the_parity_sample_spans_a_real_range_of_probabilities` guarding exactly
this. The lesson was written down and reproduced anyway.

Written-down lessons do not prevent recurrence. The test that prevents it is the
one that runs. Both parity samples now assert a real spread.

## Corrective actions

1. Non-finite scores raise, with a test. **Done.**
2. Evaluation reports document AND chunk level; the artefact's metrics file
   records both, so quoting only the saturated one requires deliberately
   ignoring the other. **Done.**
3. Every reported difference carries a paired interval and a significance test.
   **Done.**
4. Where a result is under-powered, the required sample size is computed and
   published alongside it. **Done.**
5. Parity samples must span a real range, asserted by test, in both models.
   **Done.**

## Lesson

A null result that is identical to the decimal place is not a null result. It is
a pipeline that is not running.
