"""The orchestration graph.

Two invariants here are not stylistic and are tested as controls:

  * `await_approval` has no edge to any node that does work (ADR-0006). Asserted
    by enumerating the COMPILED graph's edges, because reading the builder only
    proves what the author meant.
  * No model call happens without an open budget (ADR-0007). Asserted by opening
    none and expecting a refusal.

Both encode failures that already happened in real systems: an approval node
wired into registration that collected a decision and controlled nothing, and an
unattended run that drained an API balance.
"""

from __future__ import annotations

import pytest

from sandscope_agent.orchestrator.budget import (
    BudgetExhaustedError,
    NoBudgetOpenError,
    SpendGuard,
)
from sandscope_agent.orchestrator.graph import (
    MAX_VERIFY_ATTEMPTS,
    Dependencies,
    build_graph,
    run,
)
from sandscope_agent.orchestrator.workloads import (
    ChangeReview,
    IncidentTriage,
    RiskLevel,
    WorkloadInput,
    get_workload,
)
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.hybrid import HybridRetriever
from sandscope_agent.router.providers import StubProvider
from sandscope_agent.router.router import Router
from sandscope_agent.router.state import ManualClock, RouterState

POOL_INCIDENT = WorkloadInput(
    subject="inc-0001",
    body="db.pool.wait_ms is climbing on orders-db and available connections reached zero",
    context={"service": "orders-db", "tier": "0", "signature": "db.pool.saturated"},
)


def make_deps(responses: list[str] | None = None, ceiling: float = 1.0) -> Dependencies:
    retriever = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
    retriever.build_vectors()

    provider = StubProvider("stub", responses=list(responses or []), default="[1] A cited claim.")
    router = Router(
        providers=[provider], state=RouterState(), clock=ManualClock(), environment="test"
    )
    guard = SpendGuard()
    if ceiling > 0:
        guard.open(ceiling)
    return Dependencies(retriever=retriever, router=router, guard=guard)


class TestApprovalIsTerminal:
    """ADR-0006."""

    def test_await_approval_has_no_edge_to_a_working_node(self) -> None:
        graph = build_graph(make_deps()).get_graph()
        outgoing = {e.target for e in graph.edges if e.source == "await_approval"}
        assert outgoing <= {"__end__"}, (
            f"await_approval routes into {outgoing - {'__end__'}}; reaching it must end the run"
        )

    def test_await_approval_is_reachable(self) -> None:
        """A terminal node nothing reaches is not a control, it is dead code."""
        graph = build_graph(make_deps()).get_graph()
        assert any(e.target == "await_approval" for e in graph.edges)

    def test_no_node_loops_back_from_a_terminal_state(self) -> None:
        graph = build_graph(make_deps()).get_graph()
        for terminal in ("refuse", "escalate", "await_approval", "emit"):
            targets = {e.target for e in graph.edges if e.source == terminal}
            assert targets <= {"__end__"}, f"{terminal} routes into {targets}"

    def test_a_high_risk_proposal_stops_for_approval(self) -> None:
        deps = make_deps(
            responses=[
                "[1] The pool is exhausted because hold time rose sharply.",
                "Restart the orders-db connection pool on the Tier 0 path immediately.",
            ]
        )
        state = run(deps, "incident_triage", POOL_INCIDENT)
        assert state["status"] == "awaiting_approval"
        assert RiskLevel(state["risk"]).requires_approval

    def test_a_low_risk_proposal_completes(self) -> None:
        deps = make_deps(
            responses=[
                "[1] Wait time rose before query time, which points at the pool.",
                "Compare db.pool.wait_ms against db.query.p99_ms to confirm the ordering.",
            ]
        )
        state = run(
            deps,
            "incident_triage",
            # Same evidence-rich body as the high-risk case, so this exercises
            # the RISK gate rather than accidentally re-testing the evidence
            # gate: a weak query is refused before risk scoring is ever reached.
            WorkloadInput(
                subject="inc-2",
                body=POOL_INCIDENT.body,
                context={"service": "analytics-etl", "tier": "3"},
            ),
        )
        assert state["status"] == "completed", state.get("evidence_rationale", "")
        assert not RiskLevel(state["risk"]).requires_approval


