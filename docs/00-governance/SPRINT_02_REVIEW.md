# Sprint 2 — Review & Retrospective

**Sprint:** 2 — Agent Core I · **Closed:** 2026-08-20 · **Release:** 0.2.0

| Lens | Position |
|---|---|
| Product stage | MVP |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| AIDLC | 3 Context · 4 Grounding · 7 Serving |

---

## 1. Sprint goal

> A model call cannot leave this system ungoverned. Routing, caching, retrieval
> and refusal all work, are measured, and survive provider failure.

**Met.** 36 of 39 committed points. S1-09 remains blocked on IMP-04.

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S2-01 | Deterministic router | 8 | Ordered failover, typed failure taxonomy, injected clock |
| S2-02 | Provider adapters | 5 | 5 providers behind 2 adapters; HTTP outcomes classified |
| S2-03 | Failure injection | 3 | Session-scoped, expiring, cannot degrade another visitor |
| S2-04 | Semantic cache | 5 | Exact and vector tiers, keyed by embedding model |
| S2-06 | Hybrid retrieval | 5 | BM25 + dense, explicit degradation labelling |
| S2-07 | Evidence and refusal gate | 5 | Three bands, measured, plus a value-demand discriminator |
| S2-10 | Corpus depth and change domain | 5 | 19 documents, 87 chunks, differential-diagnosis sections |
| S2-05 | Hosted embedder | 3 | **Carried** — depends on ADR-0008 threshold measurement |
| S1-09 | Seed loader | 3 | **Blocked** — IMP-04 |

**Velocity: 36 of 39.** 224 tests: 218 offline, 6 integration.

## 3. The measurement that shaped the sprint

Every candidate refusal signal was measured against 10 answerable and 10
deliberately-unanswerable questions. **None of them separates the classes:**

| Signal | Answerable min | Unanswerable max | Margin |
|---|---|---|---|
| Dense cosine | 0.268 | 0.270 | **-0.003** |
| Lexical BM25 | 7.861 | 7.780 | +0.081 |
| Term coverage | 0.667 | **1.000** | **-0.333** |
| Fused normalised | 1.000 | 1.000 | **0.000** |

The fused score reads 1.000 for both classes, because normalising within a
result set makes the top hit 1.0 whether the match was excellent or hopeless.
That is precisely the defect in the system this design learns from, where the
refusal gate read 0.031 on both classes and was structurally incapable of
refusing anything.

A test now asserts the fused score does **not** separate the classes, so that a
future change gating on it fails loudly rather than silently disabling refusal.

## 4. Two decisions that came out of measurement, not preference

**ADR-0008 — the cache similarity threshold belongs to the embedder.** Written
first as a module constant of 0.86. Measurement showed paraphrases scoring 0.679
to 0.959 and distinct questions -0.065 to 0.034, so 0.86 sat nowhere near the
boundary. More importantly no constant can be right: a sparse hashed space puts
unrelated text near zero and a dense neural space puts it above 0.5. A threshold
carried between them returns confidently wrong cache hits and raises nothing.

**Three bands instead of one threshold.** Since no signal separates the classes,
the gate resolves the clear cases for free and routes the genuinely ambiguous
band to adjudication. Measured: 13 of 22 questions resolved with zero model
calls, zero unanswerable questions marked sufficient, zero answerable flatly
refused.

## 5. Retrospective

**What worked.** Measuring before choosing every threshold. Three separate
numbers that looked reasonable — 0.86 for the cache, a single fused-score
threshold, a bare digit match for stated values — were each wrong, and each was
caught by measurement rather than by review.

Writing `GAPS.md` in Sprint 1 paid for itself here. The gate could only be
falsified because a list of things the system must not answer already existed.

**What did not.** A fix was reported as applied and was not. A string
replacement against the source matched nothing because the formatter had already
rewrapped the target, and the script printed success. Half the change landed;
the call site did not. Compilation, lint, types and the full test suite all
passed with the function defined and never called. Only re-running the
measurement caught it.

**Improvement committed for Sprint 3.** A behavioural change is not complete
until a test or a measurement demonstrates the new behaviour. "The edit
succeeded" is not evidence that the behaviour changed, and this sprint produced
a concrete case where it was not.

**Also.** The original unanswerable question set was too easy. All ten were
vocabulary-absent cases. The gate did not weaken when the corpus grew — it was
always this weak, and the questions were not hard enough to show it.

## 6. Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted |
| IMP-04 | No managed Postgres or Redis credentials | **OPEN** — now blocks S1-09 and all deployment stories |

## 7. Gate

Sprint Review — pending Product Owner.
