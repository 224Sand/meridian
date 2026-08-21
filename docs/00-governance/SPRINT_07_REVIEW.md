# Sprint 7 — Review & Retrospective

**Sprint:** 7 — Proof Surfaces · **Closed:** 2026-08-21 · **Release:** 0.7.0 ·
**Gate:** UAT

## 1. Sprint goal

**Met.** `/reliability` and `/architecture` ship, every figure on them derived
from the repository at build time. The README exists for the first time and its
figures are checked against the same record.

## 2. Delivered

All six stories, 29 points. Plus the pen-test and hardening work below, which was
not in the plan and belonged in Sprint 8 — pulled forward because running the
system was the only way to know whether these pages were telling the truth.

| | |
|---|---|
| Tests | 351 across 19 files · 439 pass, 26 skip |
| Smoke | 8/8 |
| Pen tests | **6/6**, from 4/6 |
| Requirements | 58, 13 `Done`, each naming a test that exists |
| Defects | 15 logged, 5 severity 1 |
| New CI guards | 3 — workflow shell, traceability, README |

## 3. What running it actually found

This sprint ran the assembled system against a live runtime for the first time.
**Four defects, and three of them were checks that could not fail.**

- **D-012** — no body-size limit; a 200KB body reached the agent and returned
  502. A real gap, and the only one of the four that was a missing control rather
  than a fake one.
- **D-013** — the rate-limit pen test sent 8 requests against a limit of 20, so
  no limiter behaviour could have failed it, and its pass condition accepted
  `all(c >= 400)` — meaning a service that was **down** reported as correctly
  rate limited. It did exactly that earlier in the session.
- **D-014** — traceability drifted in **both** directions: four rows used
  statuses the legend never defines, which the delivery page counted as done, and
  one sat at `Planned` while its test had passed since Sprint 2.
- **D-015** — the first README checker searched each figure as a substring of the
  whole file. Changing `54` to `99` still passed, because "54" appears in "54% of
  questions". It went green on a value deliberately corrupted to test it.

The contract test written for AC-001 found real drift on its first run: the BFF
admitted 8KB while the runtime caps `body` at 4000 characters, so the edge
forwarded requests that could only be refused upstream.

## 4. Measured

| | measured | 95% CI | budget |
|---|---|---|---|
| False answers | 4.7% | [2.9, 7.6] | 5% |
| False refusals | 2.3% | [1.2, 4.3] | 10% |

Both within budget on the point estimate. The false-answer **interval crosses its
budget**, and the surface says so in those words rather than reporting a pass.

## 5. Retrospective

**What worked.** Definition of Done item 9 — run the guard against the defect it
claims to catch and watch it fail — earned itself immediately. It caught D-015 in
a script written to prevent exactly that class, minutes after the commentary
about that class was written. Without the deliberate corruption step, a check
that could never fail would have shipped as a governance control.

**What did not.** Sprint 7's own work included Sprint 8 stories. Pen tests, the
body-size bound and the deployment manifests all belong to Hardening & Release,
and they were done here because they were in the way. That is defensible once and
corrosive as a habit: it is how a release sprint ends up with nothing left in it
but the deploy, and no slack for what the deploy breaks.

**Also.** Three of four defects this sprint were controls that reported success
without testing anything. That is now a recognised pattern rather than three
coincidences — the failure is not in any one check but in accepting green as
evidence. Improvement 1 below makes the response structural.

**Improvements committed for Sprint 8.**
1. Every guard added from here carries a companion test that runs it against
   known-bad input and asserts it fails. Item 9 becomes automated rather than a
   habit — habits are what produced D-013 and D-015.
2. Work belonging to a later sprint is logged as an impediment against the
   current one before it is started, not narrated afterwards in the review.

## 6. Gate

**UAT** — pending Product Owner. The proof surfaces are inspectable; the two
criteria that matter are that no figure on them is hand-written, and that the
failing checks are visible without scrolling past a success.
