---
id: rb-search-shard-imbalance
kind: runbook
title: Search shard imbalance on catalog-search
owner: Data Platform
---

## When this applies

`search.query.p99_ms` rises while mean query latency stays within its normal
range. `search.shard.max_docs_ratio` exceeds 2.0.

## What is happening

Documents have concentrated on one shard. Every query fans out to all shards and
waits for the slowest, so the tail is set by the largest shard while the mean is
set by the rest. A dashboard built on averages shows nothing wrong.

## Diagnosis

1. Compare per-shard document counts. A ratio above 2.0 between largest and
   median is the confirmation.
2. Check the routing key. Imbalance is usually a routing key with low
   cardinality, or one that correlates with document volume such as tenant or
   category.
3. Confirm the mean is genuinely healthy. If the mean has also risen, this is a
   cluster capacity problem, not an imbalance.

## Remediation

- Force a shard rebalance if the cluster supports it and imbalance is recent.
- For a routing key problem, reindex with a corrected key. Rebalancing does not
  fix a key that will re-concentrate.
- Increase shard count only as part of a reindex; changing it alone does not
  redistribute existing documents.

## Escalation

Page Data Platform when `search.query.p99_ms` exceeds 2000 ms for 10 minutes.
Tier 2 service, so this does not page outside business hours unless a Tier 0
consumer is affected.

## Related

`pol-incident-severity`

## Common misdiagnosis

**Declared healthy from mean latency.** Every query waits for the slowest shard,
so the tail is set by the largest shard and the mean by the rest. A dashboard
built on averages shows nothing wrong throughout.

**Mistaken for cluster capacity.** If the mean has also risen it is capacity. If
only the tail moved it is imbalance. Adding nodes does not redistribute existing
documents.

**Rebalanced without fixing the routing key.** A low-cardinality routing key
re-concentrates after every rebalance. Rebalancing buys time and changes
nothing.
