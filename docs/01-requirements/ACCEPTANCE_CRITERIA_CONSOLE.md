# Acceptance Criteria — Console (Sprints 5 & 6)

**Author:** Business Analyst · **Date:** 2026-08-20
**Accepted by:** Product Owner at the UAT gate

> Written before the console exists so that acceptance is judged against
> criteria rather than against whatever gets built. A demo is persuasive and a
> criterion is checkable, and the two disagree more often than anyone expects.

Each criterion is written from a persona in the BRD and is testable by a person
in under a minute.

---

## AC-C1 — Marcus (SRE) can see what the agent used

**Given** a triage run has completed
**When** Marcus reads the assessment
**Then** every claim carries a citation marker, and clicking it reveals the exact
passage — not the document, the passage.

*Rejects:* a citation that opens a whole runbook. A citation that points at a
passage which does not contain the claim.

## AC-C2 — Marcus can tell refusal from failure

**Given** he asks something the corpus cannot answer
**When** the run ends
**Then** the console says the evidence does not support an answer, names what was
searched, and does not look like an error.

*Rejects:* a spinner that stops. An empty result. A stack trace.

## AC-C3 — Marcus cannot be surprised by an action

**Given** the agent proposes something above the risk threshold
**When** the run reaches the gate
**Then** the run **stops**, the proposed action and its risk level are shown, and
nothing proceeds until he decides.

*Rejects:* an action described as "applied". A countdown. A default-yes.

## AC-C4 — Dana (Platform) can force a provider failure and watch it survive

**Given** she injects a failure into the first provider
**When** she starts a run
**Then** the run completes, and the provider panel shows the failure, the
failover and which provider actually served it.

*Rejects:* the run completing with no visible evidence a failover happened.

## AC-C5 — Dana can see what the cache saved

**Given** any run has completed
**Then** the console reports cache hit rate and tokens avoided as numbers, for
that run.

## AC-C6 — Priya (VP) can read the cost of a single run

**Given** a run has completed
**Then** its cost appears in USD to at least four decimal places, alongside the
tokens in and out.

*Rejects:* a monthly total. An estimate not tied to the run just watched.

## AC-C7 — Sofia (Risk) can reconstruct any decision

**Given** a completed run
**When** she opens its trace
**Then** she sees every node in order with its duration, which provider served
each model call, whether the cache was hit, and the evidence verdict with its
score.

*Rejects:* a summary. A log without ordering. A trace missing the BFF's own span.

## AC-C8 — A visitor understands the refusal posture without being told

**Given** a first-time visitor runs the default incident
**Then** within one screen they can see that the system cites, that it can
refuse, and that a human approves risky actions.

*This one is deliberately subjective.* It is the difference between a tool and a
demonstration, and the Product Owner judges it.

---

## Sprint 6 criteria (experience)

## AC-C9 — It reads as a product, not a dashboard

**Given** the landing surface on a cold visit
**Then** it communicates the problem, the mechanism and the proof in that order,
without requiring the visitor to already know what a control plane is.

## AC-C10 — It works without motion

**Given** `prefers-reduced-motion: reduce`
**Then** every claim on the page is still readable and every scene still
communicates, with no content reachable only by animating.

*Rejects:* a page that is blank until scrolled. Text that fades in and stays out.

## AC-C11 — It is fast on a cold visit

**Given** a first visit on a throttled connection
**Then** first meaningful paint is under 2.5 s (NFR-003), measured by Lighthouse
in CI rather than asserted.

## AC-C12 — Nothing on the delivery surface is decorative

**Given** any number shown on `/delivery`
**Then** it is derived from the repository or the GitHub API at build time, and a
reader can find where it came from.

*Rejects:* a hand-written test count. A hard-coded coverage badge. A sprint
velocity that is not computed from commits.
