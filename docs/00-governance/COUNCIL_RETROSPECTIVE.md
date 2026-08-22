# Council Retrospective

**Produced by:** `skills/role-council` — the project's own governance tooling, extracted into a
reusable skill (see `skills/role-council/README.md`) and run against this repository's own real
history. Every reaction below is grounded in a citation in this repo: a defect ID, an ADR, a
sprint review, or a file. Nothing here is an invented opinion.

**Roster.** Roles are drawn from `docs/00-governance/WAYS_OF_WORKING.md`, this project's own
declared charter, per the skill's step-1 rule: start from what the project already names rather
than inventing a parallel roster. Not every role appears on every artifact — a role that has
nothing real to say about a given decision is left out rather than padded in.

---

## 1. The Sprint 2 gate reported 0% false-answer rate. The real rate was 56.6%. — [D-001](DEFECT_LOG.md)

**What happened:** The refusal gate marked 150 of 265 unanswerable questions as answerable — a
56.6% false-answer rate — on a sample where the Sprint 2 gate had reported 0%.

- **QA Lead:** The test set was written by the implementer, on 22 questions, and every one of
  them happened to be easy. That's not a QA failure of rigor so much as a structural one — the
  same person who builds the gate should not be the only one who decides what counts as a hard
  question for it. I'd have wanted an adversarial set from someone who didn't write the gate.
- **Business Analyst:** A 0% error rate reported at a sprint gate is the kind of number that
  should have triggered a question before it was accepted, not after a defect was found later. If
  the acceptance criteria for that gate didn't require a minimum sample size, that's a gap in what
  I wrote at Sprint 0, not just in how it was tested.
- **Technical Program Manager:** This is the one that actually changes how I'd read every other
  green metric in this project. If a headline number can be 0% wrong on a small sample and 57%
  wrong on a large one, "passed at the gate" isn't sufficient evidence on its own going forward —
  it needs a stated sample size next to it, every time.
- **Where they diverged:** QA and BA read this as a process gap in two different places (test
  authorship vs. acceptance criteria); TPM reads it as a trust problem with every other reported
  metric in the project. All three are right, and none of them alone would have caught it.

---

## 2. The semantic cache served a stale answer to a correction retry. — [D-006](DEFECT_LOG.md)

**What happened:** A retry meant to correct an uncited answer instead received the previous,
uncited answer from cache — similarity 0.886 against a 0.60 threshold.

- **Solutions Architect / FDE:** Both components — the retry logic and the cache — had correct,
  passing tests individually. The cache's own test asks whether two different *questions*
  collide (0.208, correctly no); nobody asked whether a prompt collides with its own
  *correction*. That's an architecture-level blind spot, not a bug in either component, and no
  amount of unit testing either one in isolation would have found it.
- **Developer:** From inside the retry code, this looks like it should have worked — the retry
  fired, a new attempt was made. The failure is invisible at the call site; you'd only see it by
  looking at what actually came back.
- **QA Lead:** This is the sharpest example in the whole log of why running the assembled system
  matters more than passing unit suites. I'd flag it as the strongest argument for the DoD item
  that got skipped for four sprints (see below) — this exact defect is what "demonstrable, not
  described" was meant to catch, and it didn't get the chance to.
- **Where they diverged:** the Architect and QA agree on the root cause but draw different
  conclusions from it — Architect reads it as an inherent limit of component-level testing;
  QA reads it as a specific, avoidable process failure (the integration layer wasn't exercised
  early enough to catch it before Sprint 5).

---

## 3. The console displayed output the governance layer had refused to emit. — [D-009](DEFECT_LOG.md)

**What happened:** Rendering ignored the run outcome and displayed an assessment the system had
already decided not to emit.

- **Application Security Engineer:** This is a governance-bypass bug wearing a UI-bug costume.
  The backend correctly refused; the frontend showed it anyway. If the refusal exists to enforce
  a real constraint (and here it does — INSUFFICIENT evidence, no draft), a rendering layer that
  can silently override that constraint is the same class of problem as an auth check that
  passes but a UI that shows the gated content regardless.
- **UX / UI Designer:** From a pure "does this look right" standpoint the page rendered fine —
  there was nothing visually broken about it. Which is exactly the problem: a visual review alone
  would have signed this off.
- **QA Lead:** Confirms the Designer's point from the test side — this wouldn't be caught by
  checking "does the page render," only by checking "does the page render *the right thing*,"
  which requires knowing what the backend actually decided.
- **Where they diverged:** none, really — this is a case where three roles converge on the same
  conclusion from three different entry points, which is itself informative: a defect that's
  invisible to a purely visual check AND invisible to a purely functional check needed someone
  checking the two against each other.

---

## 4. Two guards that were built to confirm, not to detect. — [D-013](DEFECT_LOG.md) and [D-015](DEFECT_LOG.md)

