# ADR-0001 — Split the experience layer from the agent runtime

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect, Stakeholder (AC-001)

## Context
The product needs a cinematic web experience and a stateful multi-agent runtime.
Every credible implementation of the agent side — LangGraph, BM25, the evaluation
harness, the local embedder — exists in Python. Every credible implementation of
the experience side — React Server Components, streaming, the motion layer —
exists in the JavaScript ecosystem. A single runtime forces one of the two to be
reimplemented.

## Decision
Two deployable units behind a versioned HTTP contract: a Next.js experience layer
acting as a backend-for-frontend, and a FastAPI agent runtime.

## Consequences
**Positive.** Each side uses its native ecosystem. The BFF holds provider secrets
so the browser never does. Either side can be replaced independently. The pattern
matches how large consumer platforms actually deploy — a JS edge in front of
polyglot services.

**Negative.** Two deploy targets, two CI paths, and a network hop on every run.
Distributed tracing becomes mandatory rather than optional, because a single
request now spans two languages.

**Reversal condition.** If the Python-only components were ever replaced with
equivalents in TypeScript, this decision loses its justification and the system
should collapse to one runtime. That is a real condition, not a formality.