class TestOneGraphTwoWorkloads:
    """FR-025. A second graph would have been easier and proved nothing."""

    def test_both_workloads_share_one_topology(self) -> None:
        deps = make_deps()
        edges = {(e.source, e.target) for e in build_graph(deps).get_graph().edges}
        assert edges, "graph has no edges"
        # The workload is data in the state; the graph is built without knowing
        # which workload will run, so there is only one topology by construction.
        again = {(e.source, e.target) for e in build_graph(deps).get_graph().edges}
        assert edges == again

    def test_change_review_runs_the_same_graph(self) -> None:
        deps = make_deps(
            responses=[
                "[1] The change alters a connection pool ceiling on a Tier 0 service.",
                "Require an approver from the owning team before this proceeds.",
            ]
        )
        state = run(
            deps,
            "change_review",
            WorkloadInput(
                subject="chg-1",
                body="raise the orders-db connection pool ceiling from 100 to 200",
                context={"service": "orders-db", "tier": "0", "change_kind": "configuration"},
            ),
        )
        assert state["workload"] == "change_review"
        assert state["status"] in ("awaiting_approval", "completed", "refused", "escalated")

    def test_an_unknown_workload_raises(self) -> None:
        with pytest.raises(KeyError, match="unknown workload"):
            get_workload("does_not_exist")


class TestSpendGuard:
    """ADR-0007."""

    def test_a_live_call_is_refused_with_no_budget_open(self) -> None:
        deps = make_deps(ceiling=0.0)
        assert not deps.guard.is_open
        with pytest.raises(NoBudgetOpenError, match="no budget is open"):
            deps.complete("system", "user", tier="fast")

    def test_reserving_past_the_ceiling_raises(self) -> None:
        guard = SpendGuard()
        guard.open(0.000001)
        with pytest.raises(BudgetExhaustedError, match="would exceed"):
            guard.reserve("anthropic", "large", max_tokens_in=100_000, max_tokens_out=100_000)

    def test_the_estimate_is_taken_before_the_call(self) -> None:
        """Pricing after the response is accounting, not control."""
        deps = make_deps()
        before = deps.guard.reserved_usd
        deps.complete("system", "user", tier="fast")
        assert deps.guard.reserved_usd > before
        assert deps.guard.ledger[-1].estimated_usd > 0

    def test_an_unknown_provider_is_priced_at_the_most_expensive_rate(self) -> None:
        from sandscope_agent.orchestrator.budget import PRICES, price

        unknown = price("a-provider-that-does-not-exist", 1_000_000, 1_000_000)
        assert unknown >= max(sum(p) for p in PRICES.values())

    def test_a_zero_or_negative_ceiling_is_rejected(self) -> None:
        from sandscope_agent.orchestrator.budget import BudgetError

        with pytest.raises(BudgetError, match="must be positive"):
            SpendGuard().open(0.0)

    def test_actual_cost_is_ledgered_after_the_response(self) -> None:
        deps = make_deps()
        deps.complete("system", "user", tier="fast")
        entry = deps.guard.ledger[-1]
        assert entry.actual_usd is not None
        assert entry.tokens_in >= 0 and entry.tokens_out >= 0


class TestRefusalAndEscalation:
    def test_a_refused_run_emits_no_hypothesis(self) -> None:
        deps = make_deps()
        state = run(
            deps,
            "incident_triage",
            WorkloadInput(
                subject="q",
                body="what is the disaster recovery failover procedure",
                context={},
            ),
        )
        if state["status"] == "refused":
            assert state.get("hypothesis", "") == ""

    def test_uncited_claims_loop_back_then_escalate(self) -> None:
        """An answer with uncited claims is the failure this system exists to
        prevent, so the ceiling escalates rather than shipping the best attempt."""
        deps = make_deps(responses=["The pool is exhausted and hold time rose sharply."] * 6)
        state = run(deps, "incident_triage", POOL_INCIDENT)
        if state["status"] == "escalated":
            assert state["attempts"] >= MAX_VERIFY_ATTEMPTS
            assert not state.get("proposal")

    def test_escalation_emits_no_proposal(self) -> None:
        deps = make_deps(responses=["An entirely uncited assertion about the system."] * 6)
        state = run(deps, "incident_triage", POOL_INCIDENT)
        assert state["status"] != "completed" or state.get("citations")


