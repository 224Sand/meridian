"""Workload definitions.

A workload is DATA, not a graph. Incident triage and change review run through
the same compiled orchestration graph with different task profiles, because the
central claim of a control plane is that it is workload-agnostic and a second
graph would prove nothing about that.

What a workload supplies:

  * how to turn its input into a retrieval query
  * how to frame the task for the model
  * how to score the risk of what it proposes - deterministically, never by
    asking the model how risky its own suggestion is
  * what its action is called, so the approval record reads as something a human
    can decide about
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def requires_approval(self) -> bool:
        """HIGH and above stop for a human.

        The boundary is set here rather than in the graph so that both workloads
        answer to the same rule and neither can quietly hold itself to a looser
        one.
        """
        return self in (RiskLevel.HIGH, RiskLevel.CRITICAL)


@dataclass(frozen=True, slots=True)
class WorkloadInput:
    """Everything a run starts from.

    `subject` identifies what is being reasoned about - an incident id, a change
    id. `body` is the free text. `context` carries structured facts the caller
    already knows, so the model is never asked to recall what the caller can
    simply state.
    """

    subject: str
    body: str
    context: dict[str, str]


class Workload(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def action_noun(self) -> str:
        """What this workload proposes, in words a reviewer can act on."""

    def build_query(self, request: WorkloadInput) -> str: ...

    def system_prompt(self) -> str: ...

    def score_risk(self, proposal: str, request: WorkloadInput) -> tuple[RiskLevel, str]: ...


#: Verbs that describe touching production. Matched on the PROPOSAL text, which
#: the model wrote, so this is a check on the model's output rather than a
#: request for the model to assess itself.
_DESTRUCTIVE = re.compile(
    r"\b(delete|drop|truncate|purge|revoke|rotate|failover|fail over|restart|"
    r"terminate|kill|scale down|roll back|rollback|redeploy|flush)\b",
    re.IGNORECASE,
)
_TIER_ZERO = re.compile(r"\btier\s*0\b", re.IGNORECASE)
_IRREVERSIBLE = re.compile(
    r"\b(drop\s+table|truncate|delete\s+from|purge|irreversible|cannot be undone)\b",
    re.IGNORECASE,
)


def _base_risk(proposal: str, request: WorkloadInput) -> tuple[RiskLevel, str]:
    """Risk from the shape of the proposal and the blast radius of its target.

    Deterministic on purpose. Asking a model how risky its own suggestion is
    produces a number that correlates with how confidently it phrased the
    suggestion, which is the opposite of what a risk gate needs.
    """
    tier = request.context.get("tier", "")
    touches_tier_zero = tier == "0" or bool(_TIER_ZERO.search(proposal))

    if _IRREVERSIBLE.search(proposal):
        return RiskLevel.CRITICAL, "the proposal is not reversible by redeploying"
    if _DESTRUCTIVE.search(proposal) and touches_tier_zero:
        return RiskLevel.HIGH, "a state-changing action on a Tier 0 service"
    if _DESTRUCTIVE.search(proposal):
        return RiskLevel.MEDIUM, "a state-changing action outside the Tier 0 path"
    if touches_tier_zero:
        return RiskLevel.MEDIUM, "advice concerning a Tier 0 service"
    return RiskLevel.LOW, "no state-changing action proposed"


@dataclass(frozen=True, slots=True)
class IncidentTriage:
    name: str = "incident_triage"
    action_noun: str = "remediation"

    def build_query(self, request: WorkloadInput) -> str:
        signature = request.context.get("signature", "")
        service = request.context.get("service", "")
        metrics = request.context.get("metrics", "")
        return " ".join(part for part in (request.body, signature, service, metrics) if part)

    def system_prompt(self) -> str:
        return (
            "You are triaging a production incident. Use ONLY the evidence "
            "provided. Every factual claim must be traceable to one of the "
            "numbered passages, cited as [n]. Where the evidence does not "
            "support a claim, say so instead of making it. Do not propose an "
            "action the evidence does not describe."
        )

    def score_risk(self, proposal: str, request: WorkloadInput) -> tuple[RiskLevel, str]:
        return _base_risk(proposal, request)


@dataclass(frozen=True, slots=True)
class ChangeReview:
    name: str = "change_review"
    action_noun: str = "review decision"

    def build_query(self, request: WorkloadInput) -> str:
        service = request.context.get("service", "")
        kind = request.context.get("change_kind", "")
        return " ".join(
            part for part in (request.body, service, kind, "change risk classification") if part
        )

    def system_prompt(self) -> str:
        return (
            "You are reviewing a proposed production change against policy and "
            "incident history. Use ONLY the evidence provided. Cite the policy "
            "clause or precedent behind every judgement as [n]. Where policy is "
            "silent, say it is silent rather than inferring what it would say."
        )

    def score_risk(self, proposal: str, request: WorkloadInput) -> tuple[RiskLevel, str]:
        level, reason = _base_risk(proposal, request)
        # A change already rolled back once escalates one level, matching
        # pol-change-risk-classification's automatic escalation rule. The
        # policy is in the corpus for the model to cite; it is enforced HERE so
        # that enforcement does not depend on the model having read it.
        if request.context.get("recently_rolled_back") == "true":
            order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            escalated = order[min(order.index(level) + 1, len(order) - 1)]
            return escalated, f"{reason}; escalated because this service was rolled back recently"
        return level, reason


WORKLOADS: dict[str, Workload] = {
    "incident_triage": IncidentTriage(),
    "change_review": ChangeReview(),
}


def get_workload(name: str) -> Workload:
    try:
        return WORKLOADS[name]
    except KeyError:
        raise KeyError(f"unknown workload {name!r}; known: {sorted(WORKLOADS)}") from None
