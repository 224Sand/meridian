"""Incident and telemetry generation.

The property that matters most is reproducibility: if an incident cannot be
regenerated from its seed, a triage run that goes wrong can only be described,
not replayed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from meridian_agent.seed import estate
from meridian_agent.seed.faults import PATTERNS, Signal, pattern_by_id
from meridian_agent.seed.incidents import (
    BASELINE_WINDOW,
    FAULT_WINDOW,
    generate_incident,
    generate_telemetry,
)

T0 = datetime(2026, 8, 20, 14, 0, tzinfo=UTC)


class TestDeterminism:
    def test_same_seed_yields_the_same_incident(self) -> None:
        assert generate_incident(42, T0) == generate_incident(42, T0)

    def test_same_seed_yields_byte_identical_telemetry(self) -> None:
        a = generate_telemetry(generate_incident(42, T0))
        b = generate_telemetry(generate_incident(42, T0))
        assert a == b

    def test_different_seeds_yield_different_incidents(self) -> None:
        ids = {generate_incident(s, T0).id for s in range(30)}
        assert len(ids) == 30

    def test_seeds_reach_a_variety_of_patterns(self) -> None:
        patterns = {generate_incident(s, T0).pattern_id for s in range(200)}
        assert len(patterns) >= 6, f"only {len(patterns)} distinct patterns in 200 seeds"

    def test_telemetry_does_not_depend_on_process_hash_seed(self) -> None:
        """A salted hash would make this pass in-process and fail across runs."""
        import subprocess
        import sys

        script = (
            "from datetime import datetime, timezone;"
            "from meridian_agent.seed.incidents import generate_incident, generate_telemetry;"
            "i=generate_incident(7, datetime(2026,8,20,14,0,tzinfo=timezone.utc));"
            "t=generate_telemetry(i);"
            "print(round(sum(p.value for p in t), 6))"
        )
        runs = {
            subprocess.run(  # noqa: S603
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                check=True,
                env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            ).stdout.strip()
            for seed in ("0", "1", "12345")
        }
        assert len(runs) == 1, f"telemetry varied with PYTHONHASHSEED: {runs}"


class TestConsistency:
    def test_incident_pattern_matches_the_service_runtime(self) -> None:
        for seed in range(60):
            incident = generate_incident(seed, T0)
            service = estate.service_by_id(incident.service_id)
            assert pattern_by_id(incident.pattern_id).applies_to(service.runtime)

    def test_severity_comes_from_the_pattern(self) -> None:
        incident = generate_incident(42, T0)
        assert incident.severity == pattern_by_id(incident.pattern_id).severity


class TestTelemetryShape:
    def test_covers_the_baseline_and_fault_windows(self) -> None:
        incident = generate_incident(42, T0)
        points = generate_telemetry(incident)
        earliest = min(p.observed_at for p in points)
        latest = max(p.observed_at for p in points)
        assert earliest == incident.opened_at - BASELINE_WINDOW
        assert latest <= incident.opened_at + FAULT_WINDOW

    def test_primary_signals_are_on_the_root_service_only(self) -> None:
        incident = generate_incident(42, T0)
        primary = {p.service_id for p in generate_telemetry(incident) if p.is_primary}
        assert primary == {incident.service_id}

    def test_secondary_signals_stay_within_the_blast_radius(self) -> None:
        incident = generate_incident(42, T0)
        radius = set(estate.blast_radius(incident.service_id))
        secondary = {p.service_id for p in generate_telemetry(incident) if not p.is_primary}
        assert secondary <= radius

    def test_baseline_is_quiet_and_fault_window_is_not(self) -> None:
        """The evidence must actually distinguish before from after."""
        incident = generate_incident(42, T0)
        pattern = pattern_by_id(incident.pattern_id)
        signal: Signal = pattern.primary[0]
        points = [
            p for p in generate_telemetry(incident) if p.is_primary and p.name == signal.metric
        ]
        before = [p.value for p in points if p.observed_at < incident.opened_at]
        after = [
            p.value for p in points if p.observed_at >= incident.opened_at + timedelta(minutes=20)
        ]

        assert before and after
        drift = abs(sum(before) / len(before) - signal.baseline)
        assert drift < abs(signal.peak - signal.baseline) * 0.1, "baseline is not quiet"

        if signal.direction == "rise":
            assert max(after) > signal.baseline + (signal.peak - signal.baseline) * 0.4
        else:
            assert min(after) < signal.baseline - (signal.baseline - signal.peak) * 0.4

    def test_downstream_effects_lag_the_root_cause(self) -> None:
        """Time ordering is the diagnostic signal; without it triage is guesswork."""
        incident = generate_incident(42, T0)
        points = generate_telemetry(incident)
        secondary = [p for p in points if not p.is_primary]
        if not secondary:
            pytest.skip("this seed's incident has no in-radius secondary metrics")

        metric = secondary[0].name
        service = secondary[0].service_id
        series = sorted(
            (p for p in secondary if p.name == metric and p.service_id == service),
            key=lambda p: p.observed_at,
        )
        at_onset = [p.value for p in series if p.observed_at == incident.opened_at]
        later = [
            p.value for p in series if p.observed_at >= incident.opened_at + timedelta(minutes=15)
        ]
        assert at_onset and later
        assert max(later) != at_onset[0], "downstream signal never moved"

    def test_metrics_are_plausible_for_the_service(self) -> None:
        """A datastore metric on the edge gateway is noise a real estate would not emit."""
        datastore_runtimes = {"postgres16", "redis7", "kafka3.8", "opensearch2"}
        for seed in range(25):
            for point in generate_telemetry(generate_incident(seed, T0)):
                if point.is_primary:
                    continue
                service = estate.service_by_id(point.service_id)
                if point.name.startswith(("http.", "thread_pool.", "process.", "runtime.")):
                    assert service.runtime not in datastore_runtimes, (
                        f"{point.name} emitted on datastore {service.name}"
                    )


class TestFaultCatalogue:
    def test_every_pattern_has_a_runbook_and_signals(self) -> None:
        for pattern in PATTERNS:
            assert pattern.runbook_id.startswith("rb-")
            assert pattern.primary, f"{pattern.id} has no identifying signal"
            assert pattern.summary.strip()

    def test_pattern_ids_are_unique(self) -> None:
        assert len({p.id for p in PATTERNS}) == len(PATTERNS)

    def test_a_rising_signal_must_peak_above_baseline(self) -> None:
        with pytest.raises(ValueError, match="must peak above baseline"):
            Signal("x", "ms", "rise", 100.0, 10.0)

    def test_a_falling_signal_must_trough_below_baseline(self) -> None:
        with pytest.raises(ValueError, match="must trough below baseline"):
            Signal("x", "ratio", "fall", 0.1, 0.9)

    def test_every_pattern_is_reachable_from_some_service(self) -> None:
        runtimes = {s.runtime for s in estate.services()}
        for pattern in PATTERNS:
            assert any(pattern.applies_to(r) for r in runtimes), f"{pattern.id} is unreachable"
