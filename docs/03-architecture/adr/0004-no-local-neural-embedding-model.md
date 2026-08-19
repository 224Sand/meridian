# ADR-0004 — No local neural embedding model in the container

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect

## Context
Dense retrieval needs embeddings. The default choice, `sentence-transformers`,
pulls `torch` — 2–3 GB of image weight. Under ADR-0003 that inflates build time
severely and risks the free tier's limits, for a corpus small enough that the
quality difference is marginal.

## Decision
Dense embeddings come from Gemini `text-embedding-004` (768 dimensions, free
tier). The offline fallback is a deterministic zero-dependency embedder carried
over from prior work, which projects hashed character n-grams into the same 768
dimensions. Lexical retrieval is BM25 in pure Python and is always available.

## Consequences
**Positive.** The image stays small. Retrieval works with no API key at all,
which means tests run offline and deterministically. The fallback is a genuine
degradation path rather than a hypothetical one.

**Negative.** Dense retrieval depends on an external provider during normal
operation, so the embedding provider joins the router's failure surface.

**Important.** The fallback embedder does **not** produce vectors comparable with
Gemini's. See ADR-0005 — this is the constraint that decision exists to enforce.
