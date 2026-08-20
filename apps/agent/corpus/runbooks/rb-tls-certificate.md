---
id: rb-tls-certificate
kind: runbook
title: TLS certificate expiry at the edge
owner: Platform Edge
---

## When this applies

`tls.handshake_failures_per_s` goes from zero to its full rate within a single
sample interval, and `tls.certificate_days_remaining` has crossed zero.

## What is happening

A certificate has expired. Clients refuse the handshake. Failure is total and
instantaneous, which is the signature that distinguishes it from every capacity
problem: capacity degrades along a curve, expiry is a step.

## Diagnosis

1. Read `tls.certificate_days_remaining`. Below zero confirms it outright and no
   further diagnosis is needed.
2. If the value is above zero, the failures are not expiry. Check the chain
   instead: an intermediate certificate can expire while the leaf remains valid,
   and the leaf's own expiry metric will not show it.
3. Confirm which listener is affected. Internal mesh certificates and public edge
   certificates rotate on different schedules and rarely fail together.

## Remediation

- Deploy the renewed certificate. There is no mitigation short of this; there is
  nothing to tune and nothing to scale.
- If automated renewal exists and did not fire, treat the renewal failure as its
  own incident once service is restored. A renewal path that failed silently will
  fail silently again.

## Prevention

Alert on `tls.certificate_days_remaining` below 21, not on handshake failures.
By the time handshakes fail the outage has already happened, so alerting on the
failure is alerting on the consequence.

## Escalation

Page Platform Edge immediately. Any expiry on a Tier 0 listener is Severity 1
regardless of measured traffic impact.

## Related

`pol-incident-severity`

## Common misdiagnosis

**Mistaken for a capacity problem.** Capacity degrades along a curve. Expiry is a
step: total failure within one sample interval. The shape settles it without any
further investigation.

**Leaf certificate checked, chain ignored.** An expired intermediate produces
identical handshake failures while `tls.certificate_days_remaining` on the leaf
stays positive. A positive leaf value does not clear this fault.

**Alerted on the wrong metric.** Alerting on handshake failures means alerting
after the outage has already happened. The actionable alert is on days
remaining.
