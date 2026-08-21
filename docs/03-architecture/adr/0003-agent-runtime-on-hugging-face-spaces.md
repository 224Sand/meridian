# ADR-0003 — Host the agent runtime on Hugging Face Spaces (free CPU)

**Status:** **Superseded by [ADR-0012](0012-agent-runtime-on-northflank.md)** (2026-08-22) · **Date:** 2026-08-20 · **Deciders:** Executive Sponsor (NFR-002, INF-001)

> **Superseded.** Hugging Face moved Docker Spaces behind a PRO subscription;
> only Static Spaces remain free, and a Static Space cannot run FastAPI. The
> pricing claim in this ADR was never verified against the pricing page — that
> omission, not the choice itself, is the defect. See ADR-0012.

## Context
NFR-002 requires zero infrastructure cost. Candidates evaluated: Google Cloud Run
(generous always-free tier, ~1–3 s cold start, requires a card on file), Render
free tier (no card, but sleeps after 15 minutes with a ~50 s cold start),
Hugging Face Spaces free CPU (no card, 2 vCPU / 16 GB, sleeps only after
prolonged inactivity), and Fly.io (no longer meaningfully free).

## Decision
Hugging Face Spaces, Docker SDK, free CPU tier. The Executive Sponsor declined
card-backed services outright.

## Consequences
**Positive.** No payment instrument required. 2 vCPU / 16 GB is materially more
capacity than most free tiers. The 48-hour idle window is far more forgiving than
Render's 15 minutes, and a 6-hourly warm-ping makes sleep effectively unreachable.

**Negative.** The container filesystem is ephemeral, so no state may live on
local disk — this drives NFR-005 and forces all state into Postgres and Redis.
The image must bind port 7860. Build times are sensitive to image size, which is
what rules out `torch` (see ADR-0004).

**Accepted risk (R-01).** A visitor arriving after a long idle period sees a cold
start. Mitigated by the warm-ping and by streaming placeholder UI, not eliminated.