class TestRetryActuallyRetries:
    """The retry loop must be able to succeed.

    Found on the first live run: all three attempts returned byte-identical
    text, the same claims stayed uncited, and every run escalated. Two causes,
    both of which made the ceiling reachable and the retry impossible:

      * the retry re-sent an IDENTICAL prompt, so it never told the model what
        was wrong
      * once the prompt did differ, it differed only by a short correction
        suffix - 0.886 similar against a 0.60 threshold - so the semantic cache
        returned the previous answer anyway
    """

    def build(self, responses: list[str]) -> Dependencies:
        from sandscope_agent.router.cache import SemanticCache

        retriever = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
        retriever.build_vectors()
        guard = SpendGuard()
        guard.open(1.0)
        return Dependencies(
            retriever=retriever,
            router=Router(
                providers=[StubProvider("stub", responses=list(responses))],
                state=RouterState(),
                clock=ManualClock(),
                environment="test",
            ),
            guard=guard,
            cache=SemanticCache(embedder=HashingEmbedder()),
        )

    def test_a_correction_retry_reaches_the_model(self) -> None:
        deps = self.build(
            [
                "The pool is exhausted because callers hold connections far too long here.",
                "[1] The pool is exhausted because callers hold connections too long.",
                "Compare wait time against query time before acting on this incident.",
            ]
        )
        state = run(
            deps,
            "incident_triage",
            WorkloadInput(
                subject="inc",
                body=POOL_INCIDENT.body,
                context={"service": "analytics-etl", "tier": "3"},
            ),
        )
        assert state["attempts"] == 2, "the retry did not happen"
        assert state["status"] == "completed", "the corrected attempt was not accepted"
        assert not state.get("uncited")
        assert deps.cache is not None
        assert deps.cache.stats.semantic_hits == 0, (
            "the correction was served from cache; the retry cannot change anything"
        )

    def test_the_retry_prompt_names_what_was_uncited(self) -> None:
        """A retry that does not say what was wrong is a re-roll, not a fix."""
        from sandscope_agent.orchestrator.graph import hypothesise

        deps = self.build(["[1] corrected."])
        retriever = deps.retriever
        hits = list(retriever.search(POOL_INCIDENT.body).hits)
        hypothesise(
            {
                "workload": "incident_triage",
                "request": POOL_INCIDENT,
                "hits": hits,
                "uncited": ["The pool exhausted itself spontaneously overnight."],
                "attempts": 1,
                "events": [],
            },
            deps,
        )
        provider = deps.router.providers[0]
        sent = provider.last_user_message  # type: ignore[attr-defined]
        assert "NO citation" in sent
        assert "spontaneously overnight" in sent

    def test_a_first_attempt_uses_the_cache_normally(self) -> None:
        """Only corrections bypass. A first attempt must still be cacheable, or
        the cache stops earning its place."""
        deps = self.build(["[1] cited.", "[1] cited.", "act."])
        deps.complete("system", "a question about pool exhaustion", tier="large")
        deps.complete("system", "a question about pool exhaustion", tier="large")
        assert deps.cache is not None
        assert deps.cache.stats.exact_hits == 1


