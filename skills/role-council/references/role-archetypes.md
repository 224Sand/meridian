# Role archetypes

A library of role lenses, not a checklist to apply in full every time. Pick the subset that's
load-bearing for the project at hand (see SKILL.md step 1). Each entry is a brief: what this
role instinctively looks for, and the kind of question they'd ask of an artifact. Use the brief
to ground a reaction — never to script one; the artifact still has to earn the reaction.

This list is deliberately not exhaustive. If a project needs a lens not listed here (Legal /
Compliance on a fintech repo, a Localization lead on a multi-region product, a Game Designer on
a game repo), write a one-paragraph brief in the same shape and use it — the pattern matters
more than the roster.

## Delivery roles

**Business Analyst (BA)** — Owns the link between a stated requirement and what got built.
Asks: does this artifact trace back to a real, logged requirement, or did scope drift in without
anyone deciding it should? Flags gaps between what was asked for and what shipped, and flags
requirements that were never actually validated against anything.

**Product Manager (PM)** — Owns why this exists and whether it moves a real metric. Asks: does
this serve the stated goal, or is it effort spent because it was interesting to build? Skeptical
of scope that expanded past what the product needed, and of decisions justified by "it would be
nice" rather than by user or business impact.

**Technical Program Manager (TPM)** — Owns the plan, the dependencies, and whether the sequence
made sense. Asks: was this the right thing to build at this point in the plan, did it block or
get blocked by something else, and does the timeline/effort claimed match what actually
happened? Notices when a "quick fix" consumed disproportionate calendar time or masked a
dependency nobody planned for.

**Solutions Architect / Technical Lead** — Owns the shape of the system across components. Asks:
does this decision compose with the rest of the architecture, what did it cost in coupling or
flexibility, and what was the alternative that got rejected — and why? Suspicious of a decision
record that lists only advantages.

**Software Engineer / Developer** — Owns whether the implementation is sound on its own terms.
Asks: is this code correct, maintainable, and does it do what it claims — independent of whether
it was the right thing to build at all. Reacts to implementation quality, not scope.

**QA / SDET** — Owns whether a claim of "it works" is actually demonstrated. Asks: what proves
this, was it tested before or after the defect, and does the fix address the root cause or just
the symptom that got reported? Flags a defect that was "fixed" without a test that would catch
its regression.

**DevOps / SRE** — Owns whether this runs reliably in production, not just on a laptop. Asks:
what happens when this fails, is the failure mode graceful, and does this decision survive being
deployed, restarted, or scaled? Reacts to anything that works locally but has an unstated
assumption about its environment.

**Application Security Engineer (AppSec)** — Owns the threat surface. Asks: what does this
expose, to whom, and was that a deliberate trade-off or an oversight? Reacts to secrets, auth
boundaries, and anything that trusts input it shouldn't.

## Stakeholder / process roles

**UX / UI Designer** — Owns whether the experience communicates what it's supposed to. Asks:
does this read clearly to someone seeing it cold, and does the visual hierarchy match what
actually matters? Reacts on clarity and consistency, not on personal taste.

**Data Engineer** — Owns whether data flowing through the system is correct and well-shaped.
Asks: where does this data come from, is the schema/contract stable, and what breaks downstream
if it isn't?

**ML Engineer / Data Scientist** (only for projects that train or serve models) — Owns whether a
model claim is actually measured. Asks: what's the evaluation, against what baseline, on what
sample size, and does the reported metric survive being checked? Deeply skeptical of a result
that looks too good on a small or convenient sample.

**Scrum Master** — Owns the health of the process itself, not any one deliverable. Asks: did
this follow the process the team committed to, and if not, was the deviation named and owned, or
did it just happen silently? Flags a retrospective commitment that was made and then never
honoured.

**Technical Writer** — Owns whether anyone outside the author can understand this without asking
them. Asks: is this documented at the level someone unfamiliar with the decision would need?

**Stakeholder / Subject-Matter Expert (SME)** — Owns domain correctness the engineering team
can't self-check. Asks: is this actually true about the domain, or does it just look plausible
to someone without domain context?

**Release Manager** — Owns whether this is safe to ship now. Asks: what's the blast radius if
this is wrong, and is there a way back out if it is?

**Executive Sponsor** — Owns budget, priority, and go/no-go. Asks: was this worth what it cost
in time or money, and does it move something the sponsor actually asked for?
