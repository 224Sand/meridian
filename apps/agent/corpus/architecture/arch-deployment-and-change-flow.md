---
id: arch-deployment-and-change-flow
kind: architecture
title: Deployment topology and change flow
owner: Platform Edge
---

## Environments

Three: development, staging and production. Staging carries a synthetic dataset
of the same shape as production but roughly one percent of its volume. That
ratio matters when reading a staging result: faults whose cost scales with data
size, such as query amplification and shard imbalance, are invisible in staging
by construction.

## Change flow

A change moves through: proposal and classification, review or approval by risk
level, merge, staged rollout, and observation. Every deploy emits a change
marker carrying service, version and commit, which is the first thing incident
triage lists for the incident window.

## Rollout strategy by tier

Tier 0 and Tier 1 services on the synchronous path roll out by region, one
region at a time, with a minimum observation period between regions. Tier 2 and
Tier 3 roll out in a single step.

The observation period exists to catch faults that only appear under production
data shape. It is not a soak test for correctness, which should have been
established before merge.

## Rollback

Rollback is a redeploy of the previous version and is the first response to any
incident correlated with a recent deploy (`pol-change-management`). Rollback
capability is asserted at deploy time: a version that cannot be rolled back to
is not a version that can be deployed.

Configuration changes roll back the same way, and carry the same expectation.
Several of the most expensive incidents on record were configuration-only.

## What is not automated

Promotion between environments requires a human action for Tier 0 and Tier 1.
This is deliberate and is not a maturity gap: the observation period between
regions is only meaningful if someone observes.
