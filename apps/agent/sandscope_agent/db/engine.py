"""Database connection and migration application.

The runtime holds no state on local disk (NFR-005), so this module is the only
place a connection is opened and is deliberately thin.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg

from sandscope_agent.db.migrations import (
    SCHEMA_MIGRATION_DDL,
    Migration,
    discover,
    plan,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when DATABASE_URL is absent.

    Deliberately explicit rather than defaulting to localhost: a silent default
    is how a test suite ends up writing to whatever happens to be listening.
    """


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set. The offline test suite runs without it; "
            "integration tests are skipped rather than pointed at a default host."
        )
    return url


@contextmanager
def connect(url: str | None = None) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(url or database_url())
    try:
        yield conn
    finally:
        conn.close()


def applied_versions(conn: psycopg.Connection) -> dict[int, str]:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_MIGRATION_DDL)
        cur.execute("SELECT version, checksum FROM schema_migration")
        return {int(version): str(checksum) for version, checksum in cur.fetchall()}


def apply_migrations(conn: psycopg.Connection, directory: Path | None = None) -> list[Migration]:
    """Apply every pending migration, each in its own transaction.

    Per-migration transactions mean a failure leaves the database at the last
    complete migration rather than partway through an unknown one.
    """
    available = discover(directory or MIGRATIONS_DIR)
    pending = plan(applied_versions(conn), available)

    for migration in pending:
        with conn.transaction(), conn.cursor() as cur:
            # The SQL is a repository file, never user input; there is no
            # interpolation here to parameterise.
            cur.execute(migration.sql)
            cur.execute(
                "INSERT INTO schema_migration (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
    return pending
