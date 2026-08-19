---
id: rb-memory-pressure
kind: runbook
title: Heap growth and collection pauses
owner: Platform Edge
---

## When this applies

`process.memory.rss_mb` climbs monotonically across hours, `runtime.gc.pause_ms`
lengthens with it, and `process.restarts` becomes non-zero.

## What is happening

Memory is being retained that should be released. Collection runs more often and
takes longer as the live set grows, so latency degrades before any restart occurs.

## Diagnosis

1. Confirm the climb is monotonic across restarts. A sawtooth that returns to
   baseline on each restart is a leak. A flat line at a higher level after a
   deploy is a legitimate increase in working set, not a leak.
2. Correlate the start of the climb with a deploy. The restart resets the graph,
   so widen the window to at least 24 hours or the trend is invisible.
3. Capture a heap dump before the next restart. After the restart the evidence
   is gone.
4. Compare pause time against the pause budget. Latency degrades from pause time
   long before memory is exhausted, so users feel this well before it alerts.

## Remediation

- Roll back the correlated deploy. This is the fastest path to service and
  preserves the heap dump for diagnosis.
- Do not raise the memory limit as a first response. It extends time-to-restart
  and lengthens pauses, which makes the user experience worse while appearing to
  fix the alert.
- Where rollback is not possible, schedule rolling restarts at a fixed interval
  shorter than time-to-exhaustion, and record it explicitly as a temporary
  measure with an owner and a date.

## Escalation

Page the owning team when `runtime.gc.pause_ms` exceeds 1000 or when restarts
exceed three in one hour.

## Related

`rb-timeout-and-retry` · `pm-2026-07-fraud-scoring-restart-loop`
