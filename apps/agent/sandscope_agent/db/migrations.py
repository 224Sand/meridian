"""Forward-only migration discovery and application.

Migrations are numbered SQL files applied in order and recorded with a checksum.
A migration that has been applied anywhere is never edited: a correction is a new
file. The checksum is what turns that from a convention people forget into a
condition the runner refuses to proceed past.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

FILENAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


class MigrationError(RuntimeError):
    """Raised when the migration set on disk is not internally consistent."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str

    @property
    def label(self) -> str:
        return f"{self.version:04d}_{self.name}"


def checksum(sql: str) -> str:
    """Content hash of a migration.

    Whitespace is normalised at the line level so that reformatting does not
    read as tampering, while any change to a statement does.
    """
    normalised = "\n".join(line.rstrip() for line in sql.strip().splitlines())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def discover(directory: Path) -> list[Migration]:
    """Load every migration in `directory`, ordered by version.

    Raises MigrationError on a duplicate version or a gap in the sequence. Both
    are silent hazards otherwise: a duplicate means one file never runs, and a
    gap usually means a file was lost in a merge.
    """
    migrations: list[Migration] = []
    seen: dict[int, str] = {}

    for path in sorted(directory.glob("*.sql")):
        match = FILENAME_RE.match(path.name)
        if match is None:
            raise MigrationError(f"{path.name}: expected NNNN_lower_snake_case.sql")
        version = int(match.group(1))
        name = match.group(2)
        if version in seen:
            raise MigrationError(
                f"duplicate migration version {version:04d}: {seen[version]} and {path.name}"
            )
        seen[version] = path.name

        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise MigrationError(f"{path.name}: migration is empty")
        migrations.append(Migration(version, name, sql, checksum(sql)))

    if not migrations:
        return migrations

    expected = list(range(1, len(migrations) + 1))
    actual = [m.version for m in migrations]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        raise MigrationError(
            f"migration sequence must be contiguous from 0001; missing {missing or actual}"
        )
    return migrations


def plan(applied: dict[int, str], available: list[Migration]) -> list[Migration]:
    """Return the migrations still to run, refusing to proceed on drift.

    `applied` maps version to the checksum recorded when it ran. A recorded
    checksum that no longer matches the file means the migration was edited
    after being applied, so the database and the repository disagree about what
    the schema is. Continuing would apply later migrations onto an unknown base.
    """
    by_version = {m.version: m for m in available}

    for version, recorded in sorted(applied.items()):
        migration = by_version.get(version)
        if migration is None:
            raise MigrationError(
                f"migration {version:04d} is applied in the database but missing from disk"
            )
        if migration.checksum != recorded:
            raise MigrationError(
                f"{migration.label} was edited after it was applied "
                f"(recorded {recorded[:12]}…, on disk {migration.checksum[:12]}…). "
                "Forward-only: add a new migration instead."
            )

    return [m for m in available if m.version not in applied]


SCHEMA_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER     PRIMARY KEY,
    name       TEXT        NOT NULL,
    checksum   TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""
