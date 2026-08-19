"""Incident and telemetry generation.

Reproducibility is the contract: an incident is fully determined by its seed, so
a triage run that goes wrong can be replayed exactly from the seed alone rather
than described.

The generated telemetry is what makes an incident diagnosable. The root service
moves first; services in its blast radius move later, attenuated by graph
distance. That time ordering is the diagnostic signal, and it is the thing the
agent has to reason from.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from meridian_agent.seed import estate
from meridian_agent.seed.faults import FaultPattern, Signal, patterns_for_runtime

SAMPLE_INTERVAL = timedelta(seconds=60)
BASELINE_WINDOW = timedelta(minutes=45)
FAULT_WINDOW = timedelta(minutes=30)
#: Seconds of delay per hop away from the root service.
PROPAGATION_LAG_PER_HOP = 90


@dataclass(frozen=True, slots=True)
class Incident:
    id: str
    service_id: str
    pattern_id: str
    title: str
    signature: str
    severity: int
    opened_at: datetime
    seed: int


@dataclass(frozen=True, slots=True)
class TelemetryPoint:
    service_id: str
    observed_at: datetime
    kind: str
    name: str
    value: float
    unit: str
    is_primary: bool


def _stable_hash(text: str) -> int:
    """A hash that survives process restarts.

    Python's built-in `hash()` on strings is salted per process, so using it
    here would make "deterministic" hold within a run and fail across runs -
    the exact bug this module exists to avoid.
    """
    return zlib.crc32(text.encode("utf-8"))


def _candidates() -> list[tuple[str, FaultPattern]]:
    """Every (service, fault) pairing the estate can actually exhibit."""
    pairs: list[tuple[str, FaultPattern]] = []
    for service in estate.services():
        for pattern in patterns_for_runtime(service.runtime):
            pairs.append((service.id, pattern))
    return sorted(pairs, key=lambda p: (p[0], p[1].id))


def generate_incident(seed: int, opened_at: datetime) -> Incident:
    """Produce the incident determined by `seed`."""
    rng = random.Random(seed)
    service_id, pattern = rng.choice(_candidates())
    service = estate.service_by_id(service_id)

    return Incident(
        id=f"inc-{seed:08x}",
        service_id=service_id,
        pattern_id=pattern.id,
        title=f"{pattern.name} on {service.name}",
        signature=pattern.signature,
        severity=pattern.severity,
        opened_at=opened_at,
        seed=seed,
    )


def _shape(pattern: FaultPattern, progress: float) -> float:
    """How far the fault has developed at `progress` through the fault window.

    Expiry is a step: it is total at the moment it happens. Everything else
    ramps. That difference is exactly what distinguishes an expiry from a
    capacity problem on the same graph, so it must be visible in the data.
    """
    if progress <= 0.0:
        return 0.0
    if pattern.id == "fault-cert-expiry":
        return 1.0
    if pattern.id == "fault-memory-leak":
        return min(1.0, progress)  # linear climb, no plateau
    # float ** float widens to Any under strict mypy; the cast keeps the
    # declared return type honest rather than silencing the check.
    return float(min(1.0, progress**0.6))  # fast onset, slow saturation


def _value(signal: Signal, development: float, rng: random.Random) -> float:
    span = signal.peak - signal.baseline
    noise = rng.gauss(0.0, abs(span) * 0.02 + abs(signal.baseline) * 0.01)
    return signal.baseline + span * development + noise


def _metric_applies(metric: str, service_id: str) -> bool:
    """Whether a secondary metric is plausible on this service.

    Emitting `db.pool.wait_ms` on the edge gateway would be noise that the agent
    then has to reason around, and noise a real estate would not produce.
    """
    service = estate.service_by_id(service_id)
    datastore_runtimes = {"postgres16", "redis7", "kafka3.8", "opensearch2"}
    is_app = service.runtime not in datastore_runtimes

    if metric.startswith(("db.", "cache.")):
        return any(
            estate.service_by_id(dep).runtime in datastore_runtimes
            for dep in estate.downstream_of(service_id)
        )
    if metric.startswith(("http.", "thread_pool.", "runtime.", "process.", "tls.")):
        return is_app
    if metric.startswith("pipeline."):
        return service.tier == estate.Tier.BATCH
    if metric.startswith(("stream.", "search.")):
        return not is_app
    return is_app


def _hop_distance(root: str) -> dict[str, int]:
    """Hops from `root` outward through its consumers."""
    distance = {root: 0}
    frontier = [root]
    while frontier:
        current = frontier.pop(0)
        for parent in sorted(estate.upstream_of(current)):
            if parent not in distance:
                distance[parent] = distance[current] + 1
                frontier.append(parent)
    return distance


def generate_telemetry(incident: Incident) -> list[TelemetryPoint]:
    """Telemetry across the baseline and fault windows for one incident."""
    pattern = next(p for p in _patterns() if p.id == incident.pattern_id)
    distance = _hop_distance(incident.service_id)

    start = incident.opened_at - BASELINE_WINDOW
    end = incident.opened_at + FAULT_WINDOW
    points: list[TelemetryPoint] = []

    step = 0
    observed = start
    while observed <= end:
        for signal in pattern.primary:
            rng = random.Random(
                incident.seed ^ _stable_hash(f"{incident.service_id}|{signal.metric}|{step}")
            )
            progress = (
                observed - incident.opened_at
            ).total_seconds() / FAULT_WINDOW.total_seconds()
            points.append(
                TelemetryPoint(
                    service_id=incident.service_id,
                    observed_at=observed,
                    kind="metric",
                    name=signal.metric,
                    value=round(_value(signal, _shape(pattern, progress), rng), 4),
                    unit=signal.unit,
                    is_primary=True,
                )
            )

        for service_id, hops in distance.items():
            if hops == 0:
                continue
            lag = timedelta(seconds=PROPAGATION_LAG_PER_HOP * hops)
            attenuation = 1.0 / (1.0 + 0.6 * (hops - 1))
            for signal in pattern.secondary:
                if not _metric_applies(signal.metric, service_id):
                    continue
                rng = random.Random(
                    incident.seed ^ _stable_hash(f"{service_id}|{signal.metric}|{step}")
                )
                progress = (
                    observed - incident.opened_at - lag
                ).total_seconds() / FAULT_WINDOW.total_seconds()
                development = _shape(pattern, progress) * attenuation
                points.append(
                    TelemetryPoint(
                        service_id=service_id,
                        observed_at=observed,
                        kind="metric",
                        name=signal.metric,
                        value=round(_value(signal, development, rng), 4),
                        unit=signal.unit,
                        is_primary=False,
                    )
                )
        observed += SAMPLE_INTERVAL
        step += 1

    return points


def _patterns() -> tuple[FaultPattern, ...]:
    from meridian_agent.seed.faults import PATTERNS

    return PATTERNS