**What happened:** The rate-limit pen test sent 8 requests against a limit of 20 and accepted
`all(c >= 400)` as a pass — so a completely dead service reported as correctly rate limited. The
README figure-checker searched for values as substrings of the whole file, so `Commits | 54`
silently changing to `99` still passed, because "54" also appears elsewhere in the same document.

- **QA Lead:** Both of these are the same defect, twice, in the same sprint, written by the same
  process. That's the finding — not that a check was wrong once, but that "did I actually run
  this against something I know is broken" wasn't yet a standing habit when either check was
  written. It became one only after the second instance.
- **Scrum Master:** This is a process-health signal more than a testing one. The project's own
  Sprint 7 review names the fix directly — "a guard is not trusted until it has been run against
  the defect it claims to catch and observed to fail" — and states it was only adopted *after*
  the second occurrence. One instance is a mistake; recognizing the pattern and turning it into a
  standing rule is the actual recovery.
- **Developer:** Both bugs are easy to write by accident — a loose assertion, a naive string
  search — because a guard that passes looks identical to a guard that works, right up until you
  try to break it on purpose. I'd want "prove it fails first" as a review checklist item on any
  new check, not just a retrospective lesson.
- **Where they diverged:** QA and Developer treat this as a technique problem (test the
  negative case); Scrum Master treats it as a culture problem (was the lesson actually
  institutionalized, or just written down once). Both readings are true and the project's later
  guard (`test_guards_fail_on_bad_input.py`, added in response) is really an answer to the Scrum
  Master's version of the question, not just the technique fix.

---

## 5. Sprints 6 and 7 were worked and shipped without ever being opened. — [D-016](DEFECT_LOG.md)

**What happened:** No planning ceremony, no plan document — the sprint numbers existed only
inside defect-log entries — and a Sprint 5 retrospective had already committed, in writing, to
raising exactly this as an impediment if it happened. It happened anyway.

- **Scrum Master:** This is the one I'd flag hardest. It's not that the process broke — it's
  that the team (in this case, one person plus an AI agent in named roles) *wrote down the exact
  failure mode in advance* and then didn't catch it when it occurred. A committed retrospective
  action that isn't checked at the next retro isn't a retrospective action, it's a wish.
- **Technical Program Manager:** From a planning standpoint, work that happens outside a named
  sprint is invisible to anything that tracks velocity or capacity — there's no record of what
  was committed vs. delivered for two sprints' worth of real output. The backfilled plans
  (`SPRINT_06_PLAN.md`, `SPRINT_07_PLAN.md`) are honest about being written after the fact, which
  is the right repair, but the gap itself cost real planning fidelity that can't be recovered
  after the fact.
- **Executive Sponsor:** The part I'd actually want to know: was the *work* good despite the
  missing ceremony? Reading the backfilled reviews, yes — the deliverables match what a real
  Sprint 6/7 would have needed. So this is a paperwork failure, not a delivery failure, which
  matters for how seriously to take it, but it's still worth fixing, because the next gap might
  not be paperwork-only.
- **Where they diverged:** Scrum Master reads this as the more serious failure (a broken
  commitment); Executive Sponsor reads it as the less serious one (real work still shipped). Both
  are correct, and the tension between them is exactly why the fix that followed — a build-time
  check that a sprint number can't be used before its plan exists — was worth building rather
  than just apologizing for the gap.

---

## 6. ADR-0003 recorded a pricing claim that was never checked. — [D-017](DEFECT_LOG.md), [ADR-0003](../03-architecture/adr/0003-agent-runtime-on-hugging-face-spaces.md), [ADR-0012](../03-architecture/adr/0012-agent-runtime-on-northflank.md)

**What happened:** ADR-0003 placed the agent runtime on Hugging Face Docker Spaces "because it
is free." Docker Spaces moved behind a paid plan; only Static Spaces remain free, and a Static
Space can't run the FastAPI runtime. Three sprints of deployment work targeted a platform that
turned out to be impossible at $0.

- **Solutions Architect / FDE:** The choice itself was reasonable at the time it was made. The
  actual defect is narrower and worse: the ADR recorded a claim about a third party's pricing
  without ever citing the page it came from or the date it was checked. A decision record that
  can't be re-verified against its own stated source is a decision record that will silently go
  stale, and this one did.
- **Executive Sponsor:** Zero infrastructure cost was a constraint I set at the very start of
  this project, in the founding brief. Finding out three sprints later that the chosen host no
  longer meets it — discovered only when actually trying to deploy — is the outcome I most wanted
  a governance process to prevent. This is the sharpest miss in the whole log against something I
  personally asked for.
- **DevOps / SRE:** From where I sit, the practical cost wasn't the ADR being wrong — ADRs get
  superseded, that's normal — it's that the Dockerfile, the deploy scripts, and the README were
  all written against a platform-specific assumption (Hugging Face's Space manifest, its token
  scoping, its URL shape) that then all needed rewriting. A decision that's cheap to reverse on
  paper wasn't cheap to reverse in the actual deployment tooling built on top of it.
