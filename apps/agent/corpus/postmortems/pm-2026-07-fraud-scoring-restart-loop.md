---
id: pm-2026-07-fraud-scoring-restart-loop
kind: postmortem
title: "fraud-scoring restart loop masked a memory leak for nine days"
date: 2026-07-11
severity: 2
---

## Summary

A memory leak in fraud-scoring caused restarts roughly every four hours for nine
days before anyone noticed. Each restart reset the memory graph, so the
underlying trend was invisible on every dashboard anyone opened.

## Impact

Payment authorisation p99 rose during the pause windows preceding each restart.
No requests failed. The degradation was real and continuous and went unreported
by users for nine days.

## Timeline

- **Jul 2** Deploy introduces a cache of scoring features keyed by account, with
  no eviction policy.
- **Jul 2 – Jul 11** Restarts occur roughly every four hours. The platform
  restarts the process automatically and records it as a normal event.
- **Jul 11 09:40** An engineer investigating unrelated latency widens the memory
  graph to 14 days and sees the sawtooth.
- **Jul 11 11:20** Heap dump captured before a scheduled restart.
- **Jul 11 14:05** Eviction policy deployed. Memory flattens.

## Root cause

An unbounded in-memory feature cache. Growth was bounded only by the process
memory limit.

## What went wrong beyond the code

Restarts were being counted and not alerted on. A process restarting six times a
day was indistinguishable, in the platform's own view, from a healthy deploy
cadence. The default dashboard window was four hours, which is shorter than the
leak's period — so the graph that would have shown it was never displayed at a
width where it was visible.

## Corrective actions

1. Alert on `process.restarts` above two per hour. **Done.**
2. Default memory dashboard window widened to 7 days. **Done.**
3. Runbook now states explicitly that the graph must be widened past the restart
   interval or the trend cannot appear. **Done** — see `rb-memory-pressure`.

## What we still do not know

We have not established why the platform's restart events were not surfaced to
the owning team's alerting at any point in nine days. That routing question is
open and is tracked outside this postmortem.
