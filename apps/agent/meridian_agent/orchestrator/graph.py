"""The orchestration graph.

One compiled graph, two workloads. The workload is data carried in the state,
not a different topology, because the claim this system makes is that the
control plane is workload-agnostic and a second graph would prove nothing about
that.

The shape, and why each edge exists:

    classify           deterministic; no model call is made to decide what kind
                       of request this is (Principle 3)
    retrieve           hybrid, labelled degraded if the dense side is down
    assess_evidence    three bands from measured error budgets
      -> refuse            evidence clearly insufficient. Terminal.
      -> adjudicate        the band the deterministic signals cannot separate
      -> hypothesise       evidence clearly sufficient
    adjudicate         ONE cheap model call, only for the ambiguous band
    hypothesise        the reasoning call
    verify             every claim carries a citation, or loop back
      -> escalate          retry ceiling reached. Terminal, and emits nothing.
    propose_action     what to do about it
    risk_gate          deterministic scoring from the workload
      -> await_approval    at or above HIGH. TERMINAL.
      -> emit              below HIGH

`await_approval` has no edge to any node that does work. Reaching it ends the
run. A human decision starts a NEW run carrying the approval record, which is
ADR-0006 and exists because a prior system had an approval node wired straight
into registration - it collected a decision and controlled nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from meridian_agent.orchestrator.budget import SpendGuard
from meridian_agent.orchestrator.workloads import RiskLevel, Workload, WorkloadInput, get_workload
from meridian_agent.retrieval.evidence import EvidenceVerdict, assess
from meridian_agent.retrieval.hybrid import HybridRetriever, Retrieved
from meridian_agent.router.cache import SemanticCache
from meridian_agent.router.providers import Message
from meridian_agent.router.router import Router

#: Uncited-claim retries before the run escalates rather than emitting.
MAX_VERIFY_ATTEMPTS = 3
#: Ceiling on a single response. Also what the spend guard reserves against.
MAX_TOKENS = 700


class RunState(TypedDict, total=False):
    run_id: str
    workload: str
    request: WorkloadInput

    query: str
    hits: list[Retrieved]
    degraded: bool
    degraded_reason: str

    verdict: str
    evidence_rationale: str
    adjudicated: bool

    hypothesis: str
    citations: list[dict[str, Any]]
    uncited: list[str]
    attempts: int

    proposal: str
    risk: str
    risk_reason: str

    status: str
    events: list[dict[str, Any]]


@dataclass(slots=True)
class Dependencies:
    """Everything the graph reaches outside itself.

    Passed in rather than imported so a test can substitute any of it, and so
    two concurrent runs cannot share a spend ceiling or a router's disabled-provider
    state.
    """

    retriever: HybridRetriever
    router: Router
    guard: SpendGuard
    cache: SemanticCache | None = None
    #: Injected so the graph never reads a wall clock, matching the router.
    now: Callable[[], float] = field(default=lambda: 0.0)

    def complete(
        self,
        system: str,
        user: str,
        *,
        tier: Literal["fast", "large"],
        bypass_cache: bool = False,
    ) -> str:
        """The single model-call chokepoint.

        Every path that spends a token passes through here, which is what makes
        one spend guard sufficient (ADR-0007). Cache is consulted first, and a
        hit is ledgered at zero rather than skipped, so the saving is a number
        rather than a claim.

        `bypass_cache` exists because a semantic cache is actively harmful to a
        retry loop. A correction retry differs from its predecessor only by a
        short suffix naming what was wrong, so the two prompts measure 0.886
        similar against a 0.60 threshold: the cache returns the previous answer
        verbatim, the same claims stay uncited, and the run escalates every
        time. The ceiling was reachable and the retry could never succeed.

        This is ADR-0008's warning arriving from a direction it did not
        anticipate. The threshold is correct for telling two QUESTIONS apart and
        wrong for telling a prompt from its own correction.
        """
        messages = [Message("system", system), Message("user", user)]

        if self.cache is not None and not bypass_cache:
            hit = self.cache.lookup(messages, tier=tier, temperature=0.0)
            if hit is not None:
                self.guard.record_cache_hit(hit.tokens_in, hit.tokens_out)
                return hit.response

        # Reserve BEFORE the call. A reservation after the response is accounting.
        estimated_in = sum(len(m.content) // 3 for m in messages)
        estimate = self.guard.reserve(
            self.router.providers[0].name if self.router.providers else "unknown",
            tier,
            max_tokens_in=estimated_in,
            max_tokens_out=MAX_TOKENS,
        )

        result = self.router.complete(messages, tier=tier, max_tokens=MAX_TOKENS, temperature=0.0)
        self.guard.record(
            result.provider,
            result.completion.model,
            estimated_usd=estimate,
            tokens_in=result.completion.tokens_in,
            tokens_out=result.completion.tokens_out,
        )
        if self.cache is not None:
            self.cache.store_response(
                messages,
                tier=tier,
                temperature=0.0,
                response=result.completion.text,
                tokens_in=result.completion.tokens_in,
                tokens_out=result.completion.tokens_out,
            )
        return result.completion.text


def _event(state: RunState, name: str, **detail: Any) -> list[dict[str, Any]]:
    return [*state.get("events", []), {"node": name, **detail}]


# ── Nodes ──────────────────────────────────────────────────────────────────


def classify(state: RunState, deps: Dependencies) -> RunState:
    """Decide what is being asked. No model call.

    A typed rule decides this, so no token is spent establishing something the
    caller already told us.
    """
    workload = get_workload(state["workload"])
    query = workload.build_query(state["request"])
    return {
        "query": query,
        "attempts": 0,
        "status": "running",
        "events": _event(state, "classify", workload=workload.name),
    }


def retrieve(state: RunState, deps: Dependencies) -> RunState:
    result = deps.retriever.search(state["query"])
    return {
        "hits": list(result.hits),
        "degraded": result.degraded,
        "degraded_reason": result.degraded_reason,
        "events": _event(state, "retrieve", hits=len(result.hits), degraded=result.degraded),
    }


def assess_evidence(state: RunState, deps: Dependencies) -> RunState:
    from meridian_agent.retrieval.hybrid import RetrievalResult

    result = RetrievalResult(
        query=state["query"],
        hits=tuple(state.get("hits", [])),
        degraded=state.get("degraded", False),
        degraded_reason=state.get("degraded_reason", ""),
    )
    assessment = assess(state["query"], result)
    return {
        "verdict": str(assessment.verdict),
        "evidence_rationale": assessment.rationale,
        "events": _event(
            state,
            "assess_evidence",
            verdict=str(assessment.verdict),
            score=round(assessment.combined_score, 3),
        ),
    }


def adjudicate(state: RunState, deps: Dependencies) -> RunState:
    """One cheap model call, for the band the deterministic signals cannot split.

    Asked as a closed question about the EVIDENCE rather than an open one about
    the topic, so the answer cannot come from the model's own knowledge. That
    distinction is the whole reason this step is allowed to exist.
    """
    passages = "\n\n".join(
        f"[{i + 1}] {hit.chunk.body}" for i, hit in enumerate(state.get("hits", [])[:5])
    )
    answer = deps.complete(
        "You decide whether a set of passages contains the information needed to "
        "answer a question. Answer with exactly one word: YES or NO. Answer NO if "
        "the passages discuss the subject without stating what was asked for.",
        f"Question: {state['query']}\n\nPassages:\n{passages}\n\nDoes the evidence "
        "contain what is needed to answer? Reply YES or NO.",
        tier="fast",
    )
    sufficient = answer.strip().upper().startswith("YES")
    return {
        "adjudicated": True,
        "verdict": str(EvidenceVerdict.SUFFICIENT if sufficient else EvidenceVerdict.INSUFFICIENT),
        "evidence_rationale": f"adjudicated: model answered {answer.strip()[:20]!r}",
        "events": _event(state, "adjudicate", sufficient=sufficient),
    }


def hypothesise(state: RunState, deps: Dependencies) -> RunState:
    """Produce the assessment, or correct the previous one.

    A retry MUST name what was wrong with the last attempt. The first version of
    this node re-sent an identical prompt, which meant:

      * the semantic cache returned the previous answer verbatim
      * even on a miss, an identical prompt at temperature 0 reproduces it

    so all three attempts were byte-identical, the same claims stayed uncited,
    and the run escalated every time. The retry ceiling was reachable and the
    retry itself could never succeed. Observed on the first live run.
    """
    workload = get_workload(state["workload"])
    passages = "\n\n".join(
        f"[{i + 1}] {hit.chunk.body}" for i, hit in enumerate(state.get("hits", [])[:5])
    )

    uncited = state.get("uncited", [])
    if uncited:
        correction = (
            "\n\nYour previous answer made these statements with NO citation. "
            "Rewrite it so each one either carries a [n] marker pointing at a "
            "passage above, or is removed. Do not add claims the passages do "
            "not support.\n" + "\n".join(f"  - {claim[:200]}" for claim in uncited[:6])
        )
    else:
        correction = ""

    text = deps.complete(
        workload.system_prompt(),
        f"Evidence:\n{passages}\n\nSubject: {state['request'].subject}\n"
        f"{state['request'].body}\n\nGive your assessment. Cite every claim as [n]." + correction,
        tier="large",
        # A correction must never be served from cache. The retry prompt differs
        # from its predecessor only by the correction suffix - measured 0.886
        # similar against a 0.60 threshold - so the cache would return the
        # previous answer and the loop could never succeed.
        bypass_cache=bool(uncited),
    )
    return {
        "hypothesis": text,
        "attempts": state.get("attempts", 0) + 1,
        # Cleared so `verify` judges THIS attempt. Leaving the previous list in
        # place would make the correction prompt grow with stale claims that the
        # rewrite may already have fixed.
        "uncited": [],
        "events": _event(
            state,
            "hypothesise",
            attempt=state.get("attempts", 0) + 1,
            correcting=len(uncited),
        ),
    }


def verify(state: RunState, deps: Dependencies) -> RunState:
    """Check every claim carries a citation. Deterministic.

    Sentences are the unit because a citation attaches to a statement, not to a
    paragraph. A model that cites once at the end has cited one sentence.
    """
    from meridian_agent.orchestrator.citations import extract_citations, uncited_claims

    hits = state.get("hits", [])
    citations = extract_citations(state.get("hypothesis", ""), hits)
    uncited = uncited_claims(state.get("hypothesis", ""))
    return {
        "citations": citations,
        "uncited": uncited,
        "events": _event(state, "verify", cited=len(citations), uncited=len(uncited)),
    }


def refuse(state: RunState, deps: Dependencies) -> RunState:
    return {
        "status": "refused",
        "hypothesis": "",
        "events": _event(state, "refuse", reason=state.get("evidence_rationale", "")),
    }


def escalate(state: RunState, deps: Dependencies) -> RunState:
    """Retry ceiling reached. Emits nothing.

    An answer with uncited claims is the failure mode this system exists to
    prevent, so the ceiling escalates rather than shipping the best attempt.
    """
    return {
        "status": "escalated",
        "events": _event(state, "escalate", uncited=len(state.get("uncited", []))),
    }


def propose_action(state: RunState, deps: Dependencies) -> RunState:
    workload = get_workload(state["workload"])
    text = deps.complete(
        workload.system_prompt(),
        f"Assessment:\n{state.get('hypothesis', '')}\n\n"
        f"State the {workload.action_noun} you recommend, in one or two sentences. "
        "Recommend only what the evidence describes.",
        tier="large",
    )
    return {"proposal": text, "events": _event(state, "propose_action")}


def risk_gate(state: RunState, deps: Dependencies) -> RunState:
    workload = get_workload(state["workload"])
    level, reason = workload.score_risk(state.get("proposal", ""), state["request"])
    return {
        "risk": str(level),
        "risk_reason": reason,
        "events": _event(state, "risk_gate", risk=str(level)),
    }


def await_approval(state: RunState, deps: Dependencies) -> RunState:
    """TERMINAL. No outgoing edge to any node that does work.

    A human decision starts a NEW run carrying the approval record. This is not
    a style choice: a prior system wired its approval node straight into
    registration, so the item registered regardless of what the reviewer
    answered. The control rendered, collected a decision, and did nothing.
    """
    return {
        "status": "awaiting_approval",
        "events": _event(state, "await_approval", risk=state.get("risk", "")),
    }


def emit(state: RunState, deps: Dependencies) -> RunState:
    return {"status": "completed", "events": _event(state, "emit")}


# ── Routing ────────────────────────────────────────────────────────────────


def route_after_evidence(state: RunState) -> str:
    verdict = state.get("verdict", "")
    if verdict == EvidenceVerdict.INSUFFICIENT:
        return "refuse"
    if verdict == EvidenceVerdict.AMBIGUOUS:
        return "adjudicate"
    return "hypothesise"


def route_after_adjudication(state: RunState) -> str:
    return "hypothesise" if state.get("verdict") == EvidenceVerdict.SUFFICIENT else "refuse"


def route_after_verify(state: RunState) -> str:
    if not state.get("uncited"):
        return "propose_action"
    if state.get("attempts", 0) >= MAX_VERIFY_ATTEMPTS:
        return "escalate"
    return "hypothesise"


def route_after_risk(state: RunState) -> str:
    return "await_approval" if RiskLevel(state["risk"]).requires_approval else "emit"


# ── Assembly ───────────────────────────────────────────────────────────────


def build_graph(deps: Dependencies) -> CompiledStateGraph[RunState, None, RunState, RunState]:
    """Compile the one graph both workloads run on."""
    builder = StateGraph(RunState)

    for name, function in (
        ("classify", classify),
        ("retrieve", retrieve),
        ("assess_evidence", assess_evidence),
        ("adjudicate", adjudicate),
        ("hypothesise", hypothesise),
        ("verify", verify),
        ("refuse", refuse),
        ("escalate", escalate),
        ("propose_action", propose_action),
        ("risk_gate", risk_gate),
        ("await_approval", await_approval),
        ("emit", emit),
    ):
        builder.add_node(name, lambda state, f=function: f(state, deps))

    builder.set_entry_point("classify")
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "assess_evidence")
    builder.add_conditional_edges(
        "assess_evidence",
        route_after_evidence,
        {"refuse": "refuse", "adjudicate": "adjudicate", "hypothesise": "hypothesise"},
    )
    builder.add_conditional_edges(
        "adjudicate",
        route_after_adjudication,
        {"refuse": "refuse", "hypothesise": "hypothesise"},
    )
    builder.add_edge("hypothesise", "verify")
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {"hypothesise": "hypothesise", "escalate": "escalate", "propose_action": "propose_action"},
    )
    builder.add_edge("propose_action", "risk_gate")
    builder.add_conditional_edges(
        "risk_gate",
        route_after_risk,
        {"await_approval": "await_approval", "emit": "emit"},
    )

    # Terminal states. await_approval reaches END and nothing else - there is no
    # path from it back into the graph, which is the ADR-0006 invariant.
    builder.add_edge("refuse", END)
    builder.add_edge("escalate", END)
    builder.add_edge("await_approval", END)
    builder.add_edge("emit", END)

    return builder.compile()


def run(
    deps: Dependencies, workload: str, request: WorkloadInput, run_id: str | None = None
) -> RunState:
    graph = build_graph(deps)
    initial: RunState = {
        "run_id": run_id or f"run-{uuid.uuid4().hex[:12]}",
        "workload": workload,
        "request": request,
        "events": [],
    }
    return cast(RunState, graph.invoke(initial))


__all__ = [
    "Dependencies",
    "RunState",
    "Workload",
    "build_graph",
    "run",
]