- **Where they diverged:** the Architect frames this as a documentation discipline problem
  (cite your source); the Executive Sponsor frames it as a broken constraint (the $0 promise
  failed); DevOps frames it as a blast-radius problem (how much downstream tooling assumed the
  wrong platform). The charter's resulting rule — "an ADR depending on a third party's pricing
  must name the page and the date" — really only answers the Architect's version of the
  complaint. The Sponsor's and DevOps's versions don't have a structural fix yet, which is worth
  naming rather than pretending is solved.

---

## 7. CI never built the web app; a major framework bump reported 10/10 green while broken. — [D-018](DEFECT_LOG.md)

**What happened:** No CI job had ever run `next build`. A Dependabot PR taking Next.js from 15 to
16 reported every check green while the production build failed on all seven pages (Turbopack
refuses an import path that Webpack tolerated).

- **QA Lead:** This is the purest instance in the log of a check that measures its own existence
  rather than the thing it claims to measure. Ten green checks that never touch the code under
  change aren't weak evidence, they're negative evidence — a reviewer who trusted them would be
  more confident than they should be, which is worse than no checks at all.
- **DevOps / SRE:** From a pipeline-design standpoint, this is a coverage gap that's invisible
  until exactly the moment it matters — every other change to the web app in this project's
  history happened not to touch anything Turbopack cared about, so nothing surfaced it until a
  major version bump did. I'd want a standing rule that any application with a build step gets a
  build step in CI on day one, not added reactively after a near-miss.
- **Developer:** As the person who'd have merged that PR on the strength of a green check suite,
  this is the one I find most uncomfortable — the failure isn't in code I wrote, it's in trusting
  a signal that looked authoritative and wasn't. I'd want the absence of a build job to be as
  visible as a failing one, not just silently absent from the job list.
- **Where they diverged:** no real disagreement here either — all three converge on "the
  pipeline lied by omission," which is itself the finding: when every role reads the same defect
  the same way, it usually means the defect is structural rather than a matter of judgment call.

---

## 8. A three-state chip design, decided this session, over the false-answer budget bar.

**What happened:** `apps/web/src/components/BudgetBar.tsx` originally rendered a two-state chip
(`clear`/`not clear` of budget) for the false-answer rate. The measured rate was 4.7% against a
5% budget — passing on the point estimate while its 95% confidence interval (2.9–7.6) crossed the
budget line. The two-state chip read "within budget" for a result that was genuinely more
ambiguous than that.

- **Business Analyst:** "Within budget" and "the confidence interval is clear of budget" are two
  different claims, and collapsing them into one chip is exactly the kind of over-reporting this
  project's own rules exist to prevent elsewhere (a bullet that cites a number it can't support).
  I'd have rejected the two-state version on the same grounds I'd reject an unsupported resume
  claim — it says more than the data backs.
- **UX / UI Designer:** From a pure readability standpoint, a three-state chip is a harder design
  problem than a two-state one — more label text, another color to keep meaningfully distinct
  from the other two. The fix (`"within budget, interval not yet tight"`) is honest but visually
  busier than I'd want as a first instinct; I'd keep it, but I'd want to watch whether it reads
  as a *fourth* state to someone at a glance rather than a nuance on the first.
- **Technical Program Manager:** This one didn't cost a sprint or get logged as a defect — it was
  caught and fixed inside the same session it was built, before it ever shipped. Worth noting as
  a contrast to the entries above: not every gap in this project took a postmortem to catch: this
  is what the discipline looks like working in real time instead of after the fact.
- **Where they diverged:** BA and Designer are in real tension here — BA wants maximum
  precision in what the chip claims, Designer wants maximum clarity in what it shows, and a
  three-state chip is the compromise between them, not a clean win for either. TPM's contribution
  isn't a stance on the chip at all — it's a comment on process speed, which is a genuinely
  different axis than the other two.

---

## 9. Where the roles agreed most, and what that says

Counting across the entries above: **QA Lead and DevOps/SRE converge most often** (defects 3, 4,
and 7 all read the same way from both seats). That's worth asking about rather than taking as
simple confirmation — on a solo project run by one person plus an AI agent playing named roles,
QA and DevOps concerns are structurally close (both ultimately ask "does this actually work when
run for real"), so agreement between them is less independent evidence than it would be on a
team where those are different people with different incentives. The genuinely independent
disagreements — BA vs. TPM on D-001, Architect vs. Sponsor vs. DevOps on D-017, BA vs. Designer
on the chip — are the ones that changed a decision or would change one going forward, and they're
also the ones where the roles' underlying concerns (traceability vs. schedule risk vs.
documentation discipline vs. budget vs. blast radius vs. precision vs. clarity) are structurally
different rather than restatements of each other.

**The sharpest single disagreement in the log:** D-017. Three roles, three completely different
diagnoses of the same defect (cite-your-sources / broken budget promise / rewritten tooling), and
only one of the three got a structural fix. That's the clearest single argument in this project's
own history for why a retrospective needs more than one voice — a single-author postmortem of
D-017 would very plausibly have stopped at the Architect's reading and missed the other two.
