---
id: rb-change-rollback
kind: runbook
title: Rolling back a production change
owner: Platform Edge
---

## When this applies

An incident correlates with a deploy or configuration change in the preceding 60
minutes. Correlation is enough; causation does not need to be established first.

## Why rollback comes before diagnosis

Under pressure the instinct is to understand the fault before undoing it.
Understanding reliably takes longer than reverting, and every minute spent
understanding is a minute the system spends degrading. Diagnose afterwards, on a
system that has stopped getting worse.

## Procedure

1. List change markers in the incident window. Every deploy emits one; a service
   with no marker either did not deploy or is violating `pol-change-management`.
2. Identify the marker nearest the onset of the primary signal. Onset, not
   alert: alerts lag.
3. Redeploy the previous version. For a configuration change, restore the
   previous value rather than setting what the value "should" be.
4. Confirm recovery on the primary signal, not on the alert. Alerts clear on a
   delay and can clear while the fault persists.
5. If the primary signal does not recover within two observation intervals, the
   change was not the cause. Restore the rolled-back version and continue
   diagnosis, because leaving a system on an older version for no reason is its
   own risk.

## When rollback is not available

Schema changes that dropped or rewrote data, and any change already consumed by
a downstream system, cannot be undone by redeploying. This is why
`pol-change-risk-classification` requires a written rollback plan for Critical
changes that does not depend on the change itself.

## After recovery

The rolled-back change is not resolved. It is unshipped. It re-enters review at
one risk level higher, per the automatic escalation rule.

## Related

`pol-change-management` · `pol-change-risk-classification` ·
`arch-deployment-and-change-flow` · `pm-2026-04-pricing-config-rollout`
