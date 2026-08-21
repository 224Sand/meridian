# Ways of Working — Project Charter

**Project codename:** SandScope *(provisional — see ADR-0002, rename is a single command)*
**Charter version:** 1.0 (SIGNED OFF 2026-08-20)
**Author:** Technical Program Manager
**Date:** 2026-08-20

---

## 1. Why this document exists

This project is delivered as a real product development lifecycle, not as a
coding session. Every unit of work is performed by a **named role**, produces a
**named artifact**, and passes a **named gate**. The lifecycle is itself a
deliverable: `/delivery` on the live site renders these artifacts, so the
process record must be genuine. Nothing here is decoration.

---

## 2. The delivery team

Claude Code operates as a multi-role delivery team. Before every task, the
active role is declared in this format:

```
▸ ROLE ASSUMED:  <role>
▸ TASK:          <ticket-id> — <description>
▸ OUTPUT:        <artifact path>
▸ SIGN-OFF:      REQUIRED (<approver>) | NOT REQUIRED
▸ RISK:          <what could go wrong / blast radius>
```

| Role | Owns | Produces |
|---|---|---|
| **Business Analyst (BA)** | Requirements elicitation, as-is/to-be flows, acceptance criteria | BRD, user stories, process flows, traceability matrix |
| **Product Manager (PM)** | Vision, scope, prioritisation, success metrics | PRD, roadmap, release notes |
| **Technical Program Manager (TPM)** | Charter, sprint plan, RACI, risks, dependencies, status | This charter, sprint plans, risk register, status reports |
| **Scrum Master (SM)** | Ceremonies, impediment removal, velocity | Sprint reviews, retrospectives, burndown |
| **Solutions Architect / FDE** | System design, integration design, deployment topology | Tech spec, ADRs, architecture diagrams, C4 models |
| **UX/UI Designer** | Design system, layout, motion, accessibility | Design tokens, wireframes, motion spec |
| **Software Engineer (DEV)** | Implementation | Source code |
| **SDET** | Automated test suites | Unit, integration, contract, e2e tests |
| **QA Lead** | Test strategy, Definition of Done, defect triage | Test plan, test report, defect log |
| **DevOps / SRE** | CI/CD, environments, observability, incident response | Pipelines, Dockerfile, runbooks, SLOs |
| **Application Security Engineer (AppSec)** | Threat model, SAST, DAST, dependency and secret scanning, supply chain, penetration testing, security release gate | Threat model, security pipelines, SBOM, pen-test findings, security sign-off |
| **Technical Writer** | User-facing and internal documentation | READMEs, API docs, ADR polish |

**Rule:** a role may not sign off its own work. QA Lead signs off DEV. Architect
signs off DEV on design conformance. Product Owner signs off everything that
changes scope.

---

## 3. Your roles

You are not a spectator on this project. Your inputs are classified on receipt
and recorded in the traceability matrix.

| Your role | When it applies | Authority |
|---|---|---|
| **Executive Sponsor** | Budget, vision, go/no-go, release authority | Absolute. Overrides all roles. |
| **Product Owner (PO)** | Backlog priority, scope decisions, accept/reject stories | Owns the backlog. Sole accepter of stories. |
| **Stakeholder / SME** | Domain constraints, business context, external facts | Advisory; becomes a requirement once logged. |
| **UAT Tester** | Reviewing built increments against acceptance criteria | Can reject an increment back to the sprint. |
| **Release Authority** | Production deployment approval | Deployment is blocked without it. |

Every message you send is tagged in reply:

```
◂ INPUT CLASSIFIED: <your role> — <artefact type> → <requirement id>
```

### 3.1 Classification of inputs received to date

