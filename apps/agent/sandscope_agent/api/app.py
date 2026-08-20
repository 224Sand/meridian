"""FastAPI surface for the agent runtime.

Runs on Hugging Face Spaces behind the Next.js BFF (ADR-0001, ADR-0003). The
browser never reaches this service directly and never holds its token.

One design decision worth stating: a run STREAMS WITHIN A SINGLE REQUEST rather
than being started by one call and polled by another. Cross-request run state
would have to live somewhere, and the container's disk is ephemeral (NFR-005)
while a restart mid-run would strand the client on a run id that no longer
exists. One request, one stream, no shared state to lose.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sandscope_agent.api.security import require_token
from sandscope_agent.orchestrator.budget import SpendGuard
from sandscope_agent.orchestrator.graph import Dependencies, RunState, build_graph
from sandscope_agent.orchestrator.workloads import WORKLOADS, WorkloadInput
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.hybrid import HybridRetriever
from sandscope_agent.router.adapters import build_default_providers
from sandscope_agent.router.cache import SemanticCache
from sandscope_agent.router.router import Router, RouterEvent
from sandscope_agent.router.state import RouterState

#: Per-run spend ceiling. Small on purpose: this is a demonstration and the
#: worst outcome of a bug should be a refused call, not a bill.
RUN_BUDGET_USD = float(os.environ.get("RUN_BUDGET_USD", "0.02") or "0.02")

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the retrieval index once at startup.

    The BM25 index and corpus vectors are derived from the corpus, so they are
    rebuilt rather than persisted (NFR-005). At 87 chunks this is milliseconds;
    doing it per request would not be.
    """
    # Fail fast on a configuration that cannot serve a request. A zero ceiling
    # is the spend guard's "cannot spend" state, which is the correct DEFAULT
    # and a terrible runtime surprise: every run dies mid-stream with a stack
    # trace instead of the service refusing to start. Same posture as the
    # missing-token case in api/security.py.
    if RUN_BUDGET_USD <= 0:
        raise RuntimeError(
            f"RUN_BUDGET_USD is {RUN_BUDGET_USD}; the spend guard cannot open a "
            "budget and every run would fail. Set a positive per-run ceiling."
        )

    documents = load_corpus()
    retriever = HybridRetriever(chunks=chunk_corpus(documents), embedder=HashingEmbedder())
    retriever.build_vectors()
    _state["retriever"] = retriever
    _state["started_at"] = time.time()
    yield
    _state.clear()


app = FastAPI(
    title="SandScope agent runtime",
    description="Agent control plane. Not a public API; the BFF is its only client.",
    version="0.5.0",
    lifespan=lifespan,
)


class RunRequest(BaseModel):
    workload: str = Field(description="incident_triage or change_review")
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    context: dict[str, str] = Field(default_factory=dict)

    def to_input(self) -> WorkloadInput:
        return WorkloadInput(subject=self.subject, body=self.body, context=self.context)


