---
id: rb-stream-consumer-lag
kind: runbook
title: Consumer group lag on events-bus
owner: Data Platform
---

## When this applies

`stream.consumer.lag` grows continuously while `stream.consumer.throughput`
falls. Nothing errors. Error-rate alerting stays green throughout.

## What is happening

Consumers are processing more slowly than producers are publishing. The system
is not broken in any way an error-rate dashboard can see; it is falling behind,
and downstream data goes stale in proportion to the lag.

## Diagnosis

1. Establish whether production rose or consumption fell. Only one of the two is
   ever the cause, and they need opposite responses.
2. If consumption fell, check for a rebalance in the consumer group. Repeated
   rebalances present as sawtooth throughput and are usually caused by a
   processing time that exceeds the session timeout.
3. If production rose, check for a backfill or replay job. A replay publishing at
   full speed will outrun any steady-state consumer configuration.
4. Check `pipeline.freshness_lag_s` on downstream batch services to size the
   business impact. Lag alone does not say who is affected.

## Remediation

- For a rebalance loop, raise `max.poll.interval.ms` above observed processing
  time, or reduce `max.poll.records` so a batch completes inside the interval.
- For a genuine volume increase, add consumer instances up to the partition
  count. Beyond partition count, additional instances idle and change nothing.
- For a replay, throttle the replay rather than scaling consumers to absorb it.

## Escalation

Page Data Platform on-call when lag exceeds 1,000,000 messages or when
`pipeline.freshness_lag_s` exceeds 900 on any Tier 0 or Tier 1 consumer.

## Related

`rb-timeout-and-retry` · `pol-data-freshness`

## Common misdiagnosis

**Assumed healthy because nothing is erroring.** Error rate stays flat through
the entire fault. Any alerting built only on error rate will report a healthy
system while downstream data goes progressively stale.

**Mistaken for a consumer fault when production rose.** Adding consumers to
absorb a replay makes the replay finish faster and does nothing about the
freshness breach. Establish which side moved before responding.

**Scaled past the partition count.** Consumers beyond the partition count sit
idle. Throughput does not improve, and the extra instances make the next
rebalance slower.