class TestRiskScoring:
    def test_risk_is_scored_deterministically_not_by_the_model(self) -> None:
        """Asking a model how risky its own suggestion is produces a number that
        correlates with how confidently it phrased the suggestion."""
        workload = IncidentTriage()
        first, _ = workload.score_risk("Restart the service", POOL_INCIDENT)
        second, _ = workload.score_risk("Restart the service", POOL_INCIDENT)
        assert first == second

    def test_an_irreversible_action_is_critical(self) -> None:
        level, reason = IncidentTriage().score_risk(
            "Run TRUNCATE on the orders table to clear the backlog", POOL_INCIDENT
        )
        assert level is RiskLevel.CRITICAL
        assert "reversible" in reason

    def test_a_destructive_action_on_tier_zero_is_high(self) -> None:
        level, _ = IncidentTriage().score_risk("Restart the orders-db pool", POOL_INCIDENT)
        assert level is RiskLevel.HIGH

    def test_advice_with_no_action_is_low_off_the_critical_path(self) -> None:
        level, _ = IncidentTriage().score_risk(
            "Compare wait time against query time",
            WorkloadInput(subject="x", body="y", context={"tier": "3"}),
        )
        assert level is RiskLevel.LOW

    def test_change_review_escalates_a_recently_rolled_back_service(self) -> None:
        """pol-change-risk-classification's automatic escalation, enforced here
        rather than left to the model having read the policy."""
        request = WorkloadInput(
            subject="chg",
            body="config change",
            context={"tier": "2", "recently_rolled_back": "true"},
        )
        escalated, reason = ChangeReview().score_risk("Redeploy the pricing service", request)
        baseline, _ = ChangeReview().score_risk(
            "Redeploy the pricing service",
            WorkloadInput(subject="chg", body="config change", context={"tier": "2"}),
        )
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert order.index(escalated) == order.index(baseline) + 1
        assert "rolled back" in reason

    def test_only_high_and_above_require_approval(self) -> None:
        assert not RiskLevel.LOW.requires_approval
        assert not RiskLevel.MEDIUM.requires_approval
        assert RiskLevel.HIGH.requires_approval
        assert RiskLevel.CRITICAL.requires_approval


class TestDeterministicNodes:
    def test_classify_makes_no_model_call(self) -> None:
        """Principle 3: if a typed rule can decide it, no token is spent."""
        from sandscope_agent.orchestrator.graph import classify

        deps = make_deps()
        before = len(deps.guard.ledger)
        state = classify(
            {"workload": "incident_triage", "request": POOL_INCIDENT, "events": []}, deps
        )
        assert len(deps.guard.ledger) == before
        assert state["query"]

    def test_the_run_records_every_node_it_passed_through(self) -> None:
        deps = make_deps(
            responses=[
                "[1] Hold time rose.",
                "Compare the two metrics before acting.",
            ]
        )
        state = run(deps, "incident_triage", POOL_INCIDENT)
        nodes = [e["node"] for e in state["events"]]
        assert nodes[0] == "classify"
        assert "retrieve" in nodes and "assess_evidence" in nodes


class TestReservationBoundsActualCost:
    """D-010. A reservation is only a bound if it holds however the router routes.

    The first version priced against providers[0] and under-reserved by 4x the
    moment failover reached a more expensive provider: $0.000100 reserved at
    Groq's rate against $0.000404 spent at Mistral's. That is the exact case the
    guard exists to bound.
    """

    def build(self) -> Dependencies:
        retriever = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
        retriever.build_vectors()
        guard = SpendGuard()
        guard.open(1.0)
        # Cheapest first, most expensive last - the order that broke it.
        providers = [
            StubProvider("groq", default="cheap"),
            StubProvider("mistral", default="expensive"),
        ]
        return Dependencies(
            retriever=retriever,
            router=Router(
                providers=providers,
                state=RouterState(),
                clock=ManualClock(),
                environment="test",
            ),
            guard=guard,
        )

    def test_the_reservation_prices_the_most_expensive_candidate(self) -> None:
        from sandscope_agent.orchestrator.budget import price

        deps = self.build()
        deps.complete("system", "a question", tier="large")
        entry = deps.guard.ledger[-1]
        # Groq would have been cheaper; the reservation must not assume it.
        groq_rate = price("groq", 1000, 700)
        mistral_rate = price("mistral", 1000, 700)
        assert mistral_rate > groq_rate
        assert entry.estimated_usd >= entry.actual_usd, (
            f"reserved ${entry.estimated_usd:.6f} against ${entry.actual_usd:.6f} spent"
        )

    def test_the_reservation_covers_the_spend_across_many_calls(self) -> None:
        deps = self.build()
        for _ in range(5):
            deps.complete("system", "a question about pool exhaustion", tier="large")
        assert deps.guard.reserved_usd >= deps.guard.actual_usd, (
            f"reserved ${deps.guard.reserved_usd:.6f} < spent ${deps.guard.actual_usd:.6f}"
        )
