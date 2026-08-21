# SandScope

**An agent that operates production systems, and declines when it cannot support an answer.**

SandScope answers incident and change-management questions over a fixed corpus
of architecture, policy and runbook documents. Given a question it retrieves
evidence, decides whether that evidence is sufficient to answer *at all*, and
either answers with citations or refuses.

The refusal is the interesting part. Anything can answer; the engineering is in
knowing when not to.

| | |
|---|---|
| **Experience layer** | Next.js on Vercel — SSE console, delivery record, reliability and architecture surfaces |
| **Agent runtime** | FastAPI + LangGraph on Hugging Face Spaces |
| **Data plane** | Neon Postgres + pgvector · Upstash Redis + Vector — all Ireland |
| **Models** | Trained offline, served as ONNX. No training framework in the serving image. |
| **Cost** | $0. Every dependency has a free tier, and a test asserts it. |

---

## The refusal decision

Retrieval produces a score; the score maps to one of three bands.

| Band | Behaviour |
|---|---|
| `SUFFICIENT` | answer, every claim cited |
| `AMBIGUOUS` | answer, flagged partial — never silently upgraded |
| `INSUFFICIENT` | refuse — **no draft is emitted at all** |

The two thresholds are not chosen by taste. They are read off the ROC curve
against explicit, asymmetric error budgets, measured over **715 labelled
questions** (396 answerable, 319 not):

| | measured | 95% CI | budget |
|---|---|---|---|
| False answers | 4.7% | [2.9, 7.6] | 5% |
| False refusals | 2.3% | [1.2, 4.3] | 10% |

An earlier build reported a **0% false-answer rate on 22 questions**. The real
rate on 534 was **56.6%**. Deriving the bands from budgets instead of from a
good-looking sample is what fixed it, and the postmortem is in the repo.

## What is still weak

Three checks run on every push and are **expected to fail**. They keep known
limitations visible rather than letting a green suite imply the problem is
solved:

- the answerable and unanswerable score distributions overlap, which is why the
  gate defers most decisions rather than committing
- a value-demanding question the corpus never answers still scores 8.85 on
  retrieval alone; only a separate value-demand check keeps it out of the
  sufficient band
- the gold chunk ranks first for 54% of questions, which bounds citation
  precision

A passing probe suite would mean it had stopped looking.

## Machine learning

Trained offline, shipped as ONNX, served without torch or transformers — that
split is [ADR-0009](docs/03-architecture/adr/0009-train-offline-serve-without-the-framework.md),
and it turned out to be a security boundary too: the training extra carries four
known RCE advisories while the runtime closure audits clean at zero.

| | |
|---|---|
| Sufficiency classifier | gradient boosting, 12 retrieval features, 715 examples. **AUC 0.808** vs 0.609 baseline. Ships *uncalibrated* — Platt collapsed it to 0.599, isotonic broke ONNX parity. |
| Cross-encoder re-ranker | TinyBERT-L-2 on 1,939 pairs. Chunk-level MRR **0.528 → 0.587**, p50 18.5ms. |

Document-level MRR was already 0.986 and hid the entire effect. Measuring at the
level a citation actually points at is what made the improvement visible — see
[the postmortem on a null result that was two bugs](docs/06-operations/postmortems/2026-08-20-a-null-result-that-was-two-bugs.md).

## Reliability engineering

- **Deterministic provider failover** — groq → gemini → cerebras → openrouter →
  mistral, fixed order. A rate-limited provider is disabled for a *bounded*
  interval, and the clock is injected so expiry is tested rather than waited on.
- **Spend is reserved against the worst-case surviving provider** before the
  call. Pricing the first one under-reserved by 4× the moment failover reached a
  costlier model.
- **Semantic cache**, exact-hash then vector. Its threshold belongs to the
  embedder, not the cache — a module-level `0.86` was wrong in both directions
  at once ([ADR-0008](docs/03-architecture/adr/0008-similarity-thresholds-belong-to-the-embedder.md)).
- **Rate limiting fails closed.** If the limiter is unreachable, the request is
  refused, not allowed ([ADR-0007](docs/03-architecture/adr/0007-rate-limiting-fails-closed.md)).
- **Approval nodes are terminal.** A gated run is never resumed; approving
  creates a continuation run ([ADR-0006](docs/03-architecture/adr/0006-approval-nodes-are-terminal.md)).

## How it was built

Six sprints, eleven named delivery roles and four stakeholder roles, five
lifecycle lenses (product stage · SDLC · PDLC · AIDLC mapped to NIST AI RMF ·
Agile). The governance is real rather than decorative: **a requirement that
claims `Done` while the test it names is absent fails the build.**

Every number on the delivery surface is derived from the repository at build
time or read live from the GitHub API. None is typed by hand — including the
defect count, and including the numbers in this README.

| | |
|---|---|
| Tests | 351 across 19 files |
| Requirements | 58, of which 13 `Done` and each names a test that exists |
| Defects logged | 15, of which 5 severity 1 |
| ADRs | 11 |

**Not one defect was caught by code review, and not one by a unit test written
before it.** Every single one was caught by *executing* something — the
assembled system, a measurement over a large labelled set, or a container in CI.
That distribution is the finding.

The [defect log](docs/04-quality/DEFECT_LOG.md) is published in full, including
the embarrassing ones, because a delivery record containing only successes is
not evidence of anything.

## Security

CodeQL · Semgrep · Trivy · gitleaks · pip-audit · npm audit · CycloneDX SBOM ·
OWASP ZAP · 6 scripted penetration tests, all green.

The security pipeline found real problems, including in itself: a shell
injection in a workflow input, four RCE advisories that never reach the serving
image, an unbounded request body, and a rate-limit test that **passed while the
service was down**.

## Running it

```bash
# agent runtime
cd apps/agent && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/smoke.py          # 8 checks against the assembled system

# experience layer
cd apps/web && npm ci && npm run dev
```

Deployment manifests live in [`deploy/space/`](deploy/space) (Hugging Face) and
[`vercel.json`](vercel.json).

## Honest limitations

- Retrieval signals overlap; the gate defers rather than committing, and the
  three probe checks above quantify exactly how much.
- The corpus is synthetic by design. No real customer data touches this.
- Session identity is a cookie. It scopes memory and binds approvals; it is not
  authentication, and the threat model says so.
- 45 of 58 requirements are still `Planned`, and the matrix says so rather than
  rounding up.

---

*Built by [Sandeep Chavan](https://github.com/224Sand). Corpus, incidents and
metrics are synthetic; the engineering, the defects and the measurements are
not.*
