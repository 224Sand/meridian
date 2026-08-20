# Product Requirements Document

**Product:** MERIDIAN *(name provisional — ADR-0002)*
**Version:** 1.0 · **Author:** Product Manager · **Date:** 2026-08-20
**Status:** DRAFT — awaiting Product Owner sign-off
**Upstream:** [BRD.md](./BRD.md)

---

## 1. Vision

> **The control plane for AI agents that operate production systems.**

An agent that touches production must be as accountable as the humans who do.
MERIDIAN is the layer that makes it so: every action routed deterministically,
cached semantically, grounded with citations, evaluated against a fixed set,
traced end to end, priced per call, and gated on human approval when it crosses
a risk line.

The product is demonstrated through a single flagship workload — **production
incident triage** — because that is where the four questions from the BRD are
asked most urgently and answered worst.

## 2. Positioning

| | |
|---|---|
| **For** | Platform and SRE teams putting LLM agents into production operations |
| **Who** | Cannot get production sign-off because agent behaviour is unaccountable |
| **MERIDIAN is** | An agent control plane |
| **That** | Makes grounding, cost, safety and behaviour observable and enforceable |
| **Unlike** | Prompt-level observability tools that record what happened after the fact |
| **MERIDIAN** | Enforces the constraints at execution time, then proves it did |

## 3. Product principles

1. **Evidence over assertion.** A claim without a citation is a defect, not a style choice.
2. **Refusal is a feature.** "I don't know" beats a confident wrong answer for every persona in the BRD.
3. **Determinism before intelligence.** If a typed rule can decide it, no model call is made.
4. **The limitation stays visible.** Where a problem could not be engineered away, it is surfaced, not tuned until it looks clean.
5. **Nothing is claimed that cannot be shown.** Applies to the product and to its own delivery record equally.

## 4. Feature set

### 4.1 Incident Intelligence Console — the flagship workload

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-002** | Simulated production estate | Services, dependencies and telemetry that behave plausibly, seeded deterministically so a demo is reproducible | Must |
| **FR-003** | Incident feed | Incidents fire on a seeded schedule and on visitor demand | Must |
| **FR-004** | Live triage run | Agent triages a selected incident; reasoning, tool calls and retrieval stream to the client as they happen | Must |
| **FR-005** | Cited evidence panel | Every claim links to the retrieved chunk that supports it; unsupported claims are marked, not hidden | Must |
| **FR-006** | Explicit refusal | Where retrieval does not support an answer, the agent says so and stops | Must |
| **FR-007** | Human approval gate | Remediations above a risk threshold block; approval is terminal and cannot auto-proceed | Must |
| **FR-008** | Session memory | The agent recalls earlier turns and prior incidents in the session; memory contents are visible to the user | Should |
| **FR-009** | Postmortem drafting | Agent drafts an RCA document from the run, grounded and cited | Could |

### 4.1b Change Risk Review — the second workload

Added at the Sprint 1 review (Product Owner). It exists to prove the central
claim: the control plane is workload-agnostic. Change review runs the *same*
orchestration graph as triage — classify, retrieve, assess evidence, hypothesise,
verify citations, propose, risk-gate — with a different task profile. A second
graph would have been easier and would have proven nothing.

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-025** | Change risk review workload | Agent assesses a proposed production change against policy and incident history, cites the policy clause and the precedent, and gates on approval by risk level | Should |

### 4.2 Reliability surfaces — the control plane made visible

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-010** | Deterministic router | Ordered multi-provider failover with time-boxed disabling of failing providers; live health per provider | Must |
| **FR-011** | Provider failure injection | Visitor can force a provider failure and watch the workflow survive it | Must |
| **FR-012** | Semantic cache | Near-duplicate requests served from cache; hit rate, threshold and spend avoided are shown | Must |
| **FR-013** | Execution trace viewer | OpenTelemetry waterfall per run: spans, provider hops, cache outcome, tokens, latency, cost | Must |
| **FR-014** | Cost attribution & spend guard | Per-run cost; live calls refused unless a budget is open; every call priced at worst case pre-flight | Must |
| **FR-015** | Evaluation harness | Golden-set results across groundedness, citation accuracy, refusal correctness | Should |
| **FR-016** | Known-limitation probe set | A second golden set that reports a warning on every run, documenting a failure mode that was not engineered away | Should |

### 4.2b Applied machine learning and evaluation science

Added 2026-08-20 on Product Owner observation. Until this point the system
contained no trained model and no statistical rigour: every threshold had been
set from the minimum and maximum of a 20-question set. That is a defensible
starting point and it is not evidence that any threshold is correct.

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-026** | Labelled evaluation dataset | ~600 questions with labels true by construction, split by document to prevent leakage | Must |
| **FR-027** | Statistical evaluation of the refusal gate | ROC and precision-recall curves, operating point by Youden's J, bootstrap confidence intervals, McNemar's test between configurations, power analysis for dataset size | Must |
| **FR-028** | Trained evidence-sufficiency classifier | Calibrated probabilistic classifier over engineered retrieval features, measured against the heuristic baseline and reported either way | Must |
| **FR-029** | Cross-encoder re-ranker | Fine-tuned offline in PyTorch, exported to ONNX, served without the training framework | Should |
| **FR-030** | Approximate nearest neighbour benchmark | pgvector HNSW against IVFFlat, exact search and a managed vector store, on recall@k, latency percentiles, build time and memory | Should |

