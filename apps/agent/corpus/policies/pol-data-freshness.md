---
id: pol-data-freshness
kind: policy
title: Data freshness commitments
owner: Data Platform
---

## Commitments

| Consumer tier | Maximum acceptable freshness lag |
|---|---|
| Tier 0 and Tier 1 | 300 seconds |
| Tier 2 | 900 seconds |
| Tier 3 (batch) | 4 hours |

Freshness lag is measured as `pipeline.freshness_lag_s`: the age of the newest
record a consumer has processed, not the age of the newest record published.
Measuring at the publisher hides exactly the failure this policy exists to catch.

## Breach handling

A breach of a Tier 0 or Tier 1 commitment is a Severity 2 incident even when no
service is erroring. Stale data presented as current is a correctness failure,
and correctness failures do not become acceptable because nothing crashed.

## Replay and backfill

Any replay expected to exceed 10% of normal publish rate must be throttled and
announced to consumer-owning teams in advance. An unthrottled replay will outrun
steady-state consumer capacity and manufacture a freshness breach.

## What this policy does not cover

Retention. How long data is kept, and deletion obligations, are outside this
policy entirely.
