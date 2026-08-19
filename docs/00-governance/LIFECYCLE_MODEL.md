# Lifecycle Model — five lenses on the same work

**Version:** 1.0 · **Author:** Technical Program Manager · **Date:** 2026-08-20
**Status:** DRAFT — awaiting Executive Sponsor sign-off

---

## 0. Why five lenses

A single "we did Agile" claim tells a reviewer almost nothing. Five questions
are actually being asked in an interview, and they are different questions:

1. **Where is the product?** — Concept, MVP, Beta, GA. A commercial question.
2. **Where is the engineering?** — Requirements, design, build, test, operate.
3. **Where is the product management?** — Discovery, definition, delivery, growth.
4. **Where is the AI system?** — This one has its own lifecycle, and conflating it
   with the software lifecycle is the single most common mistake in AI delivery.
5. **How is the work organised?** — Sprints, ceremonies, gates.

Every task in this project is labelled against all five. The label appears in the
role announcement before the work starts, and on the delivery surface afterwards.

---

## 1. Product stage

Where the *product* is as a commercial object.

| Stage | Meaning | Sprints |
|---|---|---|
| **Concept** | The problem is articulated; nothing is built | 0 |
| **Prototype** | Load-bearing pieces exist and are proven in isolation | 1 |
| **MVP** | The core loop works end to end for one user journey | 2–3 |
| **Beta** | Complete, usable, publicly reachable, not yet hardened | 4–5 |
| **GA** | Hardened, monitored, operable, released | 6 |
| **Growth** | Post-release iteration driven by observed usage | — |

## 2. SDLC phase

Where the *engineering* is. Phases recur per increment rather than running once.

| Phase | Activity | Sprints |
|---|---|---|
| Requirements | Elicitation, specification, traceability | 0 |
| Design | Architecture, ADRs, data model, contracts | 0, 2 |
| Implementation | Build | 1–5 |
| Testing | Unit, contract, integration, evaluation, e2e | 1–6 |
| Deployment | Release engineering, environments, pipelines | 6 |
| Maintenance | Operation, defect response, postmortems | 6+ |

## 3. PDLC stage

Where the *product management* is.

| Stage | Activity | Sprints |
|---|---|---|
| Ideation | Problem framing, opportunity sizing | 0 |
| Validation | Feasibility, constraints, non-goals | 0 |
| Definition | PRD, personas, success metrics, release plan | 0 |
| Design | Experience design, interaction, motion | 4 |
| Development | Build against the definition | 1–5 |
| Testing / UAT | Acceptance against criteria | 3–6 |
| Launch | Release, positioning, proof surfaces | 6 |
| Growth | Iteration on observed behaviour | — |

## 4. AIDLC — the AI Delivery Lifecycle

**This is the lens most teams are missing, and the reason AI pilots stall.** An
LLM system has a lifecycle that the software lifecycle does not describe: the
software can be correct while the system is ungrounded, unevaluated, and
unbounded in cost. Shipping it is a *separate* set of stages.

| # | Stage | The question it answers | Sprints |
|---|---|---|---|
| **AIDLC-1** | Use-case framing & feasibility | Is this an AI problem? What is the human baseline, and what does being wrong cost? | 0 |
| **AIDLC-2** | Knowledge & data curation | What does the system know, where did it come from, and **what does it deliberately not know?** | 1 |
| **AIDLC-3** | Context & task engineering | How is the task decomposed? What are the tool contracts and prompt contracts? | 2 |
| **AIDLC-4** | Retrieval & grounding design | How is evidence found, and how is every claim tied back to it? | 1–2 |
| **AIDLC-5** | Evaluation design | What is the golden set, what is measured, and what counts as a regression? | 2 |
| **AIDLC-6** | Guardrails & governance | When does it refuse? What requires a human? What bounds the spend? | 2 |
| **AIDLC-7** | Deployment & serving | Routing, caching, failover, latency and cost budgets | 2, 6 |
| **AIDLC-8** | Observability & continuous evaluation | Can any decision be reconstructed? Is quality drifting? | 3, 5, 6 |

### Mapping to NIST AI RMF

The four RMF functions map onto AIDLC rather than replacing it:

| RMF function | AIDLC stages |
|---|---|
| **GOVERN** | Cross-cutting — the ADRs, the risk register, the approval topology |
| **MAP** | AIDLC-1, AIDLC-2 |
| **MEASURE** | AIDLC-5, AIDLC-8 |
| **MANAGE** | AIDLC-6, AIDLC-7 |

### Why AIDLC-2 carries the emphasis it does

"What does it deliberately not know" is written into the stage definition on
purpose. A corpus curated only for coverage produces a system that can never be
shown to refuse correctly, because there is nothing it should refuse. That is why
`corpus/GAPS.md` was authored **before** the evaluation suite rather than after —
the gaps are a design artifact, not an omission.

## 5. Agile cadence

Scrum, adapted honestly to work-session cadence rather than calendar days
(charter §4). Sprint planning, per-session status, sprint review with a working
demonstration, and a retrospective with one committed improvement.

---

## 6. Master matrix

| Sprint | Product stage | SDLC | PDLC | AIDLC | Release |
|---|---|---|---|---|---|
| **0** Inception | Concept | Requirements, Design | Ideation, Validation, Definition | 1 | — |
| **1** Foundation | Prototype | Implementation, Testing | Development | 2, 4 (partial) | 0.1.0 |
| **2** Agent Core I | MVP | Design, Implementation, Testing | Development | 3, 4, 7 | 0.2.0 |
| **3** Agent Core II | MVP | Implementation, Testing | Development | 5, 6 | 0.3.0 |
| **4** Console | MVP | Implementation, Testing | Development, UAT | 8 | 0.4.0 |
| **5** Experience | Beta | Implementation | Design, Development | — | 0.5.0 |
| **6** Proof Surfaces | Beta | Implementation, Testing | Development, UAT | 8 | 0.6.0 |
| **7** Release | GA | Testing, Deployment | Launch | 7, 8 | 1.0.0 |

## 7. Task label format

Every role announcement carries the position of the work:

```
▸ ROLE:   Software Engineer (DEV)
▸ TASK:   S2-03 — Semantic cache
▸ STAGE:  MVP · SDLC Implementation · PDLC Development · AIDLC-7 Serving · Sprint 2
▸ OUTPUT: meridian_agent/router/cache.py
▸ GATE:   QA Lead review
```

The point is not ceremony. It is that a reviewer can see, for any given piece of
work, which lifecycle it belongs to — and notice when a project has run four
sprints of SDLC without ever entering AIDLC-5.
