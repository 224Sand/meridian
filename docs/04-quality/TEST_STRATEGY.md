# Test Strategy

**Version:** 1.0 · **Author:** QA Lead · **Date:** 2026-08-20
**Status:** DRAFT — awaiting sign-off

---

## 1. Purpose

Definition of Done (charter §7) requires that every change ship with a test that
fails without it. This document defines what "test" means at each layer, what is
deliberately not tested, and how the quality gates enforce it.

## 2. Test pyramid

| Layer | Scope | Tooling | Runs |
|---|---|---|---|
| **Unit** | Pure logic: router ordering, TTL expiry, cache keying, BM25 scoring, evidence thresholds, risk scoring, spend arithmetic | `pytest` · `vitest` | Every push |
| **Contract** | The BFF↔runtime HTTP contract, asserted from both sides against one schema | `pytest` + generated types | Every push |
| **Integration** | Graph execution end to end against a real database and a stubbed provider | `pytest` + ephemeral Postgres | Every push |
| **Evaluation** | Retrieval and generation quality against fixed golden sets | Eval harness | Every push, non-blocking on the probe suite |
| **End-to-end** | Browser drives a real triage run through both services | Playwright | **Every push, from Sprint 5** |
| **Smoke** | The assembled system executes one real run | `scripts/smoke.py` | **Every push, from Sprint 5** |
| **Governance** | Requirements traced, config valid, no secrets | `scripts/check-*.mjs` | Every push |

The shape is deliberate: the expensive, slow, flaky layers stay thin, and the
properties that actually decide correctness — routing order, refusal thresholds,
approval topology — are tested where they are cheap and deterministic.

**Corrected in Sprint 5.** End-to-end was originally scheduled "Pre-release",
which deferred the only layer that exercises the assembled system to Sprint 8.
Four sprints and 412 passing tests later, the first actual execution of the
system found three defects in ten minutes (D-005, D-006, D-007), one of which
(D-006) was an emergent interaction between two individually correct components
and was unreachable by any unit test.

Definition of Done item 7 — *"Demonstrable: it can be shown working, not
described as working"* — was written at Sprint 0 and enforced zero times across
five sprint reviews. Every review reported delivery; none demonstrated the
system running. The rule existed and the gate did not, which is worse than not
having written the rule.

A thin end-to-end layer that runs is worth more than a thorough one that is
scheduled.

## 3. Determinism policy

Non-deterministic tests are worse than no tests, because they train the team to
re-run rather than investigate. Therefore:

- **Clocks are injected.** No test may call `sleep` to observe a TTL expiring.
- **Providers are stubbed by default.** No test in CI makes a live model call.
- **Seeds are fixed.** The simulated estate and telemetry are generated from a
  fixed seed, so a failing demo is reproducible from its seed alone.
- **The embedder used in tests is the offline deterministic one**, which is why
  ADR-0004 keeps it as a first-class component rather than dead code.

## 4. Tests that must exist

These are named now because each encodes a known, previously-observed failure.

| Test | Asserts | Guards |
|---|---|---|
| `test_approval_node_has_no_outgoing_edges` | The compiled graph has no edge from `await_approval` | ADR-0006 |
| `test_rate_limiter_denies_when_store_unreachable` | Limiter returns deny, not allow, on backend error | ADR-0007 |
| `test_live_call_refused_without_open_budget` | Spend guard raises rather than proceeding | ADR-0007 |
| `test_query_never_returns_foreign_embedding_space` | Retrieval under model A returns no model-B rows | ADR-0005 |
| `test_retrieval_degrades_to_lexical_when_embedder_down` | Result set is labelled degraded, not silently different | ADR-0004 |
| `test_rate_limited_provider_is_disabled_for_ttl_then_reenabled` | Time-boxed disable expires on the injected clock | Router |
| `test_quota_exhausted_provider_is_disabled_permanently` | Distinguished from a transient 429 | Router |
| `test_workflow_completes_when_first_provider_fails` | Failover is real, not configured | FR-011, BR-003 |
| `test_unanswerable_questions_are_refused` | Golden set: all deliberately-unanswerable items refused | FR-006 |
| `test_every_emitted_claim_carries_a_citation` | No uncited claim reaches output | FR-005, BO-1 |
| `test_uncited_claim_escalates_at_retry_ceiling` | Escalation, not emission, at the ceiling | F-8 |
| `test_partial_run_is_never_presented_as_complete` | Budget exhaustion marks the run incomplete | F-7 |
| `test_ip_is_never_stored_raw` | Session rows contain a hash only | Privacy |

## 5. Evaluation suites

Two golden sets, with different purposes.

**`golden/core`** — must pass. Answerable and unanswerable questions over the
corpus. Metrics: groundedness, citation accuracy, refusal correctness,
retrieval recall.

**`golden/probe`** — **expected to warn on every run.** It contains a failure
mode that could not be engineered away: on certain acronym paraphrases, a genuine
question scores below a fabricated one, so no single threshold separates them.
Reporting the warning permanently is the honest treatment. Tuning the threshold
until the suite looked clean would hide a real limitation, and this suite exists
specifically to prevent that from happening quietly.

A warning from `golden/probe` does not fail the build. A *change* in its result
requires a written explanation in the sprint review.

## 6. Definition of Done — enforcement map

| DoD item | Enforced by |
|---|---|
| 1. Acceptance criteria met | PO review at sprint gate |
| 2. Test fails without the change | Reviewer verifies by reverting the change |
| 3. lint / typecheck / test green | CI, blocking |
| 4. No secrets in the diff | `check-secrets.mjs`, blocking |
| 5. Docs updated | `check-docs.mjs` + review |
| 6. Reviewed by a different role | Charter §2, enforced at review |
| 7. Demonstrable | Sprint review demo |

## 7. Not tested, deliberately

Visual pixel-diffing of the motion surface — brittle relative to its value; the
reduced-motion and mobile fallbacks are tested for *presence and comprehension*
instead. Third-party provider behaviour — stubbed at the boundary; we test our
handling of their responses, not their correctness. Load beyond expected traffic
— a single load test establishes the safe envelope; sustained-load engineering
would be scope inflation against NFR-002.

## 8. Defect management

Defects found after a story is accepted are logged in
`docs/04-quality/DEFECT_LOG.md` with severity, discovery context and resolution.
Any defect that reaches a deployed environment gets a postmortem in
`docs/06-operations/postmortems/`, which is rendered publicly on the delivery
surface. Publishing our own defects is the strongest available evidence that the
delivery record is not curated.
