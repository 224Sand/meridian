---
id: rb-timeout-and-retry
kind: runbook
title: Synchronous timeout cascade
owner: Platform Edge
---

## When this applies

`http.client.timeout_rate` rises sharply on one caller while its own
`thread_pool.queue_depth` grows. Multiple upstream services begin failing within
minutes of each other.

## What is happening

A slow synchronous dependency occupies caller threads for the full timeout
duration. The caller exhausts its own capacity waiting, and its callers then do
the same. Retries make it worse: each retry adds load to the dependency that is
already the constraint, so the system degrades faster the harder it tries to
recover.

## Diagnosis

1. Walk the dependency graph downward from the first service that degraded. The
   root is the deepest service whose own dependencies are healthy.
2. Compare onset times. The root moves first; each hop upward moves later. If
   two services degraded simultaneously, they share a dependency rather than
   causing each other.
3. Check the retry configuration on the failing caller. Retries without backoff
   and without a circuit breaker convert a slow dependency into an outage.
4. Confirm the dependency is slow rather than erroring. A dependency returning
   fast errors produces a different signature and does not exhaust threads.

## Remediation

- Open the circuit breaker to the slow dependency. Failing fast returns capacity
  to the caller immediately.
- Reduce the client timeout to below the caller's own budget. A timeout longer
  than the caller's deadline guarantees thread exhaustion.
- Disable retries to the affected dependency until it recovers.
- Fix the root. Everything above is containment, and containment that is left in
  place becomes the next incident.

## Escalation

Page the owning team of the root service. Page Platform Edge if more than three
services are affected or if any Tier 0 service is failing.

## Related

`rb-database-connection-pool` · `rb-memory-pressure` · `pol-incident-severity`
