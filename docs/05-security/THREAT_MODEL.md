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

---

# Addendum — Sprint 5: the public browser surface

**Date:** 2026-08-20 · **Trigger:** §6, "a new trust boundary appears"

Sprints 0–4 produced a library. Sprint 5 puts a browser in front of it, which
adds a boundary that did not exist and changes the exposure of two threats
already recorded.

## New surface

| | |
|---|---|
| Browser → BFF | Fully untrusted. Anyone on the internet. |
| BFF → agent runtime | Authenticated; the browser must never cross it directly. |

## Threats

| # | Threat | Vector | Mitigation | Residual |
|---|---|---|---|---|
| **T-12** | The inter-service token reaches the browser | Passing it to a client component, or into a `NEXT_PUBLIC_*` variable | The token is read only in route handlers, never in a component. A test greps the built client bundle for it and fails the build on a match. | Low |
| **T-13** | The runtime is called directly, bypassing the BFF's rate limit | The Space URL is discoverable | Bearer auth on every `/v1/*` route (T-3), plus the per-IP limit is the BFF's job and the daily token ceiling is the runtime's, so neither depends on the other | Low |
| **T-14** | SSE connections held open to exhaust the runtime | Opening many streams and never reading | Per-IP concurrent-stream cap; server-side timeout on any run exceeding its budget. A stream is not free just because it is idle. | Medium |
| **T-15** | A run's free-text body used to smuggle instructions | Prompt injection through the incident description | Retrieved content and user content are both delimited and neither is granted instruction authority. **No tool can act on any real system** (T-11), so the worst outcome is a wrong answer rather than a wrong action. Body length is capped at 4,000 characters, which is also a cost bound. | Medium — accepted |
| **T-16** | A secret reaches a trace attribute and is rendered | Span attributes are shown in the UI | The span exporter has an allowlist of attribute keys; anything else is dropped rather than redacted, because a redaction that fails is invisible | Low |
| **T-17** | Approval forged or replayed | Posting an approval for someone else's run | An approval is bound to the session that created the run; a decision for an unknown or foreign run is rejected. Demo-grade identity, stated as such. | Medium — accepted |

## Two changes to existing entries

**T-1 (unbounded model spend) moves from Low to Medium residual.** It was
theoretical while nothing was deployed. Once a URL exists it is a matter of
someone finding it. The mitigations are unchanged and now actually matter: per-IP
sliding window failing **closed** (ADR-0007), a daily token ceiling, and a spend
guard that refuses without an open budget.

**T-9 (session correlation from IP) is unchanged and worth restating.** The BFF
now sees every visitor's address for rate limiting. It is hashed with a salt
before it reaches storage and the raw value never leaves the request scope.

## The control that carries the most weight

**T-11 — no tool executes against any real system.** Every threat involving
prompt injection, forged approvals or a compromised model resolves to "the
attacker obtains a wrong sentence" rather than "the attacker obtains an action".

That is a design decision with a cost: the product proposes and never executes,
which makes the demonstration less impressive than it could be. It is also why
this threat model is short.
