---
id: pol-change-risk-classification
kind: policy
title: Change risk classification
owner: Platform Edge
---

## Purpose

Every proposed production change is classified before it is scheduled. The
classification determines who must approve it and what evidence must accompany
it. Classification is done on the change's blast radius and reversibility, never
on how confident the author feels.

## Risk levels

**Critical.** Touches a Tier 0 service AND is not reversible by a rollback of a
single deploy. Includes schema changes that drop or rewrite data, changes to
authentication or authorisation, certificate and key rotation on public
listeners, and any change to a connection-pool or timeout ceiling on a Tier 0
path. Requires approval from the owning team and Platform Edge, plus a written
rollback plan that does not depend on the change itself.

**High.** Touches a Tier 0 or Tier 1 service and is reversible by rollback.
Includes application deploys on the checkout and payment paths, cache key
namespace changes, and consumer group configuration. Requires an approver from
the owning team who is not the author.

**Medium.** Touches a Tier 2 service, or a Tier 1 service outside the
synchronous request path. Requires review, not approval.

**Low.** Tier 3 only, or documentation and observability changes with no runtime
effect. Self-approved.

## Automatic escalation

A change escalates one level, automatically and without discussion, when any of
the following holds:

- It modifies a limit, ceiling or timeout rather than logic. These changes look
  small and alter failure behaviour under load, which is precisely when nobody
  is reading the diff.
- A change to the same service was rolled back within the previous 14 days.
- It lands outside the deploy window defined in `pol-change-management`.
- The service it touches is currently in an open incident.

## Evidence required

Critical and High changes must state, in the proposal: what fails if this is
wrong, how that failure is detected, and how long rollback takes. A proposal
that cannot answer the second question is not ready, because a change nobody can
detect failing is a change nobody can roll back in time.

## What this policy does not cover

Emergency changes during an active incident. Those are governed by the incident
commander and reviewed afterwards, not classified in advance.
