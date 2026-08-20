"""Schema application against a real Postgres.

Marked `integration`: executed in CI against a pgvector service container, so
the schema is verified on every push.

The fixture DROPS THE SCHEMA. Once a managed database existed, a developer with
a populated .env and a habit of running `pytest` would have destroyed it, and
nothing in the test would have hesitated. The guard below refuses to run unless
the target is explicitly disposable - a throwaway host, or an operator who has
said so for this command only.

Refusing is the safe default here: the cost of an unnecessary skip is a test
that did not run, and the cost of the alternative is a database that no longer
exists.
"""

from __future__ import annotations

import os

import pytest

from sandscope_agent.db.engine import apply_migrations, connect

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


#: Hosts a destructive test may target without an explicit override.
DISPOSABLE_HOSTS = ("localhost", "127.0.0.1", "postgres", "::1")


def _is_disposable(url: str) -> bool:
    """Whether this target may be dropped.

    Matched on the host, not on the database name. A database called
    `sandscope_test` on a managed provider is still somebody's data, and a name
    is not an authorisation.
    """
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in DISPOSABLE_HOSTS


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set - integration tests require a live Postgres")

    if not _is_disposable(url) and os.environ.get("SANDSCOPE_ALLOW_DESTRUCTIVE_TESTS") != "1":
        from urllib.parse import urlparse

        pytest.skip(
            f"refusing to drop the schema on '{urlparse(url).hostname}': not a disposable host. "
            "Set SANDSCOPE_ALLOW_DESTRUCTIVE_TESTS=1 for this command only if you mean it."
        )

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


class TestTheGuardItself:
    """The guard is the only thing between `pytest` and a live database, so it
    is tested like a control rather than trusted like a convention."""

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@localhost:5432/db",
            "postgresql://u:p@127.0.0.1:5432/db",
            "postgresql://u:p@postgres:5432/sandscope_test",
        ],
    )
    def test_disposable_hosts_are_allowed(self, url: str) -> None:
        assert _is_disposable(url)

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@ep-something-pooler.ap-southeast-1.aws.neon.tech/neondb",
            "postgresql://u:p@db.internal.example.com/anything",
            # A database NAMED test on a managed host is still somebody's data.
            "postgresql://u:p@ep-x.aws.neon.tech/sandscope_test",
        ],
    )
    def test_managed_hosts_are_refused(self, url: str) -> None:
        assert not _is_disposable(url)

    def test_a_malformed_url_is_not_disposable(self) -> None:
        assert not _is_disposable("not a url at all")
