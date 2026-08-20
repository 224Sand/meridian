# ADR-0011 — No approximate-nearest-neighbour index until the corpus reaches ~5,000 chunks

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect
**Evidence:** `apps/agent/training/benchmark_ann.py`, run against the live Neon instance
**Relates to:** ADR-0004, ADR-0005

## Context

The schema defines an HNSW index on `chunk_embedding`. It was added because a
vector column with an HNSW index is what a pgvector schema looks like, which is
not a reason.

This system's corpus is **87 chunks**. Whether an index helps at that size is a
measurable question and it had not been measured.

## The measurement

Server-side execution time from `EXPLAIN ANALYZE`, 50 queries per configuration,
clustered synthetic vectors at 768 dimensions, run against Neon Postgres 17.11
with pgvector 0.8.0.

| Vectors | Method | p50 | p95 | recall@10 | distance ratio | build | index |
|---:|---|---:|---:|---:|---:|---:|---:|
| 87 | exact | 0.48 ms | 0.52 ms | 1.000 | 1.0000 | — | — |
| 87 | hnsw | 0.48 ms | 0.54 ms | 1.000 | 1.0000 | 0.07 s | 360 KB |
| 1,000 | exact | 5.35 ms | 6.03 ms | 1.000 | 1.0000 | — | — |
| 1,000 | hnsw | 5.31 ms | 5.68 ms | 1.000 | 1.0000 | 0.51 s | 4 MB |
| 1,000 | ivfflat | 5.31 ms | 5.92 ms | 1.000 | 1.0000 | 0.09 s | 4 MB |
| 5,000 | exact | 26.47 ms | 30.87 ms | 1.000 | 1.0000 | — | — |
| 5,000 | hnsw | **2.58 ms** | 2.81 ms | 0.686 | 1.0026 | 3.79 s | 20 MB |
| 5,000 | ivfflat | **1.61 ms** | 2.06 ms | 0.570 | 1.0068 | 0.44 s | 20 MB |
| 20,000 | exact | 107.63 ms | 113.39 ms | 1.000 | 1.0000 | — | — |
| 20,000 | hnsw | **3.87 ms** | 4.29 ms | 0.370 | 1.0076 | 34.25 s | 80 MB |
| 20,000 | ivfflat | **1.94 ms** | 2.31 ms | 0.226 | 1.0162 | 3.04 s | 80 MB |

## Decision

**Exact search until the corpus reaches roughly 5,000 chunks.** The HNSW index
declared in migration 0001 is retained — it costs 360 KB and nothing at query
time at this size — but the system does not depend on it and the decision to
rely on one is deferred until the measurement above says it pays.

Revisit when the corpus exceeds 5,000 chunks, or when exact-search p50 exceeds
20 ms, whichever comes first.

## Why

**At 87 chunks the index earns nothing.** 0.48 ms against 0.48 ms. The
difference is below measurement noise.

**Exact search is linear and the constant is small.** 0.48 → 5.35 → 26.47 →
107.63 ms across a 230-fold increase in corpus size. Under 30 ms at 5,000
chunks, which is 57 times this corpus.

**Build cost grows faster than query benefit.** HNSW build: 0.07 → 0.51 → 3.79 →
34.25 seconds. At 20,000 vectors it costs 34 seconds of build to save 100 ms per
query, so it pays back only above roughly 340 queries per rebuild. The corpus is
re-seeded on every deploy.

**Storage roughly doubles.** The index is about 4 MB per 1,000 vectors at 768
dimensions, comparable to the vectors themselves. Neon's free tier is 512 MB
(NFR-002).

## The metric that changed the reading

Recall@10 falls to **0.370** for HNSW at 20,000 vectors, which looks like a
serious quality loss and is not one. The **distance ratio** — how much further
away the approximate neighbour is than the exact one — is **1.0076**. The
neighbours it returned were 0.76% further away.

In 768 dimensions with clustered data, intra-cluster distances concentrate
tightly, so a point's ten nearest neighbours are near-ties chosen from a much
larger set of almost-equidistant candidates. Set-overlap recall cannot tell
"found a worse neighbour" from "broke a tie differently", and at this
dimensionality nearly every disagreement is the second kind.

**Reporting recall alone would have understated both indexes by a wide margin.**
Any future ANN decision here reports distance ratio alongside recall.

## Two measurement errors worth recording

The first run of this benchmark produced numbers that could not be believed, and
both causes are easy to repeat:

**Client wall-clock measured the network.** Every configuration read 65–68 ms
regardless of method or corpus size — the round trip to a managed database in
another region. "HNSW wins at 87 vectors" was 65.38 ms against 65.41 ms on a
65 ms floor. Timing now comes from `EXPLAIN ANALYZE`.

**Session-level `SET` was silently discarded.** Tuning was applied with
`SET ivfflat.probes`. The connection is Neon's **pooled** endpoint, which pools
in transaction mode, so session state does not survive to the next statement and
the setting never applied. Tuning is now `SET LOCAL` inside the same explicit
transaction as the query.

## Consequences

**Positive.** The system uses the simplest thing that works, and there is now a
number attached to the word "works" and a threshold at which to revisit.
Retrieval stays exact, so ADR-0005's degradation path has no approximation
interacting with it.

**Negative.** A corpus that grows past 5,000 chunks without anyone re-running the
benchmark will get slow before it gets fixed. The revisit trigger is written
above rather than left to be noticed.

---

## Addendum, 2026-08-20 — the managed vector store arm

FR-030 named "a managed vector store" as the fourth arm. Upstash Vector was
provisioned (768 dimensions, cosine, dense, `eu-west-1`) and the arm is
**deferred**, for two reasons that are themselves results.

### The free tier allows 10,000 writes per day

Every upserted vector counts as one write. The sweep as designed — 87 + 1,000 +
5,000 + 20,000 — needs **26,087**, and exhausted the allowance partway through
the third size:

```
{"error":"Exceeded daily write limit: 10000","status":403}
```

That is an operational property worth knowing before choosing the store, not an
obstacle to the benchmark. A managed vector database whose free tier cannot
ingest 26k vectors in a day is a different proposition from one that can, and
this project's corpus is 87 chunks — so the limit is irrelevant to *this* system
and would be decisive for a larger one.

The sweep now checks its own write budget before starting. A benchmark that runs
out of budget mid-way does not produce partial results; it produces an index in
an unknown state.

### Latency is not comparable, and will not be reported as if it were

pgvector's figures come from `EXPLAIN ANALYZE` and exclude the network. Upstash
exposes no server-side timing, so its figures are client wall-clock including a
round trip. Measured from the development machine:

| Store | Region | Client p50 | Server p50 |
|---|---|---|---|
| Neon Postgres | `ap-southeast-1` | 52.2 ms | **0.06 ms** |
| Upstash Redis | `ap-south-1` | 106.6 ms | — |
| Upstash Vector | `eu-west-1` | 519.4 ms | — |

Putting 519 ms beside pgvector's 0.48 ms would repeat exactly the error that made
this benchmark's first run meaningless, where every configuration read 65–68 ms
because the network was being measured rather than the query.

**Recall@k and distance ratio remain fully comparable** — no timing is involved —
and those are what the arm will report when it runs.

### A measurement that was refused rather than published

With the write allowance spent, the index still held 600 vectors from the partial
run. The obvious salvage was to measure against those, and the script's own
precondition refused: probing a known vector returned `id=2930` where the
deterministic corpus predicts `id=7`, so the index contents did not match any
corpus the benchmark generates.

Measuring against an index of unknown composition produces numbers that look
exactly like real ones. The arm is deferred instead.
