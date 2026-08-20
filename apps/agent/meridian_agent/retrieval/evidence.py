"""Evidence assessment: does the retrieved material support answering at all?

This module exists because of a measurement, and the measurement is worth
stating plainly since it determines the design.

Over 10 answerable and 10 deliberately-unanswerable questions on this corpus, no
single retrieval signal separates the two classes:

    dense     answerable min 0.268   unanswerable max 0.270   margin -0.003
    lexical   answerable min 7.861   unanswerable max 7.780   margin +0.081
    coverage  answerable min 0.667   unanswerable max 1.000   margin -0.333

Coverage is the most instructive failure. "What is the data retention
obligation" scores 1.00, because the corpus contains a sentence stating that
retention is explicitly NOT covered. Every query term is present, inside a
disclaimer. A coverage threshold would answer that question from the document
that says it cannot be answered.

The fused, normalised retrieval score is worse still: it reads 1.000 for both
classes, because normalising within a result set makes the top hit 1.0 whether
the match was excellent or hopeless. That is the same defect as a prior system
whose refusal gate read 0.031 on both answerable and unanswerable questions -
structurally incapable of refusing, however the threshold was tuned.

So the design does not pretend one number decides this. It uses the combined
signal to resolve the CLEAR cases for free, and routes the genuinely ambiguous
band to an explicit adjudication step. Measured on the same 20 questions, that
resolves 7 of 10 answerable and 7 of 10 unanswerable with no model call at all.

The remaining ambiguity is not tuned away. It is reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from meridian_agent.retrieval.hybrid import RetrievalResult
from meridian_agent.retrieval.tokenize import tokenize

#: Questions demanding a specific quantity. Retrieval scores cannot detect the
#: case these create: a corpus that discusses a thing at length without ever
#: stating its value scores as well as one that states it. "How long is the
#: observation period between regions" scored 8.85 - comfortably answerable -
#: against a passage that says an observation period exists and never says how
#: long it is.
_DEMANDS_A_VALUE = re.compile(
    r"\b(how (long|many|much|often|large|big)"
    r"|what (is|are) the (duration|limit|ceiling|threshold|timeout|slo|sla"
    r"|target|budget|rate|interval|period|retention|maximum|minimum|size|count))\b",
    re.IGNORECASE,
)
#: A stated quantity: a number carrying a unit, or any multi-digit figure.
#: A bare single digit does not qualify, because "Tier 0" and "Severity 1" are
#: labels rather than measurements and are everywhere in this corpus. The first
#: version of this pattern was a plain \\d and matched every one of them, which
#: is how it passed while catching nothing.
_CONTAINS_A_VALUE = re.compile(
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:ms|s|sec|secs|seconds?|min|mins|minutes?|hours?|days?|weeks?|months?"
    r"|%|percent|mb|gb|qps|connections?|instances?|messages?|retries|attempts?)\b"
    r"|\b\d{2,}\b",
    re.IGNORECASE,
)

# ── Band edges, derived from measurement ───────────────────────────────────
#
# Both were originally chosen by hand from a 22-question set. Measured against
# labelled examples, SUFFICIENT_ABOVE = 3.0 produced a false-answer rate of
# 56.6% [50.6, 62.4]: 150 of 265 unanswerable questions were marked sufficient.
# See docs/06-operations/postmortems/2026-08-20-the-refusal-gate-fails-at-scale.md
#
# They are now selected from the ROC curve against explicit error budgets, and
# the budgets are asymmetric because the errors are:
#
#   answering something unsupported  -> the failure this product exists to stop
#   refusing something answerable    -> a follow-up question
#
# Re-derive with training/derive_thresholds.py after any change to retrieval,
# the embedder, or the corpus. Do not nudge these by hand.

#: Refuse outright only where at most 2% of answerable questions are lost.
#: Deliberately conservative: INSUFFICIENT is terminal, while AMBIGUOUS still
#: reaches adjudication and can still produce an answer.
#: Measured on 715 examples: refuses 1.8% of answerable, 1.3% of
#: unanswerable. The band therefore does almost nothing, which is what a
#: 2% false-refusal budget buys over a signal this weak. It is kept because
#: an outright-refusal path has to exist, not because it earns its place.
INSUFFICIENT_BELOW = 0.74

#: Answer without adjudication only where the false-answer rate stays within 5%.
#: Measured on 715 examples: recall 0.149, false-answer rate 0.047.
#:
#: That recall is low, and it is the honest consequence of a signal with
#: AUC 0.631. Most questions now route to adjudication, which is the correct
#: posture for a gate this weak rather than a shortcoming of the threshold.
SUFFICIENT_ABOVE = 10.38

#: Fewer than this many query terms present in the top chunks means the question
#: is about something the corpus does not discuss, whatever the scores say.
MIN_TERM_COVERAGE = 0.30


class EvidenceVerdict(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    #: Neither band applies. The caller must adjudicate, and must not silently
    #: treat this as sufficient.
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    verdict: EvidenceVerdict
    combined_score: float
    dense_score: float
    lexical_score: float
    term_coverage: float
    rationale: str

    @property
    def requires_adjudication(self) -> bool:
        return self.verdict is EvidenceVerdict.AMBIGUOUS

    @property
    def permits_answering(self) -> bool:
        """Only an explicit SUFFICIENT permits answering.

        AMBIGUOUS is not a soft yes. Reading it as one is how a three-state
        assessment collapses back into the two-state one it replaced.
        """
        return self.verdict is EvidenceVerdict.SUFFICIENT


def term_coverage(query: str, result: RetrievalResult, depth: int = 3) -> float:
    """Fraction of the query's content terms present in the top chunks.

    A weak signal on its own - see the module docstring - but it catches the
    case the score-based signals miss: a question whose vocabulary simply does
    not appear in the corpus at all.
    """
    terms = set(tokenize(query))
    if not terms:
        return 0.0
    body = " ".join(hit.chunk.body for hit in result.hits[:depth]).lower()
    return len({term for term in terms if term in body}) / len(terms)


def combined_score(result: RetrievalResult) -> float:
    """Dense cosine multiplied by raw lexical score.

    Multiplied rather than summed: both signals must be present. A high BM25
    score from one repeated identifier, with no semantic proximity, should not
    clear the bar on its own, and the product is what enforces that.

    Both inputs are UNNORMALISED. The normalised fused score cannot be used
    here, because it is 1.0 for the top hit of every query by construction.
    """
    return result.top_dense * result.top_lexical


def _contains_a_value(result: RetrievalResult, depth: int = 2) -> bool:
    return any(_CONTAINS_A_VALUE.search(hit.chunk.body) for hit in result.hits[:depth])


def assess(query: str, result: RetrievalResult) -> EvidenceAssessment:
    dense = result.top_dense
    lexical = result.top_lexical
    combined = combined_score(result)
    coverage = term_coverage(query, result)

    if not result.hits:
        return EvidenceAssessment(
            EvidenceVerdict.INSUFFICIENT,
            0.0,
            0.0,
            0.0,
            0.0,
            "retrieval returned nothing",
        )

    if coverage < MIN_TERM_COVERAGE:
        return EvidenceAssessment(
            EvidenceVerdict.INSUFFICIENT,
            combined,
            dense,
            lexical,
            coverage,
            f"only {coverage:.0%} of the question's terms appear in the retrieved material",
        )

    if result.degraded:
        # Dense scores are absent, so `combined` is zero and the bands are
        # meaningless. Degraded retrieval must not be allowed to look like
        # weak evidence; it is unresolved evidence.
        return EvidenceAssessment(
            EvidenceVerdict.AMBIGUOUS,
            combined,
            dense,
            lexical,
            coverage,
            f"retrieval degraded to lexical-only ({result.degraded_reason}); "
            "the score bands do not apply",
        )

    if combined < INSUFFICIENT_BELOW:
        return EvidenceAssessment(
            EvidenceVerdict.INSUFFICIENT,
            combined,
            dense,
            lexical,
            coverage,
            f"combined evidence score {combined:.2f} is below {INSUFFICIENT_BELOW}",
        )

    if combined >= SUFFICIENT_ABOVE:
        if _DEMANDS_A_VALUE.search(query) and not _contains_a_value(result):
            # Downgraded to AMBIGUOUS, never straight to INSUFFICIENT: this is a
            # heuristic about the shape of the question, and a heuristic is not
            # entitled to refuse on its own authority.
            return EvidenceAssessment(
                EvidenceVerdict.AMBIGUOUS,
                combined,
                dense,
                lexical,
                coverage,
                f"the question asks for a specific value and scores {combined:.2f}, "
                "but the retrieved material states no value; discussing a quantity "
                "is not the same as stating it",
            )
        return EvidenceAssessment(
            EvidenceVerdict.SUFFICIENT,
            combined,
            dense,
            lexical,
            coverage,
            f"combined evidence score {combined:.2f} clears {SUFFICIENT_ABOVE}",
        )

    return EvidenceAssessment(
        EvidenceVerdict.AMBIGUOUS,
        combined,
        dense,
        lexical,
        coverage,
        f"combined evidence score {combined:.2f} falls between {INSUFFICIENT_BELOW} "
        f"and {SUFFICIENT_ABOVE}; the deterministic signals do not separate this case",
    )
