"""Fault patterns the simulated estate can exhibit.

Each pattern describes a real failure mode, the signal that identifies it, the
secondary effects it produces upstream, and the runbook that covers it. The
pattern is what makes an incident *diagnosable*: the telemetry generated from it
carries the evidence, and the corpus contains the document that explains it.

If a pattern's telemetry did not support its diagnosis, the triage demonstration
would be theatre and the evaluation harness would have nothing real to score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["rise", "fall"]


@dataclass(frozen=True, slots=True)
class Signal:
    """One metric that moves when this fault occurs."""

    metric: str
    unit: str
    direction: Direction
    baseline: float
    peak: float

    def __post_init__(self) -> None:
        if self.direction == "rise" and self.peak <= self.baseline:
            raise ValueError(f"{self.metric}: a rising signal must peak above baseline")
        if self.direction == "fall" and self.peak >= self.baseline:
            raise ValueError(f"{self.metric}: a falling signal must trough below baseline")


@dataclass(frozen=True, slots=True)
class FaultPattern:
    id: str
    name: str
    signature: str
    runtimes: tuple[str, ...]
    severity: int
    primary: tuple[Signal, ...]
    secondary: tuple[Signal, ...]
    runbook_id: str
    summary: str

    def applies_to(self, runtime: str) -> bool:
        return runtime in self.runtimes


_ALL_APP_RUNTIMES = ("go1.23", "java21", "node20", "python3.12", "rust1.82")

PATTERNS: tuple[FaultPattern, ...] = (
    FaultPattern(
        id="fault-pool-exhaustion",
        name="Connection pool exhaustion",
        signature="db.pool.saturated",
        runtimes=("postgres16",),
        severity=1,
        primary=(
            Signal("db.pool.wait_ms", "ms", "rise", 2.0, 4200.0),
            Signal("db.pool.available", "count", "fall", 40.0, 0.0),
            Signal("db.active_connections", "count", "rise", 55.0, 100.0),
        ),
        secondary=(
            Signal("http.server.p99_ms", "ms", "rise", 180.0, 9500.0),
            Signal("http.server.error_rate", "ratio", "rise", 0.001, 0.34),
        ),
        runbook_id="rb-database-connection-pool",
        summary=(
            "Callers hold connections longer than the pool can recycle them. Wait time "
            "climbs first, available connections reach zero, and every upstream caller "
            "then times out together."
        ),
    ),
    FaultPattern(
        id="fault-cache-stampede",
        name="Cache stampede after mass eviction",
        signature="cache.hit_ratio.collapse",
        runtimes=("redis7",),
        severity=2,
        primary=(
            Signal("cache.hit_ratio", "ratio", "fall", 0.94, 0.11),
            Signal("cache.evictions_per_s", "count", "rise", 5.0, 8800.0),
            Signal("cache.memory_used_ratio", "ratio", "rise", 0.62, 0.99),
        ),
        secondary=(
            Signal("http.server.p99_ms", "ms", "rise", 150.0, 3100.0),
            Signal("db.active_connections", "count", "rise", 50.0, 92.0),
        ),
        runbook_id="rb-cache-stampede",
        summary=(
            "A mass eviction empties the working set, every request misses at once, and "
            "the traffic that the cache was absorbing lands on the origin in a single wave."
        ),
    ),
    FaultPattern(
        id="fault-consumer-lag",
        name="Consumer group lag growth",
        signature="stream.consumer.lag",
        runtimes=("kafka3.8",),
        severity=2,
        primary=(
            Signal("stream.consumer.lag", "messages", "rise", 400.0, 1_850_000.0),
            Signal("stream.consumer.throughput", "msg_per_s", "fall", 12000.0, 900.0),
        ),
        secondary=(Signal("pipeline.freshness_lag_s", "s", "rise", 4.0, 2400.0),),
        runbook_id="rb-stream-consumer-lag",
        summary=(
            "Consumers fall behind producers. Nothing errors, so alerting on error rate "
            "sees a healthy system while downstream data quietly goes stale."
        ),
    ),
    FaultPattern(
        id="fault-memory-leak",
        name="Heap growth with escalating pause time",
        signature="runtime.memory.leak",
        runtimes=("java21", "node20", "python3.12"),
        severity=2,
        primary=(
            Signal("process.memory.rss_mb", "MB", "rise", 620.0, 3900.0),
            Signal("runtime.gc.pause_ms", "ms", "rise", 12.0, 1450.0),
            Signal("process.restarts", "count", "rise", 0.0, 6.0),
        ),
        secondary=(Signal("http.server.p99_ms", "ms", "rise", 210.0, 4300.0),),
        runbook_id="rb-memory-pressure",
        summary=(
            "Resident memory climbs monotonically across a deploy window. Collection "
            "pauses lengthen as the heap fills, and the process is eventually restarted "
            "by the platform, which resets the graph and hides the trend."
        ),
    ),
    FaultPattern(
        id="fault-timeout-cascade",
        name="Synchronous timeout cascade",
        signature="dependency.timeout.cascade",
        runtimes=_ALL_APP_RUNTIMES,
        severity=1,
        primary=(
            Signal("http.client.timeout_rate", "ratio", "rise", 0.0004, 0.61),
            Signal("http.client.p99_ms", "ms", "rise", 240.0, 10_000.0),
        ),
        secondary=(
            Signal("http.server.error_rate", "ratio", "rise", 0.002, 0.47),
            Signal("thread_pool.queue_depth", "count", "rise", 3.0, 480.0),
        ),
        runbook_id="rb-timeout-and-retry",
        summary=(
            "One slow synchronous dependency occupies caller threads until the caller "
            "itself runs out. Retries multiply the load on the already-slow dependency, "
            "so the system degrades faster the harder it tries to recover."
        ),
    ),
    FaultPattern(
        id="fault-cert-expiry",
        name="TLS certificate expiry",
        signature="tls.handshake.failure",
        runtimes=("go1.23", "java21", "node20"),
        severity=1,
        primary=(
            Signal("tls.handshake_failures_per_s", "count", "rise", 0.0, 1450.0),
            Signal("tls.certificate_days_remaining", "days", "fall", 14.0, -1.0),
        ),
        secondary=(Signal("http.server.error_rate", "ratio", "rise", 0.001, 0.98),),
        runbook_id="rb-tls-certificate",
        summary=(
            "A certificate reaches its expiry. Failure is total and instant at the "
            "moment of expiry rather than gradual, which is what distinguishes it from "
            "a capacity problem on the same graph."
        ),
    ),
    FaultPattern(
        id="fault-n-plus-one",
        name="Query amplification after deploy",
        signature="db.queries_per_request.regression",
        runtimes=_ALL_APP_RUNTIMES,
        severity=2,
        primary=(
            Signal("db.queries_per_request", "count", "rise", 3.0, 87.0),
            Signal("db.query_rate", "qps", "rise", 900.0, 26_000.0),
        ),
        secondary=(
            Signal("http.server.p99_ms", "ms", "rise", 190.0, 2600.0),
            Signal("db.pool.wait_ms", "ms", "rise", 2.0, 780.0),
        ),
        runbook_id="rb-query-amplification",
        summary=(
            "Request volume is unchanged but query volume is not. A change replaced a "
            "batched read with a per-item read, so cost scales with result size rather "
            "than with traffic."
        ),
    ),
    FaultPattern(
        id="fault-shard-imbalance",
        name="Search shard imbalance",
        signature="search.shard.imbalance",
        runtimes=("opensearch2",),
        severity=3,
        primary=(
            Signal("search.query.p99_ms", "ms", "rise", 85.0, 2900.0),
            Signal("search.shard.max_docs_ratio", "ratio", "rise", 1.1, 6.4),
        ),
        secondary=(Signal("http.server.p99_ms", "ms", "rise", 160.0, 1900.0),),
        runbook_id="rb-search-shard-imbalance",
        summary=(
            "Documents concentrate on one shard. Mean latency stays acceptable and the "
            "tail does not, so a dashboard built on averages shows nothing wrong."
        ),
    ),
)


def pattern_by_id(pattern_id: str) -> FaultPattern:
    for pattern in PATTERNS:
        if pattern.id == pattern_id:
            return pattern
    raise KeyError(pattern_id)


def patterns_for_runtime(runtime: str) -> tuple[FaultPattern, ...]:
    return tuple(p for p in PATTERNS if p.applies_to(runtime))
