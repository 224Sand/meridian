"""Citation extraction and uncited-claim detection.

A citation attaches to a statement, not to a paragraph. A model that puts one
[1] at the end of six sentences has cited one sentence and asserted five, and a
check operating on whole responses cannot tell the difference.

So the unit here is the sentence, and a sentence that makes a factual claim
without a marker is a defect the graph loops back on.
"""

from __future__ import annotations

import re
from typing import Any

from sandscope_agent.retrieval.hybrid import Retrieved

_MARKER = re.compile(r"\[(\d+)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

#: Sentences that assert nothing and therefore need no support. Kept short: an
#: over-broad list here quietly excuses real claims from needing evidence, which
#: is the failure this module exists to catch.
_NON_CLAIM = re.compile(
    r"^\s*(?:"
    r"i (?:do not|don't|cannot|can't) (?:know|say|tell)"
    r"|the evidence (?:does not|doesn't) (?:say|state|cover|support)"
    r"|(?:this|that) is not (?:stated|covered|documented)"
    r"|no (?:evidence|passage|document) (?:supports|states|covers)"
    r"|policy is silent"
    r"|next steps?[:.]?"
    r"|summary[:.]?"
    r"|assessment[:.]?"
    r")",
    re.IGNORECASE,
)
#: A sentence with no digits, no identifiers and under this many words is
#: connective tissue rather than a claim.
_MIN_CLAIM_WORDS = 5


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.strip()) if s.strip()]


def is_claim(sentence: str) -> bool:
    """Whether a sentence asserts something that needs support.

    Explicit statements of absence are not claims. Refusing to answer must not
    itself require a citation, or the system can never say "I don't know"
    without contradicting its own rule.
    """
    if _NON_CLAIM.search(sentence):
        return False
    words = len(sentence.split())
    if words < _MIN_CLAIM_WORDS:
        return False
    return True


def extract_citations(text: str, hits: list[Retrieved]) -> list[dict[str, Any]]:
    """Map each [n] marker to the chunk it refers to.

    A marker pointing outside the evidence set is recorded with
    `resolved=False` rather than dropped. A fabricated citation is worse than a
    missing one - it looks like grounding - so it has to survive into the record
    where a check can see it.
    """
    citations: list[dict[str, Any]] = []
    for ordinal, sentence in enumerate(split_sentences(text)):
        for marker in _MARKER.finditer(sentence):
            index = int(marker.group(1)) - 1
            resolved = 0 <= index < len(hits)
            citations.append(
                {
                    "ordinal": ordinal,
                    "claim_text": sentence,
                    "marker": index + 1,
                    "chunk_id": hits[index].chunk.id if resolved else None,
                    "score": hits[index].score if resolved else 0.0,
                    "resolved": resolved,
                }
            )
    return citations


def uncited_claims(text: str) -> list[str]:
    """Sentences that assert something and carry no marker."""
    return [s for s in split_sentences(text) if is_claim(s) and not _MARKER.search(s)]


def fabricated_citations(text: str, hits: list[Retrieved]) -> list[int]:
    """Markers pointing outside the evidence that was actually supplied."""
    return [c["marker"] for c in extract_citations(text, hits) if not c["resolved"]]
