# Threat Model

**Version:** 1.0 · **Author:** Security Engineer · **Date:** 2026-08-20
**Method:** STRIDE over the container diagram in [TECH_SPEC.md](../03-architecture/TECH_SPEC.md) §2
**Status:** DRAFT — awaiting sign-off

---

## 1. Scope and assets

A publicly reachable demonstration system holding no personal data and no
customer data. The assets worth protecting are therefore not records but
**capabilities and credentials**:

| Asset | Why it matters |
|---|---|
| LLM provider API keys | Direct financial and quota value if exfiltrated |
| Inter-service bearer secret | Grants direct access to the agent runtime, bypassing the BFF's rate limits |
| Model call capability | The endpoint is free LLM capacity to an abuser (NFR-004) |
| Database credentials | Corpus and trace integrity |
| Delivery record integrity | The product's central claim is that the record is real; forged evidence would be the worst possible failure |

Explicitly **not** assets: user PII (none collected), customer data (synthetic),
uptime (a demo).

## 2. Trust boundaries

1. Browser → BFF. Fully untrusted input.
2. BFF → agent runtime. Authenticated; the browser must never cross this directly.
3. Agent runtime → LLM providers. Outbound; responses are untrusted input.
4. Agent runtime → Postgres/Redis. Credentialed.
5. Build → Pexels/GitHub. Build-time only, never request-time.

## 3. STRIDE analysis

| # | Threat | Category | Vector | Mitigation | Residual |
|---|---|---|---|---|---|
| T-1 | Abuser drives unbounded model spend | DoS / cost | Scripted requests to the run endpoint | Per-IP sliding window; daily token ceiling; spend guard refuses without an open budget; both **fail closed** (ADR-0007) | Low |
| T-2 | Provider keys exfiltrated | Information disclosure | Keys reaching the client bundle or logs | Keys live only in the runtime's environment; the BFF holds the inter-service secret; secret scanner blocks commits; structured logs redact by key name | Low |
| T-3 | Agent runtime called directly, bypassing rate limits | Elevation of privilege | Guessing the Space URL | Bearer token on every `/v1/*` route, constant-time comparison; unauthenticated requests rejected before any work | Low |
| T-4 | Prompt injection via retrieved corpus | Tampering | Malicious text inside a document chunk | Corpus is build-time seeded and immutable at runtime; no user-supplied documents; retrieved content is delimited and never granted instruction authority | Low |
| T-5 | Prompt injection via incident description | Tampering | Visitor-supplied incident text | Visitor input is constrained to selection and bounded free text; the orchestrator treats all retrieved and user content as data; no tool has write access to any real system | Medium — accepted, no tool can act externally |
| T-6 | Chaos endpoint used to degrade the demo for others | DoS | Repeated provider-failure injection | Injection is session-scoped and rate-limited; it can never disable a provider globally | Low |
| T-7 | Trace or approval records forged | Tampering / repudiation | Direct database write | Application-only write paths; approvals carry timestamp and session identity; runs are append-only | Medium — a demo-grade identity model, stated as such |
| T-8 | Delivery record misrepresented | Repudiation | Hand-written CI or test numbers | Delivery surface reads the GitHub API live; the traceability gate blocks untested requirements | Low |
| T-9 | Session correlation from IP | Information disclosure | Storing raw client IP | IPs stored as salted hashes only; no raw IP persisted anywhere | Low |
| T-10 | Dependency supply chain | Tampering | Malicious transitive package | Pinned lockfiles; minimal dependency surface (the router, cache, BM25 and embedder are first-party); Dependabot on | Medium |
| T-11 | Model output triggers unintended action | Elevation of privilege | Model emits a remediation command | **No tool executes against any real system.** Remediation is text. Risk-gated actions additionally require terminal human approval (ADR-0006) | Low |

## 4. The two that shape the architecture

**T-1** is the reason ADR-0007 exists. The instinctive default of failing open on
a limiter outage is exactly wrong here: it converts a dependency blip into an
unbounded-cost event on a publicly known endpoint.

**T-11** is the reason the product proposes rather than executes. A control plane
that could restart a service would be a more impressive demo and a materially
worse design decision, and the honest version is the one that ships.

## 5. Secrets handling

Secrets exist only as environment variables — in Vercel project settings, in HF
Space secrets, and in an untracked local `.env`. `.env.example` carries
placeholder values and is the only env file in git. `check-secrets.mjs` runs on
every push and blocks on match. No secret is ever logged, echoed into an error
message, or included in a trace attribute.

## 6. Review triggers

This model is revisited when: any tool gains write access to an external system;
user-supplied documents enter the corpus; authentication is added; or a new trust
boundary appears. Absent those, it is reviewed once at Sprint 6 hardening.