| # | Your input | Role | Type | ID |
|---|---|---|---|---|
| 1 | "build a premium, luxury front design website… full fledged backend, agentic AI, FDE Demo, production grade" | Executive Sponsor | Vision statement | VIS-001 |
| 2 | "unnecessary spend on tokens, unnecessary brainstorming is a sin" | Executive Sponsor | Constraint | NFR-001 |
| 3 | "showcase PDLC, SDLC, CI/CD, Agile, Scrum… demo on all these practices" | Stakeholder | Business requirement | BR-002 |
| 4 | "impressive UI like apple.com/iphone-17-pro, black, stock footage from Pexels, seamless animation" | Product Owner | Design requirement | DR-001 |
| 5 | "not just a site to list projects… ultimate technical agentic FDE demo site" | Product Owner | Scope decision | SD-001 |
| 6 | "brand new simulation of a production grade environment with dummy data" | Product Owner | Scope decision | SD-002 |
| 7 | "not building a job applying / tailoring agentic site… solving real problem" | Product Owner | Scope exclusion | SD-003 |
| 8 | Domain selection: Agent Reliability Platform + Incident Intelligence | Product Owner | Scope decision | SD-004 |
| 9 | Architecture selection: BFF + Python agent service | Stakeholder | Architectural constraint | AC-001 |
| 10 | "$0 investment" | Executive Sponsor | Budget constraint | NFR-002 |
| 11 | "Genuinely real" PDLC proof layer | Product Owner | Acceptance criterion | AC-002 |
| 12 | Hugging Face Spaces selected; Pexels key provisioned | Executive Sponsor | Infrastructure decision | INF-001 |
| 13 | "resume bans… not banned for this project as this isn't a resume" | Stakeholder | Constraint removal | CR-001 |
| 14 | "I should be able to easily change the name before coding" | Product Owner | Functional requirement | FR-001 |
| 15 | "frame everything into the PDLC… every role performing action… highly interactive" | Executive Sponsor | Process requirement | PR-001 |
| 16 | Disk reclamation approved | Executive Sponsor | Operational approval | OPS-001 |

---

## 4. Cadence

Work happens in bursts, not calendar days. Pretending otherwise would make the
`/delivery` metrics fiction, and AC-002 forbids fiction. The ceremonies are
therefore mapped to **work sessions**, and this mapping is disclosed on the
`/delivery` page:

| Scrum ceremony | Mapping here |
|---|---|
| Sprint Planning | Opens each sprint. Backlog presented, PO prioritises, capacity agreed. |
| Daily Standup | Per work-session status note: done / next / blocked. |
| Sprint Review (Demo) | Working increment demonstrated to PO. Gate. |
| Sprint Retrospective | What worked, what did not, one committed improvement. Recorded. |
| Backlog Refinement | Continuous; stories must meet Definition of Ready before planning. |

**Velocity is measured in story points against real completion**, not estimated
optimism. Burndown is derived from real commit timestamps.

---

## 5. Sprint plan

| Sprint | Name | Goal | Exit gate |
|---|---|---|---|
| **0** | Inception | Requirements, charter, PRD, BRD, tech spec, ADRs, repo, green CI | **Requirements Sign-off** ✅ |
| **1** | Foundation | Data layer, seeded estate, telemetry, corpus, retrieval | Sprint Review ✅ |
| **2** | Agent Core I | Deterministic router, providers, semantic cache, hybrid retrieval, refusal gate | Sprint Review ✅ |
| **3** | Applied ML & Evaluation Science | Labelled dataset, statistical evaluation, trained classifier, PyTorch re-ranker, ANN benchmark | Sprint Review |
| **4** | Agent Core II | Workload abstraction, orchestrator, governance, approval, spend guard, eval harness | Sprint Review |
| **5** | Console | BFF, SSE streaming, trace viewer, approval UI, session memory | **UAT** |
| **6** | Experience | The `/` Apple-grade surface, motion system, video pipeline | Design Review + UAT |
| **7** | Proof Surfaces | `/delivery`, `/reliability`, `/architecture` | UAT |
| **8** | Hardening & Release | Load test, e2e, threat model review, runbook, observability, deploy | **Release Approval** |

