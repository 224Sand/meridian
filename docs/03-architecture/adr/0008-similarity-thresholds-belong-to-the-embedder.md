# ADR-0008 — Similarity thresholds belong to the embedder, not to the cache

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect
**Supersedes nothing. Extends ADR-0005.**

## Context

The semantic cache was first written with a module-level
`SIMILARITY_THRESHOLD = 0.86`, chosen because 0.86 is the sort of number that
appears in semantic-cache examples.

Measuring it over real corpus questions showed the number was wrong in both
directions at once. With the offline hashed embedder, paraphrases of the same
operational question scored **0.679 to 0.959** and distinct questions scored
**-0.065 to 0.034**. A threshold of 0.86 would have missed genuine paraphrases
near the bottom of that range, while sitting far above where the actual decision
boundary is.

The more consequential finding is why a single constant cannot be correct. A
sparse hashed space and a dense neural space have entirely different similarity
distributions. Unrelated text scores near zero in the first and routinely above
0.5 in the second. A threshold calibrated in one is not merely suboptimal in the
other — in the dense space it would treat unrelated questions as the same
question and return the wrong cached answer, with no error raised anywhere.

This is the same failure ADR-0005 prevents for the vectors, arriving through the
threshold instead.

## Decision

`similarity_threshold` is a property of the `Embedder`. `SemanticCache` reads it
from whichever embedder it holds. There is no module-level default.

`HashingEmbedder.similarity_threshold = 0.60`, derived from the measurement
above: an order of magnitude above the highest observed distinct pair, and below
the lowest observed paraphrase.

The value is biased toward the miss. A missed cache hit costs one model call. A
false hit returns a wrong answer to a user and looks exactly like a correct one.

Any embedder added later must state its own measured threshold. A test
re-derives the separation and fails if it stops holding.

## Consequences

**Positive.** Adding an embedder forces the question "what is the boundary in
*your* space" to be answered with a measurement. The regression test makes a
silent drift in the embedder visible as a failure rather than as slightly wrong
answers.

**Negative.** Every embedder implementation carries a calibration obligation.
That is the intended cost.

**Watch item.** The hosted embedder is not yet implemented. It must not inherit
0.60. Its threshold is measured against the same paraphrase and distinct pairs
before it is enabled, and the test that does so is a release blocker for it.
