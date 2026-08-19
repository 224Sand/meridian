# ADR-0005 — Vectors from different embedding models are never compared

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect

## Context
ADR-0004 introduces two embedding sources. Storing both in one `vector` column
and comparing them would produce a cosine similarity that is arithmetically valid
and semantically meaningless. This class of bug is silent: retrieval keeps
returning results, they are simply the wrong ones, and no error is ever raised.

## Decision
Embeddings live in `chunk_embedding(chunk_id, model, dim, vec)` with a unique
constraint on `(chunk_id, model)`. Every query filters on the active embedding
model. The semantic cache key includes `embedding_model`. When the active model
has no stored vectors, retrieval **degrades to BM25-only and labels itself
degraded** — it never falls back to a different space.

## Consequences
**Positive.** Cross-space comparison becomes structurally impossible rather than
merely discouraged. Adding a third embedding model later requires no migration.
Degradation is explicit and visible to the user.

**Negative.** Storage is duplicated per model. Backfilling a new model is an
explicit job. A cache miss occurs whenever the active embedding model changes,
which is correct but costs a warm-up.

**Verification.** A regression test asserts that a query under model A never
returns rows embedded under model B.
