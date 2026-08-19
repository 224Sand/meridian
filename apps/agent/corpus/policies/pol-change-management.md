---
id: pol-change-management
kind: policy
title: Change management and rollback
owner: Platform Edge
---

## Deploy windows

Tier 0 services deploy between 09:00 and 16:00 local to the owning team, Monday
to Thursday. Outside that window a deploy requires an approver from the owning
team who is not the author.

## Rollback is the first response

For any incident correlated with a deploy inside the preceding 60 minutes, the
first action is rollback, not diagnosis. Diagnosis continues after service is
restored, on a system that is no longer degrading.

This is stated as a rule because under pressure the instinct is to understand
first, and understanding takes longer than reverting.

## Change correlation

Every deploy emits a marker event carrying service, version and commit. Incident
triage begins by listing markers in the incident window. A deploy that does not
emit a marker is a policy violation and is treated as one.

## Configuration changes are deploys

A configuration change carries the same rollback expectation as a code change.
Several of the most expensive incidents on record were configuration-only.

## Exceptions

Emergency changes may bypass the window with a named approver, recorded at the
time and reviewed at the next operational review. Retroactive approval is not
permitted.
