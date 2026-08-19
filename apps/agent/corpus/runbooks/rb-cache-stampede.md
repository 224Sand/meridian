---
id: rb-cache-stampede
kind: runbook
title: Cache stampede on sessions-cache
owner: Data Platform
---

## When this applies

`cache.hit_ratio` falls below 0.30 within a few minutes and
`cache.evictions_per_s` rises by more than two orders of magnitude, while
`cache.memory_used_ratio` approaches 1.0.

## What is happening

The working set has been evicted, so requests that were being absorbed by the
cache all miss at once and arrive at the origin together. The origin sees a
traffic spike it never actually received from users.

## Diagnosis

1. Check `cache.memory_used_ratio`. At or near 1.0 the eviction is capacity
   driven. Well below 1.0 it was an explicit flush or a restart.
2. Correlate the fall in `cache.hit_ratio` with deploys and with any
   configuration change to the key namespace. A changed key prefix invalidates
   the entire working set instantly and looks identical to an eviction.
3. Confirm the origin is the thing degrading: `db.active_connections` rising in
   step with the miss rate confirms the wave reached the database.

## Remediation

- Do not restart the cache. A restart empties it again and restarts the stampede.
- Enable request coalescing on the affected key namespace so that concurrent
  misses on one key issue a single origin read.
- Re-warm the top keys from the origin at a controlled rate before removing any
  rate limit.
- If a key prefix changed, roll the change back rather than waiting for natural
  re-warming.

## Escalation

Page Data Platform on-call if the hit ratio has not recovered above 0.70 within
15 minutes of coalescing being enabled.

## Related

`rb-database-connection-pool` · `pm-2026-06-sessions-cache-flush`
