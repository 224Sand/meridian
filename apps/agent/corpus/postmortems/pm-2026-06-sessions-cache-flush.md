---
id: pm-2026-06-sessions-cache-flush
kind: postmortem
title: "Latency spike after sessions-cache key prefix change"
date: 2026-06-02
severity: 2
---

## Summary

A configuration change altered the cache key prefix on sessions-cache. The
entire working set became unreachable in a single moment, and the resulting
origin load raised checkout latency for 21 minutes.

## Impact

Checkout p99 latency rose from 180 ms to 3.1 s for 21 minutes. No errors were
returned; the system was slow, not broken.

## Timeline

- **09:14** Configuration change deployed.
- **09:15** `cache.hit_ratio` falls from 0.94 to 0.11 in one sample interval.
- **09:17** `db.active_connections` rises from 50 to 92.
- **09:22** On-call attributes the fall to an eviction and restarts the cache to
  "clear a bad state". This empties it a second time and extends the incident.
- **09:29** Key prefix change identified in the deploy diff.
- **09:31** Change rolled back.
- **09:35** Hit ratio recovers above 0.70. Latency returns to baseline.

## Root cause

A renamed configuration variable changed the key prefix. Every existing key
became unreachable instantly. Memory usage was unaffected, which is why this did
not look like an eviction to anyone reading the memory graph.

## What went wrong beyond the code

The restart at 09:22 made the incident worse and was based on a reasonable but
wrong hypothesis. The runbook at the time did not distinguish a capacity
eviction from a namespace change, and the two are indistinguishable on the hit
ratio graph alone. `cache.memory_used_ratio` separates them and was not being
consulted.

## Corrective actions

1. Runbook now leads with "do not restart the cache" and gives the memory-ratio
   test that distinguishes the two causes. **Done** — see `rb-cache-stampede`.
2. Request coalescing enabled on the sessions namespace. **Done.**
3. Key prefix moved behind a change-controlled setting requiring a second
   approver. **Done.**
