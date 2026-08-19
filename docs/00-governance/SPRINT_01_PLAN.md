# Sprint 1 — Foundation

**Sprint goal:** A deterministically seeded simulated production estate, a
retrieval corpus, and the schema that holds both — with integration tests running
against a real Postgres in CI.

**Opened:** 2026-08-20 · **Gate:** Sprint Review
**Release target:** 0.1.0

---

## Sprint backlog

| ID | Story | Role | Pts | Blocked | Status |
|---|---|---|---|---|---|
| **S1-08** | Python project scaffold: packaging, lint, types, test runner | DevOps | 3 | no | ⬜ |
| **S1-01** | Schema and forward-only migrations for all 13 tables | DEV | 5 | no | ⬜ |
| **S1-02** | Deterministic estate generator: services, tiers, dependency graph | DEV | 5 | no | ⬜ |
| **S1-03** | Telemetry generator: metrics and logs with plausible correlation | DEV | 5 | no | ⬜ |
| **S1-04** | Incident generator: signatures, severity, causal chains | DEV | 5 | no | ⬜ |
| **S1-05** | Retrieval corpus: runbooks, postmortems, policies, architecture notes | Tech Writer | 5 | no | ⬜ |
| **S1-06** | Chunker, BM25 index, embedding interface with offline fallback | DEV | 8 | no | ⬜ |
| **S1-07** | CI: Postgres+pgvector service container, migrations, integration tests | DevOps | 5 | no | ⬜ |
| **S1-09** | Seed loader: corpus and estate into a live database | DEV | 3 | **IMP-04** | ⬜ |

**Committed: 44 points.**

## Requirements landing this sprint

FR-002 (seeded estate) · FR-003 (incident feed) · NFR-005 (no local state) ·
SD-002 (synthetic data only)

## Impediments

| ID | Impediment | Raised | Owner | Status |
|---|---|---|---|---|
| **IMP-04** | No managed Postgres or Redis credentials. Host has no local Postgres and no Docker (IMP-01), so nothing can be executed against a real database locally. | DevOps | Executive Sponsor | **OPEN** |

### IMP-04 resolution plan

Only **S1-09** is genuinely blocked. Everything else is authored and unit-tested
without a live database:

- Schema is DDL in migration files — authored, reviewed, not yet applied.
- Generators are pure functions over a seed — fully unit-testable offline.
- Chunker, BM25 and the offline embedder have no database dependency at all.
- **CI runs integration tests against a `pgvector/pgvector:pg16` service
  container**, which is free on GitHub Actions and needs no external account.
  This means the schema and the seed loader are *verified in CI* before any
  managed database exists.

So the managed services are needed for the deployed environment, not to make
progress. Sprint 1 proceeds at full speed.

## Definition of Done additions for this sprint

- Every generator must be reproducible from its seed alone. A test asserts that
  the same seed produces byte-identical output across two runs.
- No generated content may be imported from any real source (SD-002). A test
  asserts the seed pipeline reads no file outside `corpus/`.
