# ADR-0007 — Rate limiting and the spend guard fail closed

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Security Engineer, Solutions Architect (NFR-004, R-04)

## Context
The service is publicly reachable and calls paid-capable model providers. The
common default — allow the request when the rate-limit store is unreachable — is
chosen so that an infrastructure blip does not degrade user experience. Here that
default converts a Redis outage into an unbounded-cost incident, and the endpoint
into free LLM capacity for whoever finds it.

## Decision
When Redis is unreachable, rate limiting **denies**. When no budget is open, the
spend guard **refuses** the live model call. Every call is priced at worst case
before it is issued; actual cost is written to the ledger afterwards.

## Consequences
**Positive.** The worst outcome of a dependency failure is unavailability, not
unbounded spend. Cost is bounded before it is incurred rather than reconciled
after.

**Negative.** A Redis outage takes the demo down. Given NFR-002 and a demo
workload, that is the correct trade; it would not be for a revenue-bearing
service, and that difference is the point of recording it here.

**Verification.** Unit tests simulate an unreachable limiter and assert denial,
and assert that a live call with no open budget raises rather than proceeds.
