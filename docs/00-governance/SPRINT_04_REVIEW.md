# Sprint 4 — Review & Retrospective

**Sprint:** 4 — Agent Core II · **Closed:** 2026-08-20 · **Release:** 0.4.0

| Lens | Position |
|---|---|
| Product stage | MVP |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| AIDLC | 3 Context · 5 Evaluation · 6 Guardrails |

---

## 1. Sprint goal

> One orchestration graph runs two workloads under governance. A risky action
> cannot execute without a human decision, and no model call can happen without
> a budget open first.

**Met.** All six stories. 412 tests. CI green including the evaluation step.

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S4-WORKLOAD | Workload abstraction | 5 | Triage and change review as data on one graph |
| S4-GRAPH | Orchestrator | 8 | 12 nodes; `await_approval` terminal by topology |
| S4-ADJUDICATE | Grounding adjudicator | 5 | One cheap call, ambiguous band only |
| S4-CITE | Citation extraction | 5 | Sentence-level; fabricated markers preserved |
| S4-SPEND | Spend guard | 5 | Refuses without an open budget; priced pre-flight |
| S4-EVAL | Evaluation suites | 8 | `core` blocks, `probe` warns and never blocks |

**Velocity: 36/36.**

## 3. The invariants, and how they are proved

**`await_approval` is terminal by topology.** The test enumerates the
**compiled** graph's edges rather than reading the builder, because reading the
builder only proves what the author meant. A second test asserts the node is
reachable: a terminal node nothing reaches is dead code, not a control.

**No model call without an open budget.** `Dependencies.complete()` is the only
path that spends a token, which is what makes one guard sufficient. The
reservation is taken before the call and against `max_tokens_out` rather than an
expected length — a reservation sized to the expected response is wrong exactly
when a response runs long.

**Free tiers are priced at their paid rate.** A guard calibrated to zero teaches
nothing and stops guarding the day a free tier ends. An unknown provider is
priced at the most expensive rate present, so it cannot be cheap by default.

**Risk is scored deterministically.** Asking a model how risky its own
suggestion is produces a number that correlates with how confidently it phrased
the suggestion. `change_review` additionally enforces the corpus's own
automatic-escalation rule in code, so enforcement does not depend on the model
having read the policy it is being asked to cite.

**Citations attach to sentences.** A model that puts one `[1]` at the end of six
sentences has cited one and asserted five. Markers pointing outside the evidence
are recorded with `resolved=False` rather than dropped: a fabricated citation
looks like grounding, so it has to survive into the record where a check can see
it.

## 4. Evaluation, measured

`golden/core` — blocking, 5/5:

| Check | Result |
|---|---|
| Sample large enough | 396 answerable / 319 unanswerable |
| False-answer rate | 15/319 → **0.047 [0.029, 0.076]** |
| False-refusal rate | 9/396 → **0.023 [0.012, 0.043]** |
| Ambiguous never permits answering | 0 leaked |
| Every fault reaches its runbook | none unreachable |

`golden/probe` — warns, never blocks, 3 warnings all expected: the classes still
overlap (answerable floor 0.49 against unanswerable ceiling 10.68), value-absent
questions still score 8.85 on retrieval alone, and the gold chunk ranks first
only 54% of the time.

The false-answer check asserts the **upper bound** of the Wilson interval rather
than the point estimate. A point estimate that happens to land inside budget is
not evidence the system is inside budget — which is exactly how Sprint 2
reported a 56.6% rate as zero.

## 5. Retrospective

**What worked.** The Sprint 3 improvements were carried into the Definition of
Done as binding items rather than advice, and one of them paid immediately:
asserting an anchor exists before a text replacement caught two more silent
no-ops this sprint. Both would have reported success.

`sample_is_large_enough` as a *check* rather than a lesson. Sprint 3 established
that a written-down lesson does not prevent its own recurrence; this sprint the
same rule runs on every push.

**What CI caught that nothing else could.** Loading the corpus under a second
embedding model destroyed the first model's vectors — 87 rows where ADR-0005
requires 174 — because chunk deletion cascades to `chunk_embedding`. The
destructive-test guard skips those tests against any managed host, so a local run
against Neon **skipped them entirely and reported green**. The pgvector container
is the only place that path is exercised.

The guard did its job in both directions: it prevented an accidental wipe of the
live database, and reproducing the bug deliberately required setting
`SandScope_ALLOW_DESTRUCTIVE_TESTS=1` on purpose.

**What did not.** A test failed during the sprint because the evidence gate
correctly refused a weak query, and the first instinct was to read it as a bug in
the graph. It was a bug in the test: it used a thin query and therefore tested
the evidence gate a second time instead of the risk gate it was named for.

**Improvement committed for Sprint 5.** A test asserts one thing. Where a test's
name promises a specific gate, its fixture must reach that gate — otherwise a
change upstream silently repurposes the test without failing it.

## 6. Gate

Sprint Review — pending Product Owner.
