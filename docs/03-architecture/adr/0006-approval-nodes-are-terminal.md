# ADR-0006 — Human-approval nodes are terminal by construction

**Status:** Accepted · **Date:** 2026-08-20 · **Deciders:** Solutions Architect, Product Owner (BO-4, FR-007)

## Context
In prior work on a multi-agent system, a human-approval node had an outgoing edge
into a registration node. The graph therefore proceeded to register the item
regardless of what the reviewer actually answered. The approval step existed,
rendered, collected a decision, and controlled nothing. It read as governance and
functioned as a formality — the worst possible failure mode for a control, because
it consumes the reviewer's attention while providing no protection.

## Decision
`await_approval` has no outgoing edge. Reaching it ends the run. A human decision
creates a **new** run that carries the approval record as input.

## Consequences
**Positive.** Auto-proceed is impossible by graph topology, not by careful coding.
The approval record is a first-class row with identity and timestamp, satisfying
Sofia's audit requirement. Continuation runs are independently traceable.

**Negative.** Two runs per approved incident instead of one; the UI must join them
into a single narrative for the user.

**Verification.** A regression test enumerates the compiled graph's edges and
fails if any edge originates at `await_approval`. The test was written to fail
against the defective topology before the correct one existed.
