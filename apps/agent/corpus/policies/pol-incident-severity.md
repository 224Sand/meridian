---
id: pol-incident-severity
kind: policy
title: Incident severity and paging policy
owner: Platform Edge
---

## Severity definitions

**Severity 1** — a Tier 0 service is unavailable or materially degraded for
customers. Pages immediately, at any hour. Requires an incident commander and a
published postmortem within five working days.

**Severity 2** — a Tier 1 service is degraded, or a Tier 0 service is degraded
without customer-visible failure. Pages during business hours; outside them it
pages only if a Tier 0 consumer is affected. Postmortem required.

**Severity 3** — a Tier 2 service is degraded, or a Tier 3 service has failed.
Ticketed, not paged. Postmortem at the owning team's discretion.

**Severity 4** — no service impact. Tracked for trend only.

## Paging rules

The owning team of the **root** service is paged, not the team that observed the
symptom. Where the root is not yet established, the team owning the most
customer-facing affected service is paged and holds it until the root is found.

Certificate expiry on any Tier 0 listener is Severity 1 regardless of measured
traffic impact, because measured impact at the moment of detection is not a
predictor of impact five minutes later.

## Severity is set on impact, not on cause

An interesting cause does not raise severity and a boring one does not lower it.
Severity is a statement about who is affected right now.

## Escalation timers

Severity 1 unresolved after 30 minutes escalates to the engineering manager on
call. Severity 1 unresolved after 90 minutes escalates to the director on call.
These timers run from declaration, not from the start of the impact.
