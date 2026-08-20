"""Smoke test: the assembled system executes real runs.

This is the layer that was missing. Four sprints and 412 passing unit and
integration tests produced a system that had never once been run end to end,
and the first execution found three defects in ten minutes (D-005, D-006,
D-007). One was an emergent interaction between two individually correct,
individually tested components, unreachable by any unit test.

Runs offline against stubbed providers so it executes on every push. It is not a
substitute for a live run; it is the floor beneath one.

    python scripts/smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sandscope_agent.orchestrator.budget import BudgetError, NoBudgetOpenError, SpendGuard
from sandscope_agent.orchestrator.graph import Dependencies, run
from sandscope_agent.orchestrator.workloads import WorkloadInput
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.hybrid import HybridRetriever
from sandscope_agent.router.cache import SemanticCache
from sandscope_agent.router.providers import StubProvider
from sandscope_agent.router.router import Router
from sandscope_agent.router.state import ManualClock, RouterState

POOL_BODY = "db.pool.wait_ms is climbing on orders-db and available connections reached zero"


def build(responses: list[str]) -> Dependencies:
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


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    return condition


def main() -> int:
    results: list[bool] = []
    print("smoke: the assembled system\n")

    deps = build(["[1] Hold time rose before query time.", "Compare the two metrics first."])
    state = run(
        deps,
        "incident_triage",
        WorkloadInput(
            subject="inc-smoke", body=POOL_BODY, context={"service": "analytics-etl", "tier": "3"}
        ),
    )
    results.append(
        check(
            "a well-evidenced incident completes",
            state["status"] == "completed",
            f"status={state['status']} citations={len(state.get('citations', []))}",
        )
    )
    results.append(check("every emitted claim carries a citation", not state.get("uncited")))

    deps = build(
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
            subject="inc-retry", body=POOL_BODY, context={"service": "analytics-etl", "tier": "3"}
        ),
    )
    results.append(
        check(
            "an uncited answer is corrected on retry (D-005, D-006)",
            state["attempts"] == 2 and state["status"] == "completed",
            f"attempts={state['attempts']} status={state['status']} "
            f"cache_hits={deps.cache.stats.semantic_hits if deps.cache else 0}",
        )
    )

    deps = build(
        [
            "[1] The pool is exhausted because hold time rose.",
            "Restart the orders-db connection pool on the Tier 0 path immediately.",
        ]
    )
    state = run(
        deps,
        "incident_triage",
        WorkloadInput(
            subject="inc-risk", body=POOL_BODY, context={"service": "orders-db", "tier": "0"}
        ),
    )
    results.append(
        check(
            "a high-risk remediation stops for approval",
            state["status"] == "awaiting_approval",
            f"risk={state.get('risk')}",
        )
    )

    deps = build(["[1] anything at all."])
    state = run(
        deps,
        "incident_triage",
        WorkloadInput(
            subject="q", body="what is the disaster recovery failover procedure", context={}
        ),
    )
    results.append(check("an unsupported question is refused", state["status"] == "refused"))

    deps = build(
        [
            "[1] The change alters a pool ceiling on a Tier 0 service.",
            "Require an approver from the owning team.",
        ]
    )
    state = run(
        deps,
        "change_review",
        WorkloadInput(
            subject="chg",
            body="raise the orders-db connection pool ceiling from 100 to 200",
            context={"service": "orders-db", "tier": "0", "change_kind": "configuration"},
        ),
    )
    results.append(
        check(
            "change review runs the same graph",
            state["workload"] == "change_review",
            f"status={state['status']}",
        )
    )

    try:
        SpendGuard().open(0.0)
        refused = False
    except BudgetError:
        refused = True
    results.append(check("a zero budget ceiling is refused (D-007)", refused))

    unopened = Dependencies(
        retriever=deps.retriever, router=deps.router, guard=SpendGuard(), cache=None
    )
    try:
        unopened.complete("s", "u", tier="fast")
        guarded = False
    except NoBudgetOpenError:
        guarded = True
    results.append(check("no model call without an open budget (ADR-0007)", guarded))

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
