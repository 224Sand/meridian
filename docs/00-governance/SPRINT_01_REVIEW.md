# Sprint 1 — Review & Retrospective

**Sprint:** 1 — Foundation · **Closed:** 2026-08-20 · **Release:** 0.1.0

---

## 1. Sprint goal

> A deterministically seeded simulated production estate, a retrieval corpus,
> and the schema that holds both — with integration tests running against a real
> Postgres in CI.

**Met, with one story carried.** S1-09 (seed loader) is blocked on IMP-04 and
moves to Sprint 2.

## 2. Delivered

| ID | Story | Pts | Outcome |
|---|---|---|---|
| S1-08 | Python scaffold | 3 | ruff + mypy strict + pytest, all green |
| S1-01 | Schema and migrations | 5 | 17 tables; runner refuses to proceed on checksum drift |
| S1-02 | Estate generator | 5 | 19 services, 27 edges, asserted acyclic |
| S1-03 | Telemetry generator | 5 | Lagged, attenuated propagation across the blast radius |
| S1-04 | Incident generator | 5 | 8 fault patterns, reproducible from seed alone |
| S1-05 | Retrieval corpus | 5 | 15 documents, ~4,400 words, with deliberate gaps |
| S1-06 | Chunker, BM25, embedder | 8 | 60 chunks, zero new dependencies |
| S1-07 | CI database verification | 5 | pgvector service container; 6 integration tests |
| S1-09 | Seed loader | 3 | **Carried to Sprint 2** — blocked on IMP-04 |

**Velocity: 41 of 44 points.** 100 tests: 94 offline, 6 integration.

## 3. Demonstrated

- **CI applies the schema to a real Postgres on every push.** The constraints
  that encode ADR-0005, ADR-0006 and ADR-0007 are asserted by inserting rows the
  database must reject, not by reading the DDL.
- **Retrieval separates answerable from unanswerable by more than 3x** on the
  corpus as authored. This is the property the refusal gate will be built on in
  Sprint 2, and it is now measured rather than assumed.
- **Determinism is verified across process boundaries** for both the incident
  generator and the embedder, under three `PYTHONHASHSEED` values.

## 4. Retrospective

**What worked.** Authoring the topology by hand and generating only the dynamics
produced an estate whose incidents are actually diagnosable. A randomly wired
graph would have produced plausible names attached to a meaningless shape, and
the triage demonstration would have had nothing real to reason about.

Writing `corpus/GAPS.md` before the eval suite exists forced an uncomfortable
question early: what should this system be unable to answer? Answering it in
writing is what makes the refusal metric honest later.

**What did not.** Two facts in the Sprint 1 plan were wrong when written — the
schema was described as 13 tables and then 16, and is 17. Both were caught by
reading rather than by a gate. Counts in prose drift; counts in prose are
therefore worth avoiding.

**Improvement committed for Sprint 2.** Figures that can be derived are derived.
The delivery surface reads test counts, table counts and requirement counts from
the artifacts themselves rather than from prose written at a point in time.

## 5. Impediments

| ID | Impediment | Status |
|---|---|---|
| IMP-01 | No Docker on host | Accepted; HF build is the container integration test |
| IMP-04 | No managed Postgres or Redis credentials | **OPEN** — blocks S1-09 only. Everything else proceeded. |

## 6. Gate

Sprint Review — pending Product Owner.
