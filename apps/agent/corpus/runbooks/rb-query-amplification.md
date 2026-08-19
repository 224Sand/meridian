---
id: rb-query-amplification
kind: runbook
title: Query amplification after deploy
owner: Commerce
---

## When this applies

`db.queries_per_request` rises sharply while request volume is flat.
`db.query_rate` rises in proportion. Latency follows.

## What is happening

A change replaced a batched read with a per-item read. Cost now scales with
result size rather than with traffic, so the fault appears on large result sets
first and is invisible in any test using small fixtures.

## Diagnosis

1. Confirm request volume is unchanged. If requests also rose, this is load, not
   amplification, and the response is different.
2. Divide `db.query_rate` by request rate. A ratio that moved from single digits
   to tens is conclusive.
3. Identify the deploy at the inflection point. Amplification is almost always
   introduced by a change, not by drift.
4. Inspect the query log for the same statement repeating with different
   parameters inside one request. That is the fingerprint.

## Remediation

- Roll back the correlated deploy.
- Where rollback is not available, restore batching for the specific access path
  identified in the query log.
- Do not scale the database to absorb it. The amplification factor grows with
  result size, so capacity bought today is consumed by tomorrow's larger page.

## Escalation

Page Commerce on-call. Page Data Platform additionally if `db.pool.wait_ms`
exceeds 500 ms, since pool exhaustion will follow.

## Related

`rb-database-connection-pool`
