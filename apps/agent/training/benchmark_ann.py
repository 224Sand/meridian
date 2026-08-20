"""Approximate nearest neighbour benchmark (FR-030).

The question worth answering is not "is HNSW fast". It is **at what corpus size
does an ANN index start earning its cost**, because this system's corpus is 87
chunks and the honest expectation is that exact search wins outright at that
scale. A benchmark that only reported HNSW latency would confirm a decision
nobody should make.

So: exact search is ground truth, HNSW and IVFFlat are measured against it for
recall AND latency across four corpus sizes, and the crossover is reported.

Synthetic vectors are drawn as a mixture of Gaussians around random centroids
rather than uniformly at random. Uniform vectors in 768 dimensions are nearly
equidistant, which is the worst case for any ANN index and would flatter exact
search for a reason that has nothing to do with real embeddings.

Three corrections after the first run produced numbers that could not be
believed:

  1. Timing was client wall-clock, so every measurement read 65-68ms regardless
     of method or corpus size - the round trip to the database, not the query.
     "HNSW wins at 87 vectors" was 65.38ms against 65.41ms on a 65ms floor.
     Timing now comes from EXPLAIN ANALYZE's server-side execution time.
  2. Recall collapsed to 0.16, which says more about the fixture than about
     HNSW. 24 clusters over 20,000 points makes the top-10 neighbours near-ties,
     so exact and approximate disagree while both are defensible. More
     centroids and a tighter spread give a well-posed ranking to recall against.
  3. Tuning was applied with session-level SET. The connection is Neon's POOLED
     endpoint, which pools in transaction mode, so session state does not
     survive between statements and ivfflat.probes never took effect. Tuning is
     now SET LOCAL inside the same explicit transaction as the query.

    python training/benchmark_ann.py
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv

from meridian_agent.db.engine import connect

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DIM = 768
SIZES = (87, 1_000, 5_000, 20_000)
QUERIES = 50
TOP_K = 10
#: Enough centroids that a point's ten nearest neighbours are genuinely its
#: neighbours rather than an arbitrary pick from a crowd of near-ties.
CLUSTERS = 400
TABLE = "ann_bench_vectors"
REPORT = (
    Path(__file__).resolve().parents[1] / "meridian_agent" / "evaluation" / "ann_benchmark.json"
)


@dataclass
class Measurement:
    method: str
    size: int
    build_seconds: float
    index_bytes: int
    p50_ms: float
    p95_ms: float
    recall_at_k: float
    #: Mean ratio of the approximate top-1 distance to the exact top-1 distance.
    #: 1.000 means the neighbours found were exactly as close, even where their
    #: ids differ. Set-overlap recall cannot distinguish "found a worse
    #: neighbour" from "broke a tie differently", and in 768 dimensions with
    #: clustered data almost every disagreement is the second kind.
    distance_ratio: float


def clustered_vectors(n: int, seed: int = 20260820) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centroids = rng.normal(size=(CLUSTERS, DIM))
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
    assignment = rng.integers(0, CLUSTERS, size=n)
    vectors = centroids[assignment] + rng.normal(scale=0.12, size=(n, DIM))
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def literal(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


def populate(conn: psycopg.Connection, vectors: np.ndarray) -> None:
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(f"CREATE TABLE {TABLE} (id bigserial PRIMARY KEY, vec vector({DIM}))")
        with cur.copy(f"COPY {TABLE} (vec) FROM STDIN") as copy:
            for vector in vectors:
                copy.write_row([literal(vector)])
    conn.commit()


def search(
    conn: psycopg.Connection, query: np.ndarray, k: int, tuning: dict[str, str] | None = None
) -> tuple[list[int], float, list[float]]:
    """Run one search, returning ids, SERVER-SIDE execution time, and distances.

    Client wall-clock is dominated by the round trip to a managed database in
    another region. That is a real cost and it is not the one this benchmark is
    about: the first run reported 65-68ms for every method at every corpus size,
    which was the network and nothing else. EXPLAIN ANALYZE reports what the
    executor actually spent.

    Tuning is applied with SET LOCAL inside the same transaction as the query.
    The connection is Neon's POOLED endpoint, which pools in transaction mode,
    so a session-level SET is discarded before the next statement runs and the
    setting silently never applies.
    """
    sql = (
        f"SELECT id, vec <=> %s::vector AS distance FROM {TABLE} "
        "ORDER BY vec <=> %s::vector LIMIT %s"
    )
    vector = literal(query)
    with conn.transaction(), conn.cursor() as cur:
        for key, value in (tuning or {}).items():
            cur.execute(f"SET LOCAL {key} = {value}")
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql, (vector, vector, k))
        plan = cur.fetchone()[0][0]
        elapsed = float(plan["Execution Time"])
        cur.execute(sql, (vector, vector, k))
        rows = cur.fetchall()
    return [int(r[0]) for r in rows], elapsed, [float(r[1]) for r in rows]


def index_size(conn: psycopg.Connection, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_relation_size(%s)", (name,))
        row = cur.fetchone()
        return int(row[0]) if row else 0


def measure(
    conn: psycopg.Connection,
    method: str,
    size: int,
    queries: np.ndarray,
    truth: list[tuple[list[int], list[float]]],
) -> Measurement:
    build_seconds = 0.0
    size_bytes = 0

    if method != "exact":
        with conn.cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {TABLE}_idx")
            started = time.perf_counter()
            if method == "hnsw":
                cur.execute(
                    f"CREATE INDEX {TABLE}_idx ON {TABLE} "
                    "USING hnsw (vec vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
                )
            else:
                lists = max(1, min(size // 100, 1000))
                cur.execute(
                    f"CREATE INDEX {TABLE}_idx ON {TABLE} "
                    f"USING ivfflat (vec vector_cosine_ops) WITH (lists = {lists})"
                )
            build_seconds = time.perf_counter() - started
        conn.commit()
        size_bytes = index_size(conn, f"{TABLE}_idx")

    tuning = {"hnsw": {"hnsw.ef_search": "100"}, "ivfflat": {"ivfflat.probes": "20"}}.get(method)

    latencies: list[float] = []
    hits = 0
    ratios: list[float] = []
    for query, (expected_ids, expected_distances) in zip(queries, truth, strict=True):
        found, elapsed, distances = search(conn, query, TOP_K, tuning)
        latencies.append(elapsed)
        hits += len(set(found) & set(expected_ids))
        if distances and expected_distances and expected_distances[0] > 0:
            ratios.append(distances[0] / expected_distances[0])

    latencies.sort()
    return Measurement(
        method=method,
        size=size,
        build_seconds=round(build_seconds, 3),
        index_bytes=size_bytes,
        p50_ms=round(statistics.median(latencies), 2),
        p95_ms=round(latencies[int(0.95 * (len(latencies) - 1))], 2),
        recall_at_k=round(hits / (len(truth) * TOP_K), 4),
        distance_ratio=round(statistics.mean(ratios), 4) if ratios else 1.0,
    )


def main() -> None:
    results: list[Measurement] = []
    queries = clustered_vectors(QUERIES, seed=99)

    with connect() as conn:
        for size in SIZES:
            print(f"\n=== {size:,} vectors ===")
            populate(conn, clustered_vectors(size))

            with conn.cursor() as cur:
                cur.execute(f"DROP INDEX IF EXISTS {TABLE}_idx")
            conn.commit()

            # Ground truth from a sequential scan with no index present.
            truth = [(r[0], r[2]) for r in (search(conn, q, TOP_K) for q in queries)]

            for method in ("exact", "hnsw", "ivfflat"):
                if method == "ivfflat" and size < 100:
                    print("  ivfflat      skipped (needs more rows than clusters)")
                    continue
                m = measure(conn, method, size, queries, truth)
                results.append(m)
                print(
                    f"  {m.method:<12} p50 {m.p50_ms:7.2f}ms  p95 {m.p95_ms:7.2f}ms  "
                    f"recall@{TOP_K} {m.recall_at_k:.3f}  dist-ratio {m.distance_ratio:.4f}  "
                    f"build {m.build_seconds:6.2f}s  index {m.index_bytes / 1024:7.0f} KB"
                )

        with conn.cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {TABLE}_idx")
            cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        conn.commit()
        print("\ncleaned up benchmark table")

    REPORT.write_text(json.dumps([asdict(r) for r in results], indent=2) + "\n")
    print(f"wrote {REPORT.name}")

    print("\n" + "=" * 70)
    print("CROSSOVER: where an index first beats a sequential scan on server-side p50")
    print("=" * 70)
    for method in ("hnsw", "ivfflat"):
        crossover = None
        for size in SIZES:
            exact = next((r for r in results if r.method == "exact" and r.size == size), None)
            approx = next((r for r in results if r.method == method and r.size == size), None)
            if exact and approx and approx.p50_ms < exact.p50_ms and crossover is None:
                crossover = size
        print(
            f"  {method:<10} {crossover:,} vectors"
            if crossover
            else f"  {method:<10} never, within the sizes tested"
        )
    print("\n  This system's corpus: 87 chunks.")


if __name__ == "__main__":
    main()
