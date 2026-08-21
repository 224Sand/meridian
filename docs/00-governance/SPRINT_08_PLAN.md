# Sprint 8 — Hardening & Release

**Sprint goal:** Put it in front of people. Everything until now has run on one
machine; a system that has never been deployed has never been tested.

**Opened:** 2026-08-21 · **Release target:** 1.0.0 ·
**Gate:** **Release Approval** — the only gate in the project the Executive
Sponsor cannot delegate.

**Status: OPEN.** This plan is written at the start of the sprint, which is the
first time in three sprints that has been true.

## Why this sprint exists

The runtime has never been built as a container. The Space image, the publish
script and the Vercel configuration are all written and their *inputs* are
tested — the staged tree is verified at 19MB with no training-venv leakage, the
port assertions pass — but no Docker daemon exists on the development machine,
so **the image itself has never been built**. Northflank's first build is the
first real build, and it should be expected to fail at least once.

## Sprint backlog

| ID | Story | Pts | Acceptance | Status |
|---|---|---|---|---|
| S8-HOST | Agent runtime live on Northflank | 8 | `/healthz` 200 from the public URL; `/v1/*` 401 without a token | **Blocked — IMP-09** |
| S8-VERCEL | Experience layer live on Vercel | 5 | All five routes 200; headers present on a live response | **Blocked — IMP-09** |
| S8-E2E | Pen tests green against the deployed system | 5 | 6/6 against public URLs, not localhost | Blocked on the two above |
| S8-GUARD | Guard-of-the-guard tests (Sprint 7 improvement 1) | 5 | Every check script has a test asserting it fails on known-bad input | Ready |
| S8-OBS | Runbook and observability | 5 | Every fault in the threat model reaches a documented response | Ready |
| S8-THREAT | Threat model review against the deployed surface | 3 | Each of 17 threats re-tested or explicitly deferred with a reason | Blocked on deploy |
| S8-LOAD | Load behaviour within the free tier | 3 | Documented ceiling; the failure mode is refusal, not cost | Ready |

**Committed: 34 points**, of which **21 are blocked** on a credential the sprint
does not hold. Committing blocked work is normally a planning error; it is done
knowingly here because the blocker is external and the sprint has no other
content.

## Definition of Done additions

10. A release claim is verified against the **deployed** URL, not a local one.
    Sprint 7 demonstrated the difference: the pen suite reported 4/6 against a
    runtime that was not running, and one of those four passes was false.

## Explicitly out of scope

New product surface. If a page is missing at this point it ships in 1.1.

## Impediments

### IMP-09 — deployment credentials are not held (BLOCKING)

`VERCEL_TOKEN` must be created by the account owner, and the Northflank service
is configured through its console; neither can
be generated from inside the project. **21 of 34 committed points are blocked
behind them**, and the release gate cannot be reached at all until they exist.
Raised to the Executive Sponsor.

### IMP-10 — the container image has never been built

No Docker daemon on the development machine. Mitigated by testing everything
that can be tested without one — the staged tree, the port contract, the manifest
allowlist — and by expecting the first Space build to fail rather than treating a
failure as a surprise.
