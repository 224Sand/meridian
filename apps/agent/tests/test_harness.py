"""The evaluation harness.

The property that matters is asymmetry: `core` blocks and `probe` does not. A
probe suite that could fail the build would be tuned until it stopped
complaining, and the limitations it records would disappear from view without
being fixed.
"""

from __future__ import annotations

import json

import pytest

from sandscope_agent.evaluation.harness import (
    FALSE_ANSWER_BUDGET,
    Check,
    SuiteResult,
    run_core,
    run_probe,
    write_report,
)


@pytest.fixture(scope="module")
def core() -> SuiteResult:
    return run_core()


@pytest.fixture(scope="module")
def probe() -> SuiteResult:
    return run_probe()


class TestCoreSuite:
    def test_core_passes(self, core: SuiteResult) -> None:
        assert core.passed, [f"{c.name}: {c.detail}" for c in core.failures]

    def test_core_checks_the_false_answer_rate(self, core: SuiteResult) -> None:
        check = next(c for c in core.checks if c.name == "false_answer_rate_within_budget")
        assert check.passed
        assert check.value is not None and check.value <= FALSE_ANSWER_BUDGET * 2

    def test_core_refuses_to_report_on_a_small_sample(self, core: SuiteResult) -> None:
        """The Sprint 3 lesson as a check rather than as advice: a gate result
        from fewer than 100 labelled examples is a smoke test."""
        check = next(c for c in core.checks if c.name == "sample_is_large_enough")
        assert check.passed
        assert "100 of each" in check.detail

    def test_core_asserts_the_interval_not_the_point_estimate(self, core: SuiteResult) -> None:
        """A point estimate that happens to land inside budget is not evidence
        the system is inside budget."""
        import inspect

        from sandscope_agent.evaluation import harness

        source = inspect.getsource(harness.run_core)
        assert "rate.high" in source, "the false-answer check must assert the upper bound"

    def test_core_covers_every_fault_pattern(self, core: SuiteResult) -> None:
        check = next(c for c in core.checks if c.name == "every_fault_reaches_its_runbook")
        assert check.passed, check.detail


class TestProbeSuite:
    def test_probe_warns(self, probe: SuiteResult) -> None:
        """It is EXPECTED to warn. A quiet probe suite means either the
        limitations were fixed - which would be news - or the suite stopped
        looking."""
        assert probe.warned, "the probe suite reported nothing; verify it still measures anything"

    def test_probe_never_blocks(self, probe: SuiteResult) -> None:
        """A probe suite that could fail the build would be tuned until it
        stopped complaining."""
        assert probe.passed

    def test_probe_records_the_overlap_that_shapes_the_design(self, probe: SuiteResult) -> None:
        check = next(c for c in probe.checks if c.name == "signals_still_overlap")
        assert not check.passed, "if the classes have separated, the gate should be re-derived"

    def test_probe_records_the_chunk_selection_ceiling(self, probe: SuiteResult) -> None:
        check = next(c for c in probe.checks if c.name == "chunk_selection_is_weak")
        assert check.value is not None
        assert 0.0 <= check.value <= 1.0

    def test_every_probe_check_explains_itself(self, probe: SuiteResult) -> None:
        """A warning nobody can interpret gets ignored, which is the same as not
        reporting it."""
        for check in probe.checks:
            assert len(check.detail) > 40, f"{check.name} has no usable explanation"


class TestReport:
    def test_report_is_written_and_parses(self, core: SuiteResult, probe: SuiteResult) -> None:
        path = write_report([core, probe], git_sha="test")
        data = json.loads(path.read_text())
        assert {s["suite"] for s in data["suites"]} == {"core", "probe"}
        assert data["git_sha"] == "test"

    def test_report_records_warnings_separately_from_failures(
        self, core: SuiteResult, probe: SuiteResult
    ) -> None:
        data = json.loads(write_report([core, probe], git_sha="test").read_text())
        by_suite = {s["suite"]: s for s in data["suites"]}
        assert by_suite["probe"]["passed"] is True
        assert by_suite["probe"]["warned"] is True

    def test_a_failing_check_surfaces_in_failures(self) -> None:
        result = SuiteResult(
            "core",
            False,
            False,
            [Check("a", True, "fine"), Check("b", False, "broken")],
        )
        assert [c.name for c in result.failures] == ["b"]


class TestNoLiveModelCalls:
    def test_the_harness_makes_no_model_call(self) -> None:
        """A metric that varies with a provider's mood is not a regression test."""
        import ast
        import inspect

        from sandscope_agent.evaluation import harness

        tree = ast.parse(inspect.getsource(harness))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("router" in m or "orchestrator" in m for m in imported), imported
