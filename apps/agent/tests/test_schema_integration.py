"""Schema application against a real Postgres.

Marked `integration`: skipped locally where no database is configured (IMP-04),
executed in CI against a pgvector service container. The schema is therefore
verified on every push without anyone owning a managed database.
"""

from __future__ import annotations

import os

import pytest

from meridian_agent.db.engine import apply_migrations, connect

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "service",
    "service_dependency",
    "telemetry_event",
    "incident",
    "document",
    "chunk",
    "chunk_embedding",
    "session",
    "memory_item",
    "run",
    "span",
    "citation",
    "approval",
    "cache_entry",
    "provider_event",
    "spend_ledger",
    "eval_run",
    "schema_migration",
}


@pytest.fixture
def conn():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — integration tests require a live Postgres")
    with connect() as c:
        with c.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        c.commit()
        yield c


def table_names(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        return {row[0] for row in cur.fetchall()}


def test_migrations_create_the_full_schema(conn) -> None:
    applied = apply_migrations(conn)
    assert [m.label for m in applied] == ["0001_initial"]
    assert EXPECTED_TABLES <= table_names(conn)


def test_migrations_are_idempotent(conn) -> None:
    apply_migrations(conn)
    assert apply_migrations(conn) == [], "a second run must apply nothing"


def test_pgvector_extension_is_available(conn) -> None:
    apply_migrations(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() is not None


def test_embedding_rows_are_unique_per_chunk_and_model(conn) -> None:
    """ADR-0005 enforced by the database, not by application discipline."""
    import psycopg

    apply_migrations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO document (id, kind, title, source_uri) "
            "VALUES ('d1', 'runbook', 'T', 'corpus/t.md')"
        )
        cur.execute(
            "INSERT INTO chunk (id, document_id, ordinal, body, token_count) "
            "VALUES ('c1', 'd1', 0, 'body', 1)"
        )
        vec = "[" + ",".join(["0.1"] * 768) + "]"
        cur.execute(
            "INSERT INTO chunk_embedding (chunk_id, model, dim, vec) VALUES ('c1','m1',768,%s)",
            (vec,),
        )
        # Same chunk under a DIFFERENT model is legitimate and must be allowed.
        cur.execute(
            "INSERT INTO chunk_embedding (chunk_id, model, dim, vec) VALUES ('c1','m2',768,%s)",
            (vec,),
        )
        # The same chunk under the SAME model twice is not.
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO chunk_embedding (chunk_id, model, dim, vec) VALUES ('c1','m1',768,%s)",
                (vec,),
            )


def test_a_run_cannot_have_two_approvals(conn) -> None:
    """ADR-0006 enforced by the database."""
    import psycopg

    apply_migrations(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO session (id, ip_hash) VALUES ('s1', %s)", ("a" * 64,))
        cur.execute("INSERT INTO run (id, session_id) VALUES ('r1', 's1')")
        cur.execute(
            "INSERT INTO approval (run_id, action, risk_level) VALUES ('r1','restart','high')"
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO approval (run_id, action, risk_level) VALUES ('r1','rollback','high')"
            )


def test_approval_decision_fields_move_together(conn) -> None:
    """A decision without a timestamp or a decider is not an audit record."""
    import psycopg

    apply_migrations(conn)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO session (id, ip_hash) VALUES ('s2', %s)", ("b" * 64,))
        cur.execute("INSERT INTO run (id, session_id) VALUES ('r2', 's2')")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO approval (run_id, action, risk_level, decision) "
                "VALUES ('r2','restart','high','approved')"
            )
