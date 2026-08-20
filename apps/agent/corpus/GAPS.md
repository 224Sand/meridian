# Deliberate gaps in this corpus

This file exists so that the evaluation harness has genuinely unanswerable
questions to score refusal against.

If the corpus covered everything, "correct refusal" could not be measured at
all: every refusal would be a false negative, and the refusal threshold could be
set to zero without any suite noticing. The gaps below are therefore load
bearing, not an oversight.

## Not covered anywhere in the corpus

| Topic | Why it is absent |
|---|---|
| Disk exhaustion | No runbook, no postmortem, no policy. A plausible question with no grounding. |
| Data retention and deletion obligations | `pol-data-freshness` explicitly disclaims it. |
| DNS resolution failures | No document mentions DNS. |
| Rate limiting and quota policy for external API consumers | Not authored. |
| Cost and budget ownership for infrastructure | Not authored. |
| On-call rota, shift handover, compensation | Not authored. |
| Regional failover and disaster recovery | Estate is single region; no failover document exists. |
| Kubernetes, service mesh, or scheduler behaviour | No document names the orchestration platform. |
| Cost of a change, or budget approval for one | Change risk is classified on blast radius only. |
| Feature flags, experiments, progressive delivery | Rollout is by region; no flag system is described. |
| Security incident response, breach handling | Out of scope for this corpus. |
| Why the platform's restart events were not routed to team alerting | Explicitly left open in `pm-2026-07-fraud-scoring-restart-loop`. |

## Partially covered — the harder case

These have *related* material that a retrieval system will happily return, which
makes them the more useful test. A weak refusal check will answer them from
adjacent context.

| Question | What the corpus actually has |
|---|---|
| What is the pool ceiling on `sessions-cache`? | A ceiling of 100 is documented for `orders-db` only. |
| Which team owns `edge-gateway` out of hours? | Ownership is documented; the out-of-hours rota is not. |
| What is the SLO for checkout availability? | Severity definitions exist. No SLO is stated anywhere. |
| How long are heap dumps retained? | Capturing a dump is documented. Retention is not. |
| How long is the observation period between regions? | Its existence and purpose are documented; no duration is stated anywhere. |
| What is the minimum time between regional rollout steps? | Same gap, asked a second way. |

A system that answers any row in this table has failed, and the failure is
specifically the one this product exists to prevent.

## A correction, kept visible

"Who approves an emergency change during an incident?" was listed here and
should not have been. `pol-change-risk-classification` states that emergency
changes are governed by the incident commander, which answers it. The evidence
gate scored it answerable, the author had marked it unanswerable, and the author
was wrong.

It is recorded rather than quietly deleted because a gap list is itself a claim
about the corpus, and claims in this project are corrected in the open.
