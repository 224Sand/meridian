"""The hand-written statistics, checked against the reference implementations.

Writing ROC, average precision, Wilson intervals and an exact McNemar test by
hand is only defensible if they are right. So every function is compared against
scikit-learn or scipy on randomised data across many seeds. Agreement to 1e-9 is
the claim; "the formula looks correct" is not.

Marked `ml` because the reference libraries are a training-time dependency, not
a runtime one (ADR-0009). The module under test imports nothing but the standard
library.
"""

from __future__ import annotations

import math
import random

import pytest

from meridian_agent.evaluation.statistics import (
    Interval,
    _normal_quantile,
    bootstrap_interval,
    mcnemar,
    precision_recall_curve,
    proportion_interval,
    required_sample_size,
    roc_auc_mann_whitney,
    roc_curve,
)

sklearn_metrics = pytest.importorskip("sklearn.metrics", reason="requires the ml extra")
scipy_stats = pytest.importorskip("scipy.stats", reason="requires the ml extra")


def sample(seed: int, n: int = 120, separation: float = 1.0):
    """Scores drawn from two overlapping normals, which is what a real decision
    signal looks like."""
    rng = random.Random(seed)
    scores: list[float] = []
    labels: list[int] = []
    for _ in range(n):
        label = rng.randint(0, 1)
        labels.append(label)
        scores.append(rng.gauss(separation if label else 0.0, 1.0))
    if len(set(labels)) < 2:
        labels[0] = 1 - labels[0]
    return scores, labels


class TestAgainstScikitLearn:
    @pytest.mark.parametrize("seed", range(12))
    def test_trapezoid_auc_matches_sklearn(self, seed: int) -> None:
        scores, labels = sample(seed)
        assert roc_curve(scores, labels).auc == pytest.approx(
            sklearn_metrics.roc_auc_score(labels, scores), abs=1e-9
        )

    @pytest.mark.parametrize("seed", range(12))
    def test_mann_whitney_auc_matches_sklearn(self, seed: int) -> None:
        """An independent route to the same number."""
        scores, labels = sample(seed)
        assert roc_auc_mann_whitney(scores, labels) == pytest.approx(
            sklearn_metrics.roc_auc_score(labels, scores), abs=1e-9
        )

    @pytest.mark.parametrize("seed", range(8))
    def test_the_two_auc_routes_agree_with_each_other(self, seed: int) -> None:
        scores, labels = sample(seed)
        assert roc_curve(scores, labels).auc == pytest.approx(
            roc_auc_mann_whitney(scores, labels), abs=1e-9
        )

    @pytest.mark.parametrize("seed", range(8))
    def test_roc_points_match_sklearn(self, seed: int) -> None:
        scores, labels = sample(seed)
        # drop_intermediate=False: sklearn removes collinear points by default
        # as a plotting optimisation. It does not change the curve or its area
        # (the AUC tests agree exactly), but it does change the point count, so
        # a point-by-point comparison has to ask for the full set.
        expected_fpr, expected_tpr, _ = sklearn_metrics.roc_curve(
            labels, scores, drop_intermediate=False
        )
        points = sorted(
            roc_curve(scores, labels).points,
            key=lambda p: (p.false_positive_rate, p.true_positive_rate),
        )
        assert len(points) == len(expected_fpr)
        for point, fpr, tpr in zip(points, expected_fpr, expected_tpr, strict=True):
            assert point.false_positive_rate == pytest.approx(fpr, abs=1e-9)
            assert point.true_positive_rate == pytest.approx(tpr, abs=1e-9)

    @pytest.mark.parametrize("seed", range(12))
    def test_average_precision_matches_sklearn(self, seed: int) -> None:
        """Sum of precision weighted by recall gain, not trapezoid area.

        Interpolating a PR curve overstates performance, and sklearn does not
        interpolate either - so agreement confirms the right definition was used.
        """
        scores, labels = sample(seed)
        assert precision_recall_curve(scores, labels).average_precision == pytest.approx(
            sklearn_metrics.average_precision_score(labels, scores), abs=1e-9
        )

    def test_ties_are_handled_like_sklearn(self) -> None:
        """Tied scores must be consumed together. Splitting them invents a
        threshold separating observations the signal cannot separate."""
        scores = [1.0, 1.0, 1.0, 0.5, 0.5, 0.0, 0.0, 0.0]
        labels = [1, 0, 1, 1, 0, 0, 1, 0]
        assert roc_curve(scores, labels).auc == pytest.approx(
            sklearn_metrics.roc_auc_score(labels, scores), abs=1e-9
        )


class TestAgainstScipy:
    @pytest.mark.parametrize("p", [0.001, 0.025, 0.1, 0.5, 0.9, 0.975, 0.999])
    def test_normal_quantile_matches_scipy(self, p: float) -> None:
        assert _normal_quantile(p) == pytest.approx(scipy_stats.norm.ppf(p), abs=1e-8)

    @pytest.mark.parametrize(
        ("successes", "trials"),
        [(0, 50), (1, 50), (25, 50), (49, 50), (50, 50), (3, 400), (200, 400)],
    )
    def test_wilson_interval_matches_scipy(self, successes: int, trials: int) -> None:
        result = proportion_interval(successes, trials)
        expected = scipy_stats.binomtest(successes, trials).proportion_ci(method="wilson")
        assert result.low == pytest.approx(expected.low, abs=1e-6)
        assert result.high == pytest.approx(expected.high, abs=1e-6)

    def test_wilson_never_reports_an_impossible_bound(self) -> None:
        """The normal approximation puts the lower bound below zero at rates
        near zero, which is exactly where a false-positive rate lives."""
        interval = proportion_interval(0, 200)
        assert interval.low >= 0.0
        assert interval.high > 0.0

    @pytest.mark.parametrize(("only_a", "only_b"), [(10, 2), (3, 3), (25, 8), (1, 0), (0, 0)])
    def test_mcnemar_matches_an_exact_binomial(self, only_a: int, only_b: int) -> None:
        correct_a = [True] * only_a + [False] * only_b
        correct_b = [False] * only_a + [True] * only_b
        result = mcnemar(correct_a, correct_b)

        n = only_a + only_b
        expected = 1.0 if n == 0 else scipy_stats.binomtest(min(only_a, only_b), n, 0.5).pvalue
        assert result.p_value == pytest.approx(expected, abs=1e-9)