### 4.3 Experience surface

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-017** | Cinematic product narrative | Black canvas, scroll-scrubbed video, sticky pinned scenes, motion that carries meaning rather than decorating | Must |
| **FR-018** | Reduced-motion and mobile paths | Full comprehension without motion; poster-frame path on constrained devices | Must |
| **FR-019** | Interactive architecture view | System diagram with request lifecycle and failure modes | Should |

### 4.4 Delivery proof surface

| ID | Feature | Description | Priority |
|---|---|---|---|
| **FR-020** | Live CI/CD status | Real GitHub Actions runs, real test counts, rendered from the GitHub API | Must |
| **FR-021** | Requirements traceability view | Every requirement mapped to a story, a test and a commit | Must |
| **FR-022** | Sprint and velocity record | Derived from real commit history, with the work-session cadence mapping disclosed | Must |
| **FR-023** | Decision record | ADRs rendered with their context and consequences | Should |
| **FR-024** | Postmortems | Real defects hit during this build, written up as RCAs | Should |

## 5. User stories

**Marcus (SRE)**
- As an on-call engineer, I want the agent to show me the runbook section it used, so I can verify the hypothesis rather than trust it.
- As an on-call engineer, I want the agent to tell me when the evidence does not cover the question, so I do not act on a fabrication at 3am.
- As an on-call engineer, I want a risky remediation to wait for my approval, so an agent cannot act on production on my behalf.

**Dana (AI Platform Engineer)**
- As a platform engineer, I want to force a provider outage, so I can prove the failover works before it happens for real.
- As a platform engineer, I want to see cache hit rate and the spend it avoided, so I can justify the caching layer.
- As a platform engineer, I want golden-set results per change, so I can tell improvement from regression.

**Priya (VP Engineering)**
- As a VP, I want the cost of a single run visible, so variable spend is a number and not a surprise.
- As a VP, I want one view of reliability, spend and governance posture, so I can approve or decline deployment defensibly.

**Sofia (Risk & Compliance)**
- As a compliance lead, I want the complete trace of any run retained, so a decision can be reconstructed months later.
- As a compliance lead, I want approvals recorded against an identity and a timestamp, so accountability is not verbal.

**Visitor (technical reviewer)**
- As a reviewer, I want to verify the CI and tests are real, so I can distinguish this from a mockup.

## 6. Success metrics

| Metric | Target | Measured by |
|---|---|---|
| Claims carrying a citation or explicit no-evidence marker | 100% | Eval harness, per run |
| Workflow completion under single-provider failure | 100% | Injected-failure integration test |
| Unanswerable questions correctly refused | 100% of golden set | Eval harness |
| Answerable questions incorrectly refused | Reported, not hidden | Eval harness |
| Semantic cache hit rate on repeat traffic | > 40% | Cache telemetry |
| Live model call without an open budget | 0 | Spend guard, enforced in code |
| First meaningful paint, cold, 4G | < 2.5 s | Lighthouse in CI |
| Requirements with no linked test | 0 | `check-docs` gate, blocking |

## 7. Release plan

| Release | Contents | Gate |
|---|---|---|
| **0.1.0** Foundation | Schema, seeded estate, telemetry, corpus, retrieval | Sprint Review ✅ |
| **0.2.0** Agent Core I | Router, providers, semantic cache, hybrid retrieval, refusal | Sprint Review ✅ |
| **0.3.0** Applied ML | Labelled dataset, statistical evaluation, trained classifier, re-ranker, ANN benchmark | Sprint Review |
| **0.4.0** Agent Core II | Workloads, orchestrator, governance, approval, spend, evals | Sprint Review |
| **0.5.0** Console | BFF, streaming triage, trace viewer, approval, memory | UAT |
| **0.6.0** Experience | Narrative surface, motion system | Design Review + UAT |
| **0.7.0** Proof | Delivery, reliability and architecture surfaces | UAT |
| **1.0.0** Release | Hardened, load-tested, deployed | Release Approval |

If effort runs short, releases ship **in order and complete**. A half-finished
0.4.0 alongside a half-finished 0.3.0 is worse than 0.3.0 alone (R-05).

## 8. Explicitly out of scope

Real customer data. Production authentication. Billing. Job-application or
resume tooling (**SD-003**). Auto-execution of remediation against any real
system — the agent proposes; a human disposes, always. Native mobile apps. Any
paid infrastructure (**NFR-002**).

## 9. Open questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q-1 | Final product name | Product Owner | Sprint 4 (branding assets) |
| Q-2 | Whether the postmortem drafter (FR-009) survives scope pressure | Product Owner | Sprint 3 review |

Both are tracked, neither blocks Sprint 1.
