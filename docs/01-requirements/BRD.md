# Business Requirements Document

**Product:** SandScope *(name provisional — ADR-0002)*
**Version:** 1.0 · **Author:** Business Analyst · **Date:** 2026-08-20
**Status:** DRAFT — awaiting Product Owner sign-off

---

## 0. Nature of this document

SandScope is a **demonstration product built to production standards on
synthetic data**. The engineering is real: the services, the failover, the
retrieval, the evaluation, the tests, the pipeline and the deployment all
function. The *customers* are simulated.

This is stated plainly at the top of the document, and it is stated on the live
site, because the alternative is a reader discovering it themselves and
discounting everything else. A simulation that admits it is a simulation is
evidence of engineering judgement. One that pretends otherwise is evidence of
nothing.

---

## 1. Business context

Organisations are moving LLM agents from pilots into production operations —
triaging incidents, drafting remediations, answering on-call questions. The
capability arrived faster than the controls did.

The pattern repeats across every one of these deployments:

- The agent produces confident output. Nobody can show what it was grounded in.
- It calls one model provider. That provider rate-limits, and the workflow stops.
- Spend is discovered at the end of the billing cycle rather than at the call.
- An agent proposes an action against production. No one defined who approves it.
- The team cannot answer "did it get better or worse after we changed the prompt?"

These are not model problems. They are **control-plane** problems, and they are
the reason otherwise-working agent pilots do not get a production sign-off.

## 2. Problem statement

> An organisation deploying an LLM agent into production operations cannot
> currently answer four questions with evidence: **is it grounded, is it safe,
> what did it cost, and what did it actually do?** Without answers, the agent
> either ships unaccountably or does not ship at all.

## 3. Stakeholders

| Stakeholder | Interest | Success looks like |
|---|---|---|
| **VP Engineering / Platform** (economic buyer) | Accountable for reliability, spend and the decision to deploy | Can approve agent deployment with an auditable basis |
| **SRE / On-call engineer** (primary user) | Wants triage speed without inheriting risk | Reaches a defensible hypothesis faster than unaided |
| **AI Platform Engineer** (power user) | Owns routing, prompts, retrieval, evals | Can change configuration and see the measured effect |
| **Risk & Compliance** (gatekeeper) | Needs an audit trail and evidence of grounding | Can reconstruct any decision after the fact |
| **Finance** (constraint holder) | Controls variable model spend | Spend is bounded before it is incurred, not after |

## 4. Personas

**Marcus — Site Reliability Engineer.** Carries the pager. Under time pressure at
3am, with five dashboards open. Will use an agent that shows its evidence and
abandon one that does not. His failure mode is acting on a confident wrong
answer, so an agent that says *"I don't know"* is more valuable to him than one
that always answers.

**Dana — AI Platform Engineer.** Owns the agent configuration. Needs to change a
retrieval threshold and immediately see whether groundedness improved or
regressed. Her failure mode is tuning by vibes.

**Priya — VP Engineering.** Signs off on production deployment. Needs one screen
that shows reliability, spend and governance posture. Her failure mode is
approving something she cannot defend in a post-incident review.

**Sofia — Risk & Compliance Lead.** Needs to reconstruct, months later, exactly
what the agent saw, what it cited, what it refused, and who approved the action.

## 5. Business objectives

| ID | Objective | Measure |
|---|---|---|
| **BO-1** | Make every agent claim traceable to a retrieved source | 100% of emitted claims carry a citation or an explicit no-evidence marker |
| **BO-2** | Keep the agent available when a model provider is not | Workflow completes across provider failure without operator intervention |
| **BO-3** | Bound model spend before it is incurred | No live model call executes without an open budget; every call priced at worst case pre-flight |
| **BO-4** | Prevent an ungrounded or high-risk action reaching production | Actions above the risk threshold cannot execute without a recorded human approval |
| **BO-5** | Make configuration changes measurable | Every change evaluable against a golden set with a before/after delta |

## 6. Business requirements

