---
id: rb-database-connection-pool
kind: runbook
title: Connection pool exhaustion on orders-db
owner: Data Platform
---

## When this applies

`db.pool.available` reaches zero and `db.pool.wait_ms` climbs above 500 ms while
request volume is unchanged. Callers report timeouts that all begin within the
same minute.

## What is happening

Callers are holding connections longer than the pool recycles them. This is
almost never a traffic problem: the pool is sized for concurrency, not for
requests per second, so it saturates when hold time rises, not when volume does.

## Diagnosis

1. Confirm `db.active_connections` is at the configured ceiling of 100. If it is
   below the ceiling, the pool is not the constraint and this runbook does not apply.
2. Compare `db.pool.wait_ms` against `db.query.p99_ms`. If wait time rose before
   query time, the pool is the cause. If query time rose first, the pool is a
   symptom and the cause is query performance — see `rb-query-amplification`.
3. Identify the holding caller with `pg_stat_activity`, ordered by
   `state_change`. Long-lived `idle in transaction` sessions are the usual answer.
4. Check whether a deploy landed in the preceding 30 minutes. A transaction
   boundary moved outward is the most common introduction of this fault.

## Remediation

- Terminate sessions idle in transaction beyond 60 seconds. This restores
  service immediately and does not fix the cause.
- If a deploy correlates, roll back that deploy. Do not raise the pool ceiling
  to absorb a regression; a larger pool exhausts more slowly and hides it longer.
- Raise the ceiling only when concurrency has genuinely grown, and only with a
  matching increase in the database's own `max_connections`. Raising the client
  pool alone moves the failure into the database.

## Escalation

Page Data Platform on-call if `db.pool.available` remains at zero for more than
10 minutes after terminating idle transactions.

## Related

`rb-query-amplification` · `rb-timeout-and-retry` · `pm-2026-05-orders-db-saturation`

## Common misdiagnosis

**Mistaken for a traffic spike.** Request rate is flat in every real instance of
this fault. If request rate rose, the pool is a symptom of load and the response
is capacity, not rollback.

**Mistaken for query amplification.** Both raise `db.pool.wait_ms`. The
discriminator is `db.queries_per_request`: unchanged here, sharply higher there.
Check it before choosing a response, because the two have opposite remedies.

**Mistaken for a database outage.** The database is healthy throughout. It is
answering every query it receives; the callers cannot get a connection to send
one. `db.query.p99_ms` stays normal, which is the tell.
