"""Re-derive the evidence gate's band edges from measurement (FR-027).

Referenced by the constants in sandscope_agent/retrieval/evidence.py. Run it
after any change to retrieval, the embedder, or the corpus - all three move the
score distribution, and a threshold derived under the old one is a threshold
chosen by history rather than by evidence.

    python training/derive_thresholds.py

The budgets are asymmetric on purpose. Answering something the evidence cannot
support is the failure this product exists to prevent; refusing something
answerable costs a follow-up question. INSUFFICIENT is terminal while AMBIGUOUS
still reaches adjudication, so the refusal edge is the more conservative one.
"""

from __future__ import annotations

from sandscope_agent.evaluation.dataset import Label, build_questions
from sandscope_agent.evaluation.statistics import (
    bootstrap_interval,
    roc_auc_mann_whitney,
    roc_curve,
)
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.evidence import combined_score
from sandscope_agent.retrieval.hybrid import HybridRetriever

FALSE_ANSWER_BUDGET = 0.05
FALSE_REFUSAL_BUDGET = 0.02


def main() -> None:
    retriever = HybridRetriever(chunks=chunk_corpus(load_corpus()), embedder=HashingEmbedder())
    retriever.build_vectors()

    questions = build_questions()
    scores = [combined_score(retriever.search(q.text)) for q in questions]
    labels = [1 if q.label is Label.ANSWERABLE else 0 for q in questions]

    print(f"n = {len(questions)}  ({sum(labels)} answerable, {len(labels) - sum(labels)} not)")
    print(f"ROC AUC {bootstrap_interval(scores, labels, roc_auc_mann_whitney, resamples=1500)}\n")

    curve = roc_curve(scores, labels)

    upper = curve.at_max_false_positive_rate(FALSE_ANSWER_BUDGET)
    print(f"SUFFICIENT_ABOVE  (false-answer budget {FALSE_ANSWER_BUDGET:.0%})")
    print(
        f"  threshold {upper.threshold:.2f}   recall {upper.true_positive_rate:.3f}"
        f"   false-answer rate {upper.false_positive_rate:.3f}"
    )

    eligible = [
        p
        for p in curve.points
        if p.true_positive_rate >= 1 - FALSE_REFUSAL_BUDGET and p.threshold != float("inf")
    ]
    lower = min(eligible, key=lambda p: (p.false_positive_rate, -p.threshold))
    print(f"\nINSUFFICIENT_BELOW  (false-refusal budget {FALSE_REFUSAL_BUDGET:.0%})")
    print(
        f"  threshold {lower.threshold:.2f}   refuses {1 - lower.true_positive_rate:.1%}"
        f" of answerable, {1 - lower.false_positive_rate:.1%} of unanswerable"
    )

    print("\nCopy these into sandscope_agent/retrieval/evidence.py. Do not round them")
    print("toward a nicer number; the budget is the constraint, not the digits.")


if __name__ == "__main__":
    main()