| ID | Requirement | Priority | Objective |
|---|---|---|---|
| **BR-001** | The system shall triage a production incident and produce a hypothesis with cited evidence | Must | BO-1 |
| **BR-002** | The system shall demonstrate PDLC, SDLC, CI/CD, Agile and Scrum practice through verifiable artifacts | Must | — |
| **BR-003** | The system shall continue operating when an individual model provider fails or rate-limits | Must | BO-2 |
| **BR-004** | The system shall refuse to answer when retrieved evidence does not support an answer | Must | BO-1, BO-4 |
| **BR-005** | The system shall record the full execution trace of every agent run, inspectable after the fact | Must | BO-1 |
| **BR-006** | The system shall block actions above a defined risk threshold pending human approval | Must | BO-4 |
| **BR-007** | The system shall attribute token consumption and cost to each individual run | Must | BO-3 |
| **BR-008** | The system shall retain conversational and cross-incident memory within a session | Should | BO-1 |
| **BR-009** | The system shall evaluate retrieval and generation quality against a fixed golden set | Should | BO-5 |
| **BR-010** | The system shall reduce redundant model calls through semantic caching | Should | BO-3 |
| **BR-011** | The system shall present its own architecture, decisions and delivery record to a visitor | Must | BR-002 |

## 7. Scope

### In scope
Incident triage workload · deterministic multi-provider routing · semantic cache ·
hybrid retrieval with citations and refusal · agent orchestration with a
governance gate · human approval workflow · session memory · execution tracing ·
cost attribution and spend guard · evaluation harness · the public experience
surface · the delivery/PDLC proof surface · CI/CD · deployment to free-tier
infrastructure.

### Out of scope
Real customer data of any kind (**SD-002**). Authentication beyond
demonstration-grade session identity. Multi-tenancy billing. Any job-application
or resume tooling (**SD-003** — that problem is solved elsewhere and is
explicitly not this product). Auto-execution of remediation against any real
system. Mobile native applications. Paid infrastructure (**NFR-002**).

## 8. Constraints

| ID | Constraint | Source |
|---|---|---|
| **NFR-001** | Effort and token spend must be directed at delivery, not deliberation | Executive Sponsor |
| **NFR-002** | Total infrastructure cost must be zero; no paid tier, no card-backed service | Executive Sponsor |
| **NFR-003** | First meaningful paint under 2.5s on a cold visit over 4G | Design requirement |
| **NFR-004** | The public endpoint must survive untrusted traffic without unbounded cost | Security |
| **NFR-005** | The agent service must run on a container with ephemeral disk and no persistent local state | INF-001 |
| **AC-001** | Architecture must separate the experience layer from the agent runtime | Stakeholder |
| **AC-002** | Every PDLC claim on the site must be verifiable; no simulated delivery metrics | Product Owner |
| **DR-001** | Visual quality must meet the standard of apple.com product pages: black canvas, cinematic footage, seamless motion | Product Owner |
| **FR-001** | The product name must be changeable without code changes | Product Owner |
| **PR-001** | Delivery must follow a named-role PDLC with explicit sign-off gates | Executive Sponsor |
| **CR-001** | Resume-driven content restrictions do not apply; this is a product, not a resume | Stakeholder |
| **SD-001** | The deliverable is a working product, not a portfolio listing | Product Owner |
| **SD-004** | Domain is agent reliability, with incident intelligence as the flagship workload | Product Owner |
| **INF-001** | Agent runtime hosted on Hugging Face Spaces; experience layer on Vercel | Executive Sponsor |
| **OPS-001** | Host disk reclamation authorised prior to build | Executive Sponsor |
| **VIS-001** | The product must read as production-grade engineering to a FAANG-tier reviewer | Executive Sponsor |

## 9. Assumptions

1. Free tiers of Groq, Gemini, Cerebras, OpenRouter and Mistral remain available
   at the volumes a demonstration site generates. *Mitigated by BR-003 — if one
   or several disappear, the product's own failover behaviour absorbs it.*
2. Hugging Face Spaces free CPU tier remains at 2 vCPU / 16 GB with sleep after
   prolonged inactivity.
3. Recruiter traffic is low-volume and bursty, not sustained.
4. A visitor spends under three minutes on the site. Every claim must therefore
   be legible without reading documentation.

## 10. Success criteria

The project succeeds when a technically credible reviewer can, unaided and
without asking a question:

1. Watch an agent triage an incident and see exactly what evidence it used.
2. See it refuse a question the evidence does not support.
3. Force a provider failure and watch the workflow survive it.
4. Read the cost of the run they just triggered.
5. Block a remediation on approval, then release it.
6. Open the delivery record and verify the CI, the tests and the commits are real.

Criterion 6 is the one that distinguishes this from a demo. It is also the one
that constrains every shortcut available during the build.
