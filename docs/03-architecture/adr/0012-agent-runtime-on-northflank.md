# ADR-0012 — The agent runtime runs on Northflank, not Hugging Face Spaces

**Status:** Accepted · **Date:** 2026-08-22 · **Deciders:** Solutions Architect / FDE
**Supersedes ADR-0003.**

## Context

ADR-0003 placed the agent runtime on Hugging Face Spaces using the Docker SDK,
on the stated grounds that it was free. That was true when the decision was
written and is no longer true: Hugging Face now requires a PRO subscription for
Docker and Gradio Spaces, and only Static Spaces remain free. A Static Space
cannot run FastAPI, so the decision did not merely become expensive — it became
impossible at $0.

The failure here was not choosing Spaces. It was **never verifying the free tier
before building three sprints of deployment work on top of it**, and then
writing an ADR that recorded the choice without recording how the pricing claim
had been checked. It had not been checked at all. The whole point of NFR-002 is
that zero infrastructure cost is a requirement with a test behind it; the test
asserted that no *paid host* appeared in a manifest, which a host that silently
moves behind a paywall passes trivially.

## Decision

Run the agent runtime on **Northflank**, Developer Sandbox plan, in
`europe-west` (London).

## Why this one

The search was constrained by three things: $0, a container that needs roughly
250MB on disk, and a first-visit experience a recruiter will not wait through.

| Option | Free tier | Outcome |
|---|---|---|
| **Northflank Sandbox** | **$20/mo of managed resources, always-on** | **Chosen** |
| Google Cloud Run | 180k vCPU-s + 2M requests/mo, perpetual | Viable fallback; cold starts |
| Modal | $0 + $30/mo recurring credits | Viable; Python-native, scale-to-zero |
| Render | Free instance, 512MB | Works, but sleeps — ~60s to wake |
| Vercel Python | 250MB bundle ceiling | Runtime closure is ~255MB. Would mean dropping the cross-encoder |
| Koyeb | None — from $29/mo | Eliminated |
| Fly.io | None — pay as you go | Eliminated |
| HF Docker Space | PRO only | Eliminated; this is what we came from |

Northflank is the only free option that **does not sleep**. That decided it. A
scale-to-zero host is cheaper in principle and worse in practice for this
product: the entire audience is first-time visitors arriving from a link, which
is exactly the request a cold start punishes.

The measured runtime footprint is **108MB peak** during a full run with
re-ranking, against 512MB on `nf-compute-20` at $5.40/mo — comfortably inside
the $20 allowance with room to move up to `nf-compute-50` if inference latency
warrants it.

That 108MB is worth recording, because the deployment work was nearly re-planned
around the wrong number. The dependency closure is ~255MB **on disk**, which is
what eliminated Vercel; but hosts constrain **memory**, and onnxruntime maps
only what it uses. Reasoning about disk size where RAM was the constraint made
the problem look far tighter than it is.

## What this costs

- **No SLA, and Northflank documents the Sandbox as not for production.** For a
  demonstration surface that is acceptable and is stated on the surface itself
  rather than hidden.
- **A payment method is required on file**, on every Northflank plan, even the
  free one. It is a verification measure and nothing is charged inside the
  allowance, but it is not a card-free option and should not be described as one.
- **Two free services, one addon.** The architecture fits, with nothing spare.
- **The image has still never been built locally** — no Docker on the
  development machine. Northflank's first build is the first real build.

## What survives

The Dockerfile, unchanged apart from its path (`deploy/Dockerfile`). It was
written to be a plain container rather than a Spaces artifact, so the only
Hugging Face specifics were the Space README's front matter and the publish
script, both of which are deleted. Two-stage build, non-root uid 1000, single
worker, healthcheck on `/healthz` — all still correct.

## Consequence for the requirement

NFR-002's test now asserts against an allowlist containing `code.run` and
`northflank.com` instead of `hf.space`. That is the same weak check as before,
and it would not have caught this failure either. **The real control is that a
pricing claim in an ADR must name the page it was read from and the date** —
recorded in `WAYS_OF_WORKING.md` rather than left to habit, since habit is what
produced this.
