"""Managed vector store arm of the ANN benchmark (FR-030).

Compares Upstash Vector against the pgvector results in ADR-0011, and is
explicit about what can and cannot be compared.

VALID to compare:
  recall@k and distance ratio against exact search. No timing is involved, so
  the comparison holds regardless of where anything is hosted.

NOT valid to compare:
  latency. pgvector's numbers come from EXPLAIN ANALYZE and exclude the network.
  Upstash exposes no server-side timing, so its numbers are client wall-clock
  including a round trip to another continent. Putting those two in one column
  would repeat the mistake that made this benchmark's first run meaningless -
  every configuration read 65-68ms because the network was being measured.

Client latency is therefore reported separately and labelled, never merged.

    python training/benchmark_vector_store.py
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv

from training.benchmark_ann import DIM, QUERIES, TOP_K, clustered_vectors

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

REPORT = (
    Path(__file__).resolve().parents[1]
    / "meridian_agent"
    / "evaluation"
    / "vector_store_benchmark.json"
)
#: The free tier allows 10,000 WRITES PER DAY, and every upserted vector counts
#: as one. The first attempt at this benchmark planned 87 + 1,000 + 5,000 +
#: 20,000 = 26,087 writes and exhausted the allowance partway through the third
#: arm, leaving the index holding an unknown subset.
#:
#: That is a real operational property of the store, not an obstacle: a managed
#: vector database whose free tier cannot ingest 26k vectors in a day is a
#: different proposition from one that can, and it belongs in the comparison.
#:
#: Sizes now fit inside a single day's allowance with headroom.
SIZES = (87, 1_000, 5_000)
UPSERT_BATCH = 200
#: Refuse to start a sweep that cannot finish. A benchmark that runs out of
#: budget mid-way does not produce partial results, it produces an index in an
#: unknown state and numbers that cannot be trusted.
DAILY_WRITE_BUDGET = 10_000


@dataclass
class VectorResult:
    store: str
    size: int
    ingest_seconds: float
    ingest_vectors_per_second: float
    client_p50_ms: float
    client_p95_ms: float
    recall_at_k: float
    distance_ratio: float
    note: str = ""


class Upstash:
    """Thin REST client.

    httpx rather than urllib: it is already a runtime dependency, it handles
    retries and timeouts properly, and the security linter is right that
    urlopen accepting arbitrary schemes is worth avoiding.
    """

    def __init__(self) -> None:
        self.url = os.environ["UPSTASH_VECTOR_REST_URL"].rstrip("/")
        self.client = httpx.Client(
            base_url=self.url,
            headers={"Authorization": f"Bearer {os.environ['UPSTASH_VECTOR_REST_TOKEN']}"},
            timeout=httpx.Timeout(180.0, connect=30.0),
        )

    def reset(self) -> None:
        self.client.delete("/reset").raise_for_status()

    def info(self) -> dict:
        response = self.client.get("/info")
        response.raise_for_status()
        result: dict = response.json()["result"]
        return result

    def upsert(self, vectors: np.ndarray) -> None:
        for start in range(0, len(vectors), UPSERT_BATCH):
            batch = [
                {"id": str(start + i), "vector": [float(x) for x in vector]}
                for i, vector in enumerate(vectors[start : start + UPSERT_BATCH])
            ]
            self.client.post("/upsert", json=batch).raise_for_status()

    def query(self, vector: np.ndarray, k: int) -> tuple[list[str], list[float], float]:
        started = time.perf_counter()
        response = self.client.post(
            "/query",
            json={"vector": [float(x) for x in vector], "topK": k, "includeVectors": False},
        )
        response.raise_for_status()
        elapsed = (time.perf_counter() - started) * 1000
        matches = response.json().get("result", [])
        # Upstash returns cosine SIMILARITY; pgvector's <=> operator returns
        # cosine DISTANCE. They run in opposite directions, and comparing the
        # raw numbers would silently invert every ranking.
        return (
            [m["id"] for m in matches],
            [1.0 - float(m["score"]) for m in matches],
            elapsed,
        )


def exact_ground_truth(corpus: np.ndarray, queries: np.ndarray, k: int):
    """Brute-force cosine, computed locally.

    Ground truth must not come from the store under test.
    """
    truth = []
    for query in queries:
        distances = 1.0 - corpus @ query
        order = np.argsort(distances)[:k]
        truth.append(([str(i) for i in order], [float(distances[i]) for i in order]))
    return truth


def main() -> None:
    client = Upstash()
    info = client.info()
    print(f"index: dimension={info['dimension']} similarity={info['similarityFunction']}")
    if info["dimension"] != DIM:
        raise SystemExit(f"index dimension {info['dimension']} != {DIM}; cannot benchmark")

    planned = sum(SIZES)
    if planned > DAILY_WRITE_BUDGET:
        raise SystemExit(
            f"this sweep needs {planned:,} writes against a {DAILY_WRITE_BUDGET:,}/day "
            "allowance. Reduce SIZES rather than starting a run that cannot finish."
        )
    print(f"planned writes: {planned:,} of {DAILY_WRITE_BUDGET:,} daily allowance")

    queries = clustered_vectors(QUERIES, seed=99)
    results: list[VectorResult] = []

    for size in SIZES:
        print(f"\n=== {size:,} vectors ===")
        client.reset()
        time.sleep(2)

        # The index must be empty before a size is measured. A reset that
        # silently left rows behind is what produced an index holding 600
        # vectors of unknown provenance, and a measurement against unknown
        # contents looks exactly like a real one.
        remaining = int(client.info().get("vectorCount", 0))
        if remaining:
            raise SystemExit(f"reset left {remaining} vectors behind; refusing to measure")

        corpus = clustered_vectors(size)
        truth = exact_ground_truth(corpus, queries, TOP_K)

        try:
            started = time.perf_counter()
            client.upsert(corpus)
            ingest = time.perf_counter() - started
        except httpx.HTTPStatusError as error:
            body = error.response.text[:160]
            print(f"  ingest refused at {size:,}: HTTP {error.response.status_code} {body}")
            results.append(
                VectorResult(
                    "upstash_vector",
                    size,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    note=f"refused: HTTP {error.response.status_code} {body}",
                )
            )
            break

        # Upstash indexes asynchronously; querying before it settles measures a
        # partially built index rather than the store.
        for _ in range(30):
            if int(client.info().get("vectorCount", 0)) >= size:
                break
            time.sleep(2)

        latencies, hits, ratios = [], 0, []
        for query, (expected_ids, expected_distances) in zip(queries, truth, strict=True):
            found, distances, elapsed = client.query(query, TOP_K)
            latencies.append(elapsed)
            hits += len(set(found) & set(expected_ids))
            if distances and expected_distances[0] > 0:
                ratios.append(distances[0] / expected_distances[0])

        latencies.sort()
        result = VectorResult(
            store="upstash_vector",
            size=size,
            ingest_seconds=round(ingest, 2),
            ingest_vectors_per_second=round(size / ingest, 1) if ingest else 0.0,
            client_p50_ms=round(statistics.median(latencies), 2),
            client_p95_ms=round(latencies[int(0.95 * (len(latencies) - 1))], 2),
            recall_at_k=round(hits / (len(truth) * TOP_K), 4),
            distance_ratio=round(statistics.mean(ratios), 4) if ratios else 1.0,
        )
        results.append(result)
        print(
            f"  ingest {result.ingest_seconds:7.1f}s ({result.ingest_vectors_per_second:7.1f}/s)  "
            f"client p50 {result.client_p50_ms:7.1f}ms  "
            f"recall@{TOP_K} {result.recall_at_k:.3f}  dist-ratio {result.distance_ratio:.4f}"
        )

    client.reset()
    REPORT.write_text(json.dumps([asdict(r) for r in results], indent=2) + "\n")
    print(f"\nwrote {REPORT.name}; index reset")
    print("\nNOTE: client_p50_ms includes the round trip and is NOT comparable with")
    print("      the pgvector figures in ADR-0011, which are server-side.")
    print("      recall_at_k and distance_ratio ARE comparable.")


if __name__ == "__main__":
    main()