**Re-planned twice, both times on Product Owner input.** 2026-08-20 first split the
agent core across two sprints when a second workload was added. The same day, the
Product Owner observed that the system contained no trained model and no
statistical rigour anywhere — every threshold had been set from the minimum and
maximum of a 20-question set, which is not statistics. Sprint 3 is inserted to
close that, and deliberately runs **before** the orchestrator so the classifier
and the calibrated operating points exist before the graph is built around them.

---

## 6. Definition of Ready

A story enters a sprint only if it has: a clear user-facing outcome, written
acceptance criteria, no unresolved external dependency, an estimate, and a named
owning role.

## 7. Definition of Done

A story is Done only when **all** hold:

1. Code implements the acceptance criteria — no partial credit.
2. Automated tests written and passing, including at least one test that fails
   without the change.
3. `lint`, `typecheck`, `test` all green in CI, on the branch, before merge.
4. No secret, key, or credential in the diff.
5. Documentation updated where behaviour changed.
6. Reviewed by a role other than the implementing role.
7. Demonstrable — it can be shown working, not described as working.

## 8. Quality gates in CI

Every push runs: lint → typecheck → unit → integration → build. A red pipeline
blocks merge. There is no override.

---

## 9. Risk register (initial)

| ID | Risk | P | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | HF Spaces cold start after 48h idle degrades first impression | M | H | 6-hourly warm-ping cron from Vercel; optimistic UI with skeleton states | DevOps |
| R-02 | Free LLM tiers rate-limit under recruiter traffic | H | M | 7-provider deterministic failover + semantic cache + per-IP rate limit | Architect |
| R-03 | Scroll-scrubbed video inflates page weight, kills mobile | M | H | Hard encode budget; mobile poster-frame path; `prefers-reduced-motion` | UX |
| R-04 | Public endpoint abused for free LLM access | M | H | Per-IP rate limit, daily token ceiling, spend guard refuses without open budget | Security |
| R-05 | Scope exceeds available effort | H | M | Strict sprint ordering; ship 0–3 complete before 4–6 rather than half of each | TPM |
| R-06 | `claude_cli` cannot run in deployed container | — | — | **Accepted and designed around.** Registered as local-only provider; renders `UNAVAILABLE — local only` in prod | Architect |
| R-07 | No Docker locally — container untestable before HF build | M | L | Native `uvicorn` dev loop; minimal fully-pinned Dockerfile; HF build is the integration test | DevOps |
| R-08 | Product name undecided; late rename churns code | M | M | Name is build-time config (ADR-0002); rename is one scripted command | Architect |
| R-09 | Host disk at 90%+ | M | M | 1.4 GB reclaimed pre-build; asset budget enforced in CI | DevOps |

---

## 10. Decision log protocol

Any decision that constrains future implementation becomes an **ADR** in
`docs/03-architecture/adr/`. ADRs are immutable once accepted; a reversal is a
new ADR that supersedes, never an edit.

## 11. Traceability

Every requirement (VIS/BR/FR/NFR/DR/AC) maps forward to a story, a test, and a
commit. The matrix lives at `docs/01-requirements/TRACEABILITY.md` and is
rendered on `/delivery`. A requirement with no test is a defect in the process.

---

## 12. Sign-off

| Approver | Role | Status |
|---|---|---|
| Sandeep Chavan | Executive Sponsor | ☑ Signed off 2026-08-20 |
| Sandeep Chavan | Product Owner | ☑ Signed off 2026-08-20 |

*Charter signed off. Sprint 0 opened 2026-08-20. Gate depth elected: FULL ARTIFACT REVIEW.*

## Verifying external claims

An ADR that depends on a third party's pricing, quota or free tier must name the
page the claim was read from and the date it was read. A claim recorded without
that is not a decision record, it is a memory.

This exists because ADR-0003 placed the agent runtime on Hugging Face Spaces
"because it is free", was never checked against the pricing page, and had already
carried three sprints of deployment work by the time Docker Spaces turned out to
require a paid plan. The cost was not the subscription — it was rebuilding the
deployment decision at the release gate.
