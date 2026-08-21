"""Run persistence, the approval continuation, and session memory.

Integration-marked: runs in CI against the pgvector container, skipped against
any managed host by the destructive-test guard.

The approval tests are the important ones. ADR-0006 makes `await_approval`
terminal by topology, and this module is where that becomes durable: a decision
must create a NEW run and must never resume the gated one.
"""

from __future__ import annotations

import os

import pytest

from sandscope_agent.db import runs as store
from sandscope_agent.db.engine import apply_migrations, connect
from tests.test_schema_integration import _is_disposable

pytestmark = pytest.mark.integration

SESSION = "sess-test"
GATED = "run-gated"
#: A chunk the seeded corpus genuinely contains.
GOLD_CHUNK = "rb-database-connection-pool#00"


@pytest.fixture(scope="module")
def prepared():
    """Schema and corpus, built once.

    The corpus has to be here: `citation.chunk_id` is a foreign key onto
    `chunk`, so a citation cannot be stored for a passage that does not exist.
    That constraint is the point - a citation pointing at nothing is not
    evidence - and the first version of this fixture skipped seeding and made
    the constraint look like a test failure.

    Module-scoped because seeding 87 chunks and their embeddings per test costs
    more than the tests do.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set")
    if not _is_disposable(url) and os.environ.get("SANDSCOPE_ALLOW_DESTRUCTIVE_TESTS") != "1":
        pytest.skip("refusing to write to a non-disposable host")

    from sandscope_agent.db.seed_loader import seed

    with connect() as c:
        with c.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        c.commit()
        apply_migrations(c)
        c.commit()
        seed(c)
        yield c


@pytest.fixture
def conn(prepared):
    """A clean run/session slate per test, leaving the corpus in place."""
    with prepared.cursor() as cur:
        cur.execute("DELETE FROM session")
        cur.execute("DELETE FROM run")
    prepared.commit()
    store.ensure_session(prepared, SESSION, store.hash_ip("203.0.113.7"))
    prepared.commit()
    return prepared


def gate(conn, run_id: str = GATED) -> None:
    store.save_run(
        conn,
        run_id=run_id,
        session_id=SESSION,
        workload="incident_triage",
        subject="inc-1",
        cost_usd=0.001,
        state={
            "status": "awaiting_approval",
            "risk": "high",
            "proposal": "Restart the orders-db connection pool.",
            "hypothesis": "[1] Hold time rose before query time.",
            "citations": [
                {
                    "claim_text": "Hold time rose before query time.",
                    "chunk_id": "rb-database-connection-pool#00",
                    "score": 0.9,
                    "resolved": True,
                }
            ],
        },
    )


class TestApprovalIsTerminal:
    """ADR-0006, made durable."""

    def test_a_decision_creates_a_new_run(self, conn) -> None:
        gate(conn)
        continuation = store.record_decision(conn, GATED, "approved", "reviewer")
        assert continuation != GATED
        with conn.cursor() as cur:
            cur.execute("SELECT parent_run_id FROM run WHERE id = %s", (continuation,))
            assert cur.fetchone()[0] == GATED

    def test_the_gated_run_is_never_resumed(self, conn) -> None:
        gate(conn)
        store.record_decision(conn, GATED, "approved", "reviewer")
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM run WHERE id = %s", (GATED,))
            assert cur.fetchone()[0] == "awaiting_approval"

    def test_a_second_decision_is_refused(self, conn) -> None:
        """An approval that can be replayed is not a record of a decision."""
        gate(conn)
        store.record_decision(conn, GATED, "approved", "reviewer")
        with pytest.raises(ValueError, match="no undecided approval"):
            store.record_decision(conn, GATED, "rejected", "someone else")

    def test_a_rejection_produces_a_refused_continuation(self, conn) -> None:
        gate(conn)
        continuation = store.record_decision(conn, GATED, "rejected", "reviewer")
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM run WHERE id = %s", (continuation,))
            assert cur.fetchone()[0] == "refused"

    def test_the_decision_records_who_and_when(self, conn) -> None:
        """Accountability that is verbal is not accountability."""
        gate(conn)
        store.record_decision(conn, GATED, "approved", "sofia")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT decision, decided_by, decided_at IS NOT NULL FROM approval WHERE run_id = %s",
                (GATED,),
            )
            assert cur.fetchone() == ("approved", "sofia", True)

    def test_an_invalid_decision_is_rejected(self, conn) -> None:
        gate(conn)
        with pytest.raises(ValueError, match="approved or rejected"):
            store.record_decision(conn, GATED, "maybe", "reviewer")

    def test_a_pending_approval_disappears_once_decided(self, conn) -> None:
        gate(conn)
        assert store.load_pending_approval(conn, GATED) is not None
        store.record_decision(conn, GATED, "approved", "reviewer")
        assert store.load_pending_approval(conn, GATED) is None


class TestPersistence:
    def test_citations_are_stored_per_claim(self, conn) -> None:
        """So a reviewer can ask which passage supported a specific sentence."""
        gate(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT claim_text, chunk_id FROM citation WHERE run_id = %s", (GATED,))
            rows = cur.fetchall()
        assert rows and rows[0][1] == "rb-database-connection-pool#00"

    def test_unresolved_citations_are_not_stored_as_evidence(self, conn) -> None:
        """A fabricated citation must not become a database row that looks
        exactly like a real one."""
        store.save_run(
            conn,
            run_id="run-fab",
            session_id=SESSION,
            workload="incident_triage",
            subject="inc-2",
            cost_usd=0.0,
            state={
                "status": "completed",
                "citations": [
                    {"claim_text": "invented", "chunk_id": None, "score": 0.0, "resolved": False},
                ],
            },
        )
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM citation WHERE run_id = 'run-fab'")
            assert cur.fetchone()[0] == 0

    def test_the_raw_address_is_never_stored(self, conn) -> None:
        with conn.cursor() as cur:
            cur.execute("SELECT ip_hash FROM session WHERE id = %s", (SESSION,))
            stored = cur.fetchone()[0]
        assert len(stored) == 64
        assert "203.0.113.7" not in stored

    def test_hashing_is_salted_by_the_service_token(self, monkeypatch) -> None:
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "a" * 48)
        first = store.hash_ip("198.51.100.9")
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "b" * 48)
        assert store.hash_ip("198.51.100.9") != first


class TestMemory:
    def test_a_run_is_recalled_by_its_session(self, conn) -> None:
        gate(conn)
        items = store.recall(conn, SESSION)
        assert items and items[0]["run_id"] == GATED
        assert items[0]["status"] == "awaiting_approval"

    def test_recall_is_newest_first_and_capped(self, conn) -> None:
        """An unbounded recall becomes an unbounded prompt, which is an
        unbounded cost."""
        for index in range(8):
            store.save_run(
                conn,
                run_id=f"run-{index}",
                session_id=SESSION,
                workload="incident_triage",
                subject=f"inc-{index}",
                cost_usd=0.0,
                state={"status": "completed"},
            )
        items = store.recall(conn, SESSION, limit=3)
        assert len(items) == 3
        assert items[0]["subject"] == "inc-7"

    def test_another_session_recalls_nothing(self, conn) -> None:
        gate(conn)
        assert store.recall(conn, "sess-someone-else") == []
