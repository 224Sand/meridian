"""Statistics for evaluating a binary decision, written against the standard
library.

Two reasons it carries no dependencies. First, ADR-0009: the runtime does not
ship training frameworks, and these functions run wherever the eval harness
runs. Second, and more usefully, an implementation you wrote is an
implementation you can be questioned about — `tests/test_statistics.py` checks
every function here against scikit-learn and scipy, so the claim is not that the
maths looks right but that it agrees with the reference to 1e-9.

The point of this module is to replace the sentence "I picked 3.0" with an
operating point, an interval, and a test for whether a change is real.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

Scores = list[float]
Labels = list[int]  # 1 = positive class, 0 = negative
#: Any statistic computed from paired scores and labels, e.g. an AUC.
Statistic = Callable[[Scores, Labels], float]


def _validate(scores: Scores, labels: Labels) -> None:
    if len(scores) != len(labels):
        raise ValueError(f"length mismatch: {len(scores)} scores, {len(labels)} labels")
    if not scores:
        raise ValueError("no observations")
    if set(labels) - {0, 1}:
        raise ValueError("labels must be 0 or 1")
    if len(set(labels)) < 2:
        raise ValueError("both classes must be present; a one-class set has no ROC")


# ── ROC ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RocPoint:
    threshold: float
    false_positive_rate: float
    true_positive_rate: float

    @property
    def youden_j(self) -> float:
        """Sensitivity + specificity - 1.

        The vertical distance from the diagonal. Maximising it picks the
        threshold that separates the classes best when a false positive and a
        false negative are weighted equally - which they are not here, so the
        result is a starting point rather than the answer.
        """
        return self.true_positive_rate - self.false_positive_rate


@dataclass(frozen=True, slots=True)
class RocCurve:
    points: tuple[RocPoint, ...]

    @property
    def auc(self) -> float:
        """Area under the curve by the trapezoid rule.

        Equal to the probability that a randomly chosen positive scores above a
        randomly chosen negative. `roc_auc_mann_whitney` computes it the other
        way and a test asserts the two agree.
        """
        ordered = sorted(self.points, key=lambda p: (p.false_positive_rate, p.true_positive_rate))
        area = 0.0
        for left, right in pairwise(ordered):
            width = right.false_positive_rate - left.false_positive_rate
            area += width * (left.true_positive_rate + right.true_positive_rate) / 2
        return area

    def best_by_youden(self) -> RocPoint:
        return max(self.points, key=lambda p: (p.youden_j, -p.false_positive_rate))

    def at_max_false_positive_rate(self, limit: float) -> RocPoint:
        """The most sensitive operating point whose false-positive rate stays
        within `limit`.

        This is the selection that matters for a refusal gate: answering a
        question the evidence cannot support is the expensive error, so the
        false-positive rate is a constraint rather than something to trade.
        """
        eligible = [p for p in self.points if p.false_positive_rate <= limit]
        if not eligible:
            raise ValueError(f"no operating point achieves a false-positive rate <= {limit}")
        return max(eligible, key=lambda p: (p.true_positive_rate, -p.false_positive_rate))


def roc_curve(scores: Scores, labels: Labels) -> RocCurve:
    _validate(scores, labels)
    positives = sum(labels)
    negatives = len(labels) - positives

    ordered = sorted(zip(scores, labels, strict=True), key=lambda pair: -pair[0])

    points = [RocPoint(math.inf, 0.0, 0.0)]
    true_positives = 0
    false_positives = 0
    index = 0
    while index < len(ordered):
        threshold = ordered[index][0]
        # Tied scores must be consumed together; splitting them invents a
        # threshold that separates observations the model cannot separate.
        while index < len(ordered) and ordered[index][0] == threshold:
            if ordered[index][1] == 1:
                true_positives += 1
            else:
                false_positives += 1
            index += 1
        points.append(RocPoint(threshold, false_positives / negatives, true_positives / positives))
    return RocCurve(points=tuple(points))


def roc_auc_mann_whitney(scores: Scores, labels: Labels) -> float:
    """AUC as the Mann-Whitney U statistic, with ties counted as half.

    An independent route to the same number. Agreement between this and the
    trapezoid area is what makes either believable.
    """
    _validate(scores, labels)
    positives = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    negatives = [s for s, y in zip(scores, labels, strict=True) if y == 0]

    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


# ── Precision-recall ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PrPoint:
    threshold: float
    precision: float
    recall: float

    def f_beta(self, beta: float = 1.0) -> float:
        if self.precision == 0.0 and self.recall == 0.0:
            return 0.0
        b2 = beta * beta
        return (1 + b2) * self.precision * self.recall / (b2 * self.precision + self.recall)


@dataclass(frozen=True, slots=True)
class PrCurve:
    points: tuple[PrPoint, ...]

    @property
    def average_precision(self) -> float:
        """Sum of precision weighted by the increase in recall.

        Not the trapezoid area: interpolating between operating points on a PR
        curve overstates performance, because precision is not monotonic in
        recall and the interpolated region may be unreachable.
        """
        ordered = sorted(self.points, key=lambda p: p.recall)
        total = 0.0
        previous_recall = 0.0
        for point in ordered:
            total += (point.recall - previous_recall) * point.precision
            previous_recall = point.recall
        return total

    def best_by_f(self, beta: float = 1.0) -> PrPoint:
        return max(self.points, key=lambda p: p.f_beta(beta))


def precision_recall_curve(scores: Scores, labels: Labels) -> PrCurve:
    _validate(scores, labels)
    positives = sum(labels)
    ordered = sorted(zip(scores, labels, strict=True), key=lambda pair: -pair[0])

    points: list[PrPoint] = []
    true_positives = 0
    predicted = 0
    index = 0
    while index < len(ordered):
        threshold = ordered[index][0]
        while index < len(ordered) and ordered[index][0] == threshold:
            if ordered[index][1] == 1:
                true_positives += 1
            predicted += 1
            index += 1
        points.append(PrPoint(threshold, true_positives / predicted, true_positives / positives))
    return PrCurve(points=tuple(points))


# ── Confidence intervals ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Interval:
    point: float
    low: float
    high: float
    confidence: float

    def __str__(self) -> str:
        return f"{self.point:.3f} [{self.low:.3f}, {self.high:.3f}]"

    def excludes(self, value: float) -> bool:
        """Whether `value` lies outside the interval.

        The honest way to ask "is this difference real" for a single estimate.
        """
        return not (self.low <= value <= self.high)


def bootstrap_interval(
    scores: Scores,
    labels: Labels,
    statistic: Statistic,
    *,
    resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 20260820,
) -> Interval:
    """Percentile bootstrap over paired (score, label) observations.

    Resampling pairs rather than scores keeps each observation's label attached
    to it; resampling them independently would destroy the association the
    statistic measures and produce an interval around noise.

    A resample that lands on a single class is skipped rather than counted:
    every statistic here is undefined without both classes, and substituting
    zero would drag the interval down for a reason that has nothing to do with
    the estimator.
    """
    _validate(scores, labels)
    rng = random.Random(seed)
    observations = list(zip(scores, labels, strict=True))
    n = len(observations)

    estimates: list[float] = []
    for _ in range(resamples):
        sample = [observations[rng.randrange(n)] for _ in range(n)]
        sample_labels = [y for _, y in sample]
        if len(set(sample_labels)) < 2:
            continue
        estimates.append(statistic([s for s, _ in sample], sample_labels))

    if not estimates:
        raise ValueError("no resample contained both classes")

    estimates.sort()
    tail = (1.0 - confidence) / 2
    low = estimates[max(0, math.floor(tail * len(estimates)))]
    high = estimates[min(len(estimates) - 1, math.ceil((1 - tail) * len(estimates)) - 1)]
    return Interval(statistic(scores, labels), low, high, confidence)


def proportion_interval(successes: int, trials: int, *, confidence: float = 0.95) -> Interval:
    """Wilson score interval for a proportion.

    Not the normal approximation. At the proportions this project actually cares
    about - a false-positive rate near zero - the normal interval extends below
    zero and reports a lower bound that cannot occur.
    """
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must lie within trials")

    z = _normal_quantile(1 - (1 - confidence) / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return Interval(p, max(0.0, centre - spread), min(1.0, centre + spread), confidence)


def _normal_quantile(p: float) -> float:
    """Inverse standard normal CDF, Acklam's rational approximation.

    Accurate to about 1e-9 across the range, which is far beyond what any
    decision in this project turns on.
    """
    if not 0 < p < 1:
        raise ValueError("p must lie strictly between 0 and 1")

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)

    low, high = 0.02425, 1 - 0.02425
    if p < low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


# ── Comparing two decision rules ───────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class McNemarResult:
    only_a_correct: int
    only_b_correct: int
    p_value: float

    @property
    def significant_at(self) -> float:
        return self.p_value

    def is_significant(self, alpha: float = 0.05) -> bool:
        return self.p_value < alpha


def mcnemar(correct_a: list[bool], correct_b: list[bool]) -> McNemarResult:
    """Exact McNemar test for two rules evaluated on the SAME observations.

    The right test for "is B better than A" here, because both rules see
    identical inputs and the comparison is paired. Comparing two independent
    accuracy figures with a two-sample test throws away that pairing and needs a
    much larger sample to detect the same difference.

    Only the discordant pairs carry information: cases both rules got right, or
    both got wrong, say nothing about which is better. The exact binomial is
    used rather than the chi-square approximation, which is unreliable when the
    discordant count is small - and it usually is.
    """
    if len(correct_a) != len(correct_b):
        raise ValueError("both rules must be evaluated on the same observations")

    only_a = sum(1 for a, b in zip(correct_a, correct_b, strict=True) if a and not b)
    only_b = sum(1 for a, b in zip(correct_a, correct_b, strict=True) if b and not a)
    n = only_a + only_b

    if n == 0:
        return McNemarResult(0, 0, 1.0)

    smaller = min(only_a, only_b)
    tail = sum(math.comb(n, k) for k in range(smaller + 1)) / (2**n)
    return McNemarResult(only_a, only_b, min(1.0, 2 * tail))


def required_sample_size(
    baseline_rate: float,
    detectable_difference: float,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Observations per group needed to detect a change in a proportion.

    The question this answers is the one that should be asked before building an
    evaluation set, not after it disappoints: how many examples are needed
    before "no significant difference" means anything at all.
    """
    if not 0 < baseline_rate < 1:
        raise ValueError("baseline_rate must lie strictly between 0 and 1")
    if detectable_difference <= 0:
        raise ValueError("detectable_difference must be positive")

    p1 = baseline_rate
    p2 = min(0.999999, max(0.000001, baseline_rate + detectable_difference))
    pooled = (p1 + p2) / 2

    z_alpha = _normal_quantile(1 - alpha / 2)
    z_beta = _normal_quantile(power)

    numerator = (
        z_alpha * math.sqrt(2 * pooled * (1 - pooled))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return math.ceil(numerator / (p2 - p1) ** 2)
