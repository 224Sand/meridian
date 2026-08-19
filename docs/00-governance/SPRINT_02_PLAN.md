# Sprint 2 — Agent Core I

**Sprint goal:** A model call cannot leave this system ungoverned. Routing,
caching, retrieval and refusal all work, are measured, and survive provider
failure.

**Opened:** 2026-08-20 · **Release target:** 0.2.0 · **Gate:** Sprint Review

| Lens | Position |
|---|---|
| Product stage | **MVP** |
| SDLC | Design, Implementation, Testing |
| PDLC | Development |
| **AIDLC** | **3** Context & task engineering · **4** Retrieval & grounding · **7** Deployment & serving |
| Agile | Sprint 2 of 8 |

---

## Sprint backlog

| ID | Story | Role | Pts | AIDLC | Status |
|---|---|---|---|---|---|
| **S2-01** | Deterministic router: ordered failover, time-boxed disabling, injected clock | DEV | 8 | 7 | ⬜ |
| **S2-02** | Provider adapters for Groq, Gemini, Cerebras, OpenRouter, Mistral | DEV | 5 | 7 | ⬜ |
| **S2-03** | Failure injection endpoint, session-scoped (FR-011) | DEV | 3 | 7 | ⬜ |
| **S2-04** | Semantic cache: exact-hash tier and vector tier, keyed by embedding model | DEV | 5 | 7 | ⬜ |
| **S2-05** | Gemini embedder with degradation to the offline embedder | DEV | 3 | 4 | ⬜ |
| **S2-06** | Hybrid retrieval: BM25 and dense fusion, degraded labelling | DEV | 5 | 4 | ⬜ |
| **S2-07** | Evidence assessment and the refusal gate | DEV | 5 | 4 | ⬜ |
| **S2-10** | Corpus depth expansion and change-review documents | Tech Writer | 5 | 2 | ⬜ |
| **S1-09** | Seed loader (carried from Sprint 1) | DEV | 3 | 2 | 🚫 IMP-04 |

**Committed: 39 points** (36 unblocked). Demonstrated velocity: 41.

## Why the sprint plan changed

The Product Owner added a second workload and corpus depth at the Sprint 1
review. Sprint 2 as originally scoped reached 62 points. The plan now runs to 8
sprints with the agent core split across two. Carrying 62 points and reporting a
miss would have made the velocity record fiction, and AC-002 does not allow that.

## Requirements landing

FR-010 router · FR-011 failure injection · FR-012 semantic cache ·
FR-006 refusal · BR-003 provider resilience · BR-004 refusal · BR-010 caching ·
NFR-004 abuse resistance (partial)

## Definition of Done additions

- No test in this sprint may make a live model call. Providers are stubbed at
  the transport boundary, and the offline embedder is the default in tests.
- The router's clock is injected. A test that observes a TTL expiring by sleeping
  is rejected at review.
- Every refusal threshold must be justified by a measured separation on the
  corpus, not chosen by feel.

## Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted |
| IMP-04 | No managed Postgres or Redis credentials | **OPEN** — blocks S1-09 only |