def _dependencies(events: list[RouterEvent]) -> Dependencies:
    """A fresh router, cache and spend guard per run.

    Sharing a spend guard between concurrent runs means neither has a ceiling,
    and sharing router state means one visitor's injected failure degrades
    another's run (T-6).
    """
    router = Router(
        providers=build_default_providers(),
        state=RouterState(),
        environment=os.environ.get("SANDSCOPE_ENV", "production"),
        on_event=events.append,
    )
    guard = SpendGuard()
    guard.open(RUN_BUDGET_USD)
    return Dependencies(
        retriever=_state["retriever"],
        router=router,
        guard=guard,
        cache=SemanticCache(embedder=HashingEmbedder()),
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    """Liveness. Unauthenticated on purpose - it reveals nothing and the
    warm-ping cron needs it (R-01)."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _state.get("started_at", time.time()), 1),
        "corpus_ready": "retriever" in _state,
    }


@app.get("/v1/providers", dependencies=[Depends(require_token)])
def providers() -> dict[str, Any]:
    """Live routing order and health.

    claude_cli appears here reporting UNAVAILABLE in production rather than
    being omitted (R-06). An honest absence is more informative than a short
    list.
    """
    router = Router(
        providers=build_default_providers(),
        state=RouterState(),
        environment=os.environ.get("SANDSCOPE_ENV", "production"),
    )
    return {
        "environment": router.environment,
        "providers": [
            {
                "name": s.name,
                "available": s.available,
                "disabled_reason": s.disabled_reason,
                "detail": s.detail,
            }
            for s in router.status()
        ],
    }


@app.get("/v1/workloads", dependencies=[Depends(require_token)])
def workloads() -> dict[str, Any]:
    return {
        "workloads": [{"name": w.name, "action_noun": w.action_noun} for w in WORKLOADS.values()]
    }


@app.post("/v1/runs/stream", dependencies=[Depends(require_token)])
def stream_run(request: RunRequest) -> StreamingResponse:
    """Execute a run, streaming each node as it completes."""
    if request.workload not in WORKLOADS:
        raise HTTPException(
            status_code=422,  # UNPROCESSABLE_CONTENT; the named constant was renamed
            detail=f"unknown workload {request.workload!r}; known: {sorted(WORKLOADS)}",
        )
    if "retriever" not in _state:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="corpus not loaded"
        )

    def generate() -> Iterator[str]:
        router_events: list[RouterEvent] = []
        try:
            deps = _dependencies(router_events)
            graph = build_graph(deps)
        except Exception as error:
            # Anything that fails before the first node still has to reach the
            # client as an error EVENT. A stream that ends without one is
            # indistinguishable from a dropped connection.
            yield _sse("error", {"error": type(error).__name__, "detail": str(error)[:300]})
            return

        run_id = f"run-{int(time.time() * 1000):x}"
        initial: RunState = {
            "run_id": run_id,
            "workload": request.workload,
            "request": request.to_input(),
            "events": [],
        }
        yield _sse("run_started", {"run_id": run_id, "workload": request.workload})

        final: dict[str, Any] = {}
        spans: list[dict[str, Any]] = []
        run_started = time.perf_counter()
        node_started = run_started
        try:
            for update in graph.stream(initial, stream_mode="updates"):
                for node, patch in update.items():
                    now = time.perf_counter()
                    span = {
                        "name": node,
                        "start_ms": round((node_started - run_started) * 1000, 2),
                        "duration_ms": round((now - node_started) * 1000, 2),
                        # Which model calls happened inside this node, taken from
                        # the ledger's growth rather than from instrumentation
                        # inside the node - the chokepoint already records every
                        # one, so counting there cannot drift from reality.
                        "calls": len(deps.guard.ledger) - sum(s["calls"] for s in spans),
                        "cache_hits": sum(
                            1
                            for e in deps.guard.ledger[sum(s["calls"] for s in spans) :]
                            if e.cache_hit
                        ),
                    }
                    spans.append(span)
                    node_started = now
                    final.update(patch)
                    yield _sse(
                        "node_completed",
                        {
                            "node": node,
                            "duration_ms": span["duration_ms"],
                            **_summarise(node, patch),
                        },
                    )
        except Exception as error:
            # Fail closed and say so. A stream that stops without an error event
            # is indistinguishable from a network drop at the client.
            yield _sse("error", {"error": type(error).__name__, "detail": str(error)[:300]})
            return

        yield _sse(
            "run_completed",
            {
                "run_id": run_id,
                "status": final.get("status"),
                "risk": final.get("risk"),
                "citations": len(final.get("citations", []) or []),
                "uncited": len(final.get("uncited", []) or []),
                "cost_usd": round(deps.guard.actual_usd, 6),
                "tokens_avoided": deps.guard.tokens_avoided,
                "providers": [{"provider": e.provider, "event": e.event} for e in router_events],
                "total_ms": round((time.perf_counter() - run_started) * 1000, 2),
                "spans": spans,
                "ledger": [
                    {
                        "provider": e.provider,
                        "model": e.model,
                        "tokens_in": e.tokens_in,
                        "tokens_out": e.tokens_out,
                        "estimated_usd": float(e.estimated_usd),
                        "actual_usd": float(e.actual_usd or 0.0),
                        "cache_hit": e.cache_hit,
                    }
                    for e in deps.guard.ledger
                ],
            },
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _summarise(node: str, patch: dict[str, Any]) -> dict[str, Any]:
    """What each node contributes, without shipping the whole state.

    Deliberately explicit per node rather than dumping the patch: the state
    carries retrieval objects and request context, and a generic serialiser
    would eventually put something in the stream that does not belong there.
    """
    if node == "retrieve":
        return {
            "hits": len(patch.get("hits", [])),
            "degraded": patch.get("degraded", False),
            "top_documents": [h.chunk.document_id for h in patch.get("hits", [])[:3]],
        }
    if node == "assess_evidence":
        return {"verdict": patch.get("verdict"), "rationale": patch.get("evidence_rationale")}
    if node == "adjudicate":
        return {"verdict": patch.get("verdict"), "rationale": patch.get("evidence_rationale")}
    if node == "hypothesise":
        return {"attempt": patch.get("attempts"), "text": patch.get("hypothesis", "")}
    if node == "verify":
        return {
            "citations": [
                {
                    "claim": c["claim_text"][:160],
                    "chunk_id": c["chunk_id"],
                    "resolved": c["resolved"],
                }
                for c in patch.get("citations", [])
            ],
            "uncited": patch.get("uncited", []),
        }
    if node == "propose_action":
        return {"proposal": patch.get("proposal", "")}
    if node == "risk_gate":
        return {"risk": patch.get("risk"), "reason": patch.get("risk_reason")}
    if node in ("refuse", "escalate", "await_approval", "emit"):
        return {"status": patch.get("status")}
    return {}