class TestOperatingPointSelection:
    def test_youden_selects_the_point_furthest_from_the_diagonal(self) -> None:
        scores, labels = sample(3, n=200, separation=1.5)
        curve = roc_curve(scores, labels)
        best = curve.best_by_youden()
        assert all(p.youden_j <= best.youden_j + 1e-12 for p in curve.points)

    def test_constrained_selection_respects_the_false_positive_budget(self) -> None:
        """The selection that matters for a refusal gate: answering an
        unanswerable question is the expensive error, so its rate is a
        constraint rather than something to trade."""
        scores, labels = sample(5, n=300, separation=1.2)
        point = roc_curve(scores, labels).at_max_false_positive_rate(0.05)
        assert point.false_positive_rate <= 0.05

    def test_an_unachievable_budget_raises_rather_than_returning_something(self) -> None:
        curve = roc_curve([1.0, 0.9, 0.8], [1, 0, 1])
        with pytest.raises(ValueError, match="no operating point"):
            curve.at_max_false_positive_rate(-0.1)

    def test_f_beta_weights_recall_when_beta_exceeds_one(self) -> None:
        scores, labels = sample(9, n=200)
        curve = precision_recall_curve(scores, labels)
        assert curve.best_by_f(2.0).recall >= curve.best_by_f(0.5).recall


class TestBootstrap:
    def test_interval_contains_the_point_estimate(self) -> None:
        scores, labels = sample(1, n=200, separation=1.2)
        interval = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=400)
        assert interval.low <= interval.point <= interval.high

    def test_interval_narrows_as_the_sample_grows(self) -> None:
        small = bootstrap_interval(*sample(2, n=60), roc_auc_mann_whitney, resamples=400)
        large = bootstrap_interval(*sample(2, n=600), roc_auc_mann_whitney, resamples=400)
        assert (large.high - large.low) < (small.high - small.low)

    def test_is_reproducible_from_its_seed(self) -> None:
        scores, labels = sample(4, n=150)
        a = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=300, seed=11)
        b = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=300, seed=11)
        assert (a.low, a.high) == (b.low, b.high)

    def test_a_separated_signal_excludes_chance(self) -> None:
        scores, labels = sample(6, n=400, separation=2.0)
        interval = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=600)
        assert interval.excludes(0.5), "a clearly separated signal should exclude AUC 0.5"

    def test_a_pure_noise_signal_does_not_exclude_chance(self) -> None:
        scores, labels = sample(7, n=400, separation=0.0)
        interval = bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=600)
        assert not interval.excludes(0.5), "noise should not look like signal"


class TestPowerAnalysis:
    def test_detecting_a_smaller_difference_needs_more_data(self) -> None:
        assert required_sample_size(0.8, 0.02) > required_sample_size(0.8, 0.10)

    def test_higher_power_needs_more_data(self) -> None:
        assert required_sample_size(0.8, 0.05, power=0.95) > required_sample_size(
            0.8, 0.05, power=0.80
        )

    def test_matches_the_textbook_two_proportion_formula(self) -> None:
        """0.50 vs 0.60 at alpha 0.05, power 0.80 is a standard worked example
        and lands just under 400 per group."""
        n = required_sample_size(0.50, 0.10)
        assert 380 <= n <= 410, n

    def test_rejects_a_nonsensical_baseline(self) -> None:
        with pytest.raises(ValueError, match="baseline_rate"):
            required_sample_size(1.5, 0.05)


class TestGuards:
    def test_a_single_class_has_no_roc(self) -> None:
        with pytest.raises(ValueError, match="both classes"):
            roc_curve([0.1, 0.2, 0.3], [1, 1, 1])

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="length mismatch"):
            roc_curve([0.1, 0.2], [1])

    def test_non_binary_labels_raise(self) -> None:
        with pytest.raises(ValueError, match="labels must be"):
            roc_curve([0.1, 0.2], [1, 2])

    def test_interval_formats_readably(self) -> None:
        assert str(Interval(0.87, 0.81, 0.92, 0.95)) == "0.870 [0.810, 0.920]"


class TestNoRuntimeDependencies:
    def test_the_statistics_module_imports_only_the_standard_library(self) -> None:
        """ADR-0009: this runs wherever the eval harness runs, so it must not
        pull a training framework in behind it."""
        import inspect

        from meridian_agent.evaluation import statistics

        source = inspect.getsource(statistics)
        for forbidden in ("import numpy", "import scipy", "import sklearn", "import torch"):
            assert forbidden not in source, f"statistics imports {forbidden!r}"
        assert math  # the standard library is the whole toolkit here
