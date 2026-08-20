"""Migration discovery and drift detection.

Every test here runs offline: discovery, ordering and drift are pure functions
over files, which is deliberate — the rules they enforce are the ones most
likely to be broken during a merge, and a test that needs a database would not
run in that moment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sandscope_agent.db.migrations import (
    MigrationError,
    checksum,
    discover,
    plan,
)

REPO_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def write(tmp_path: Path, name: str, sql: str = "SELECT 1;") -> Path:
    path = tmp_path / name
    path.write_text(sql, encoding="utf-8")
    return path


class TestDiscover:
    def test_orders_by_version_not_filesystem(self, tmp_path: Path) -> None:
        write(tmp_path, "0002_second.sql")
        write(tmp_path, "0001_first.sql")
        write(tmp_path, "0003_third.sql")
        assert [m.version for m in discover(tmp_path)] == [1, 2, 3]

    def test_rejects_malformed_filename(self, tmp_path: Path) -> None:
        write(tmp_path, "initial.sql")
        with pytest.raises(MigrationError, match="lower_snake_case"):
            discover(tmp_path)

    def test_rejects_duplicate_version(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql")
        write(tmp_path, "0001_also_first.sql")
        with pytest.raises(MigrationError, match="duplicate migration version"):
            discover(tmp_path)

    def test_rejects_gap_in_sequence(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql")
        write(tmp_path, "0003_third.sql")
        with pytest.raises(MigrationError, match="contiguous"):
            discover(tmp_path)

    def test_rejects_empty_migration(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_empty.sql", "   \n\n")
        with pytest.raises(MigrationError, match="empty"):
            discover(tmp_path)

    def test_empty_directory_is_not_an_error(self, tmp_path: Path) -> None:
        assert discover(tmp_path) == []


class TestChecksum:
    def test_is_stable_across_calls(self) -> None:
        assert checksum("SELECT 1;") == checksum("SELECT 1;")

    def test_ignores_trailing_whitespace_reformatting(self) -> None:
        assert checksum("SELECT 1;  \nSELECT 2;") == checksum("SELECT 1;\nSELECT 2;")

    def test_changes_when_a_statement_changes(self) -> None:
        assert checksum("SELECT 1;") != checksum("SELECT 2;")


class TestPlan:
    def test_returns_only_unapplied(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql")
        write(tmp_path, "0002_second.sql")
        available = discover(tmp_path)
        pending = plan({1: available[0].checksum}, available)
        assert [m.version for m in pending] == [2]

    def test_detects_a_migration_edited_after_application(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql", "SELECT 1;")
        available = discover(tmp_path)
        stale = checksum("SELECT 'the original statement';")
        with pytest.raises(MigrationError, match="edited after it was applied"):
            plan({1: stale}, available)

    def test_detects_applied_migration_missing_from_disk(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql")
        available = discover(tmp_path)
        with pytest.raises(MigrationError, match="missing from disk"):
            plan({1: available[0].checksum, 2: "deadbeef"}, available)

    def test_nothing_pending_when_all_applied(self, tmp_path: Path) -> None:
        write(tmp_path, "0001_first.sql")
        available = discover(tmp_path)
        assert plan({1: available[0].checksum}, available) == []


class TestRepositoryMigrations:
    """The real migration set must satisfy its own rules."""

    def test_repository_migrations_are_discoverable(self) -> None:
        migrations = discover(REPO_MIGRATIONS)
        assert migrations, "expected at least one migration in the repository"
        assert migrations[0].label == "0001_initial"

    def test_initial_migration_creates_the_expected_tables(self) -> None:
        sql = discover(REPO_MIGRATIONS)[0].sql
        for table in (
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
        ):
            assert f"CREATE TABLE {table} (" in sql, f"missing table: {table}"

    def test_embedding_table_is_keyed_by_model(self) -> None:
        """ADR-0005: two embedding models must not share a row."""
        sql = discover(REPO_MIGRATIONS)[0].sql
        assert "PRIMARY KEY (chunk_id, model)" in sql

    def test_cache_key_includes_the_embedding_model(self) -> None:
        """ADR-0005: a lookup under a different model is a miss, not a cross-space compare."""
        sql = discover(REPO_MIGRATIONS)[0].sql
        assert "UNIQUE (prompt_hash, embedding_model, model_tier)" in sql

    def test_a_run_has_at_most_one_approval(self) -> None:
        """ADR-0006: the continuation is a separate run, so approval cannot repeat."""
        sql = discover(REPO_MIGRATIONS)[0].sql
        assert "run_id       TEXT        NOT NULL UNIQUE REFERENCES run(id)" in sql

    def test_estimated_cost_is_not_nullable(self) -> None:
        """ADR-0007: the estimate is taken before the call, so it always exists."""
        sql = discover(REPO_MIGRATIONS)[0].sql
        assert "estimated_cost_usd NUMERIC(12,6) NOT NULL" in sql
