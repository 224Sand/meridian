---
id: pm-2026-05-orders-db-saturation
kind: postmortem
title: "Checkout unavailable for 34 minutes — orders-db pool exhaustion"
date: 2026-05-14
severity: 1
---

## Summary

Checkout returned errors for 34 minutes. The cause was connection pool
exhaustion on orders-db, introduced by a change that moved a transaction
boundary to wrap an external payment call.

## Impact

Checkout unavailable for 34 minutes. Catalog browsing was unaffected throughout,
because it does not depend on orders-db.

## Timeline

- **14:02** Deploy of order-orchestrator lands.
- **14:19** `db.pool.wait_ms` begins climbing. No alert fires; there was no
  threshold on this metric at the time.
- **14:31** `db.pool.available` reaches zero. Checkout error rate crosses 30%.
  Alert fires on error rate.
- **14:36** On-call identifies pool saturation from `pg_stat_activity`.
- **14:41** Idle-in-transaction sessions terminated. Error rate falls but
  recovers to 30% within four minutes as the pool refills.
- **14:58** Deploy rolled back. Error rate returns to baseline.
- **15:05** Incident closed.

## Root cause

The change wrapped an external payment provider call inside the database
transaction. Hold time per request rose from about 12 ms to the provider's
p99 of roughly 1.9 s. Request volume never changed. The pool is sized for
concurrency, so a 150-fold increase in hold time exhausted it at unchanged traffic.

## What went wrong beyond the code

Terminating idle transactions was treated as a fix. It is not; it releases
connections that are immediately re-consumed by the same code path. Twelve of
the 34 minutes were spent repeating a mitigation that could not hold.

## Corrective actions

1. Alert on `db.pool.wait_ms` above 500 ms, not only on error rate. Error rate is
   the consequence and arrives 12 minutes later. **Done.**
2. Lint rule rejecting network calls inside a transaction block. **Done.**
3. Runbook updated to state explicitly that terminating sessions is containment
   and that rollback is the fix. **Done** — see `rb-database-connection-pool`.

## What we are not doing

We are not raising the pool ceiling. A larger pool would have delayed exhaustion
by a few minutes and made the cause harder to see.
