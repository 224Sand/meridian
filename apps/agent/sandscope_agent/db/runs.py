"""Persistence for runs, approvals and session memory.

Runs stream within a single request (api/app.py explains why), so nothing about
executing a run requires storage. Two things that happen AFTER a run do:

  * an approval decision arrives minutes later and must find the run it belongs
    to (ADR-0006: the decision creates a NEW run carrying the record)
  * a session's later runs should be able to recall its earlier ones

Both are reads of a completed run, which is why persistence lives here rather
than in the graph. The graph does not know this module exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True, slots=True)
class StoredRun:
    id: str
    session_id: str
    workload: str
    status: str
    subject: str
    risk: str | None
    proposal: str | None
    hypothesis: str | None
    cost_usd: float


def hash_ip(address: str) -> str:
    """Salted digest. The raw address is never persisted (T-9).

    Salted with the service token, which is already a secret this process holds,
    so the digest cannot be reversed with a rainbow table by anyone who obtains
    the database alone.
    """
    salt = os.environ.get("AGENT_SERVICE_TOKEN", "sandscope")
    return hashlib.sha256(f"{salt}:{address}".encode()).hexdigest()


def ensure_session(conn: psycopg.Connection, session_id: str, ip_hash: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO session (id, ip_hash) VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET last_seen_at = now()
            """,
            (session_id, ip_hash),
        )
    return session_id


def save_run(
    conn: psycopg.Connection,
    *,
    run_id: str,
    session_id: str,
    workload: str,
    subject: str,
    state: dict[str, Any],
    cost_usd: float,
    parent_run_id: str | None = None,
) -> None:
    """Write the completed run and its citations.

    Citations are written per claim rather than as a blob so that a reviewer can
    ask which passage supported a specific sentence months later, which is the
    question Sofia in the BRD actually has.
    """
    status = state.get("status", "failed")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO run (id, session_id, parent_run_id, status, verdict, confidence,
                             degraded, cost_usd, ended_at)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, ended_at = now()
            """,
            (
                run_id,
                session_id,
                parent_run_id,
                status,
                (state.get("hypothesis") or "")[:2000] or None,
                bool(state.get("degraded", False)),
                round(cost_usd, 6),
            ),
        )
        for ordinal, citation in enumerate(state.get("citations", []) or []):
            if not citation.get("resolved") or not citation.get("chunk_id"):
                continue
            cur.execute(
                """
                INSERT INTO citation (run_id, claim_text, chunk_id, score, ordinal)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    citation["claim_text"][:1000],
                    citation["chunk_id"],
                    float(citation.get("score", 0.0)),
                    ordinal,
                ),
            )

        if status == "awaiting_approval":
            cur.execute(
                """
                INSERT INTO approval (run_id, action, risk_level)
                VALUES (%s, %s, %s) ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, (state.get("proposal") or "")[:2000], state.get("risk", "high")),
            )

        # Memory is written from the OUTCOME rather than from the model's own
        # summary of itself. A model asked what it should remember writes
        # something flattering.
        cur.execute(
            "INSERT INTO memory_item (session_id, kind, content) VALUES (%s, %s, %s)",
            (
                session_id,
                "incident_ref",
                json.dumps(
                    {
                        "run_id": run_id,
                        "workload": workload,
                        "subject": subject,
                        "status": status,
                        "risk": state.get("risk"),
                    }
                ),
            ),
        )
    conn.commit()


def recall(conn: psycopg.Connection, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """What this session has already looked at.

    Ordered newest first and capped, because an unbounded recall becomes an
    unbounded prompt, and an unbounded prompt is an unbounded cost.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content FROM memory_item
            WHERE session_id = %s AND kind = 'incident_ref'
            ORDER BY created_at DESC LIMIT %s
            """,
            (session_id, limit),
        )
        return [json.loads(row[0]) for row in cur.fetchall()]


def load_pending_approval(conn: psycopg.Connection, run_id: str) -> StoredRun | None:
    """The gated run, if it exists and is still undecided."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.session_id, r.status, r.verdict, a.action, a.risk_level, a.decision
            FROM run r JOIN approval a ON a.run_id = r.id
            WHERE r.id = %s
            """,
            (run_id,),
        )
        row = cur.fetchone()
    if row is None or row[6] is not None:
        return None
    return StoredRun(
        id=row[0],
        session_id=row[1],
        workload="",
        status=row[2],
        subject="",
        risk=row[5],
        proposal=row[4],
        hypothesis=row[3],
        cost_usd=0.0,
    )


def record_decision(conn: psycopg.Connection, run_id: str, decision: str, decided_by: str) -> str:
    """Record the decision and return the CONTINUATION run's id.

    The gated run is never resumed. ADR-0006 makes `await_approval` terminal by
    topology, so a decision creates a new run that points back at it. Two rows
    for one approved incident is the cost of a control that cannot auto-proceed.
    """
    if decision not in ("approved", "rejected"):
        raise ValueError(f"decision must be approved or rejected, got {decision!r}")

    continuation = f"run-{uuid.uuid4().hex[:12]}"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE approval SET decision = %s, decided_at = now(), decided_by = %s
            WHERE run_id = %s AND decision IS NULL
            """,
            (decision, decided_by, run_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"run {run_id} has no undecided approval")
        cur.execute("SELECT session_id FROM run WHERE id = %s", (run_id,))
        row = cur.fetchone()
        session_id = row[0] if row else None
        cur.execute(
            """
            INSERT INTO run (id, session_id, parent_run_id, status, verdict, ended_at)
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            (
                continuation,
                session_id,
                run_id,
                "completed" if decision == "approved" else "refused",
                f"continuation of {run_id} after it was {decision}",
            ),
        )
    conn.commit()
    return continuation
