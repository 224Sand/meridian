"""Labelled question generation, with labels true by construction (ADR-0010).

The fast way to build this dataset is to have a model write the questions and
label them. That is invalid here. A classifier trained on model-assigned labels
learns the model's judgement of what is answerable, errors included, and
evaluating it against model-derived ground truth measures agreement rather than
correctness. This product's central claim is that it can tell grounded from
ungrounded; ground truth that is itself a model's opinion makes that claim
unfalsifiable.

So every label here is a property of HOW the example was constructed:

  * answerable   - the question is generated FROM a specific chunk, so the gold
                   reference is known rather than inferred
  * unanswerable - the question is generated from a topic GAPS.md records as
                   absent, or by transferring a property to an entity that does
                   not document it. Absence is then VERIFIED against the corpus
                   rather than assumed.

No function in this module calls a model. A test asserts that.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from meridian_agent.retrieval.corpus import Chunk, Document, chunk_corpus, load_corpus
from meridian_agent.retrieval.tokenize import tokenize
from meridian_agent.seed import estate
from meridian_agent.seed.faults import PATTERNS


class Label(StrEnum):
    ANSWERABLE = "answerable"
    UNANSWERABLE = "unanswerable"


class Mechanism(StrEnum):
    """How the example was built. This is the audit trail for its label."""

    SYMPTOM = "symptom_from_fault_signal"
    SECTION = "section_from_runbook_heading"
    POLICY = "policy_value_lookup"
    GAP_TOPIC = "topic_absent_from_corpus"
    PROPERTY_TRANSFER = "property_documented_for_another_entity"
    PRESUPPOSITION = "entity_cannot_exhibit_this_fault"


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    text: str
    label: Label
    mechanism: Mechanism
    #: The document the answer lives in. None for every unanswerable example, by
    #: definition rather than by omission.
    gold_document_id: str | None
    #: The document this example derives from. Splits are made on THIS, so that
    #: two questions sharing a source never straddle train and test.
    group: str


# ── Answerable: symptom questions from the fault catalogue ──────────────────

_SYMPTOM_TEMPLATES = (
    "{metric} is {participle} on {service}, what is happening",
    "what causes {metric} to {verb}",
    "{service} shows {metric} {participle}, what should I check first",
    "we are seeing {metric} {participle} on {service}, what does that indicate",
    "is {metric} {participle} on {service} something to act on",
    "what remediation applies when {metric} {verb}s on {service}",
    "how do I confirm that {metric} {participle} on {service} is the cause",
    "what does a {participle} {metric} tell me about {service}",
)


def _participle(direction: str) -> str:
    return "climbing" if direction == "rise" else "falling"


def _verb(direction: str) -> str:
    return "climb" if direction == "rise" else "fall"


def generate_symptom_questions() -> list[Question]:
    """From (fault, signal, applicable service) triples.

    Answerable because the fault's runbook is what documents the signal, and the
    pairing comes from the catalogue rather than from a judgement about it.
    """
    questions: list[Question] = []
    for pattern in PATTERNS:
        services = [s for s in estate.services() if pattern.applies_to(s.runtime)]
        if not services:
            continue
        for signal in pattern.primary:
            for index, template in enumerate(_SYMPTOM_TEMPLATES):
                service = services[index % len(services)]
                text = template.format(
                    metric=signal.metric,
                    participle=_participle(signal.direction),
                    verb=_verb(signal.direction),
                    service=service.name,
                )
                questions.append(
                    Question(
                        id=f"q-sym-{pattern.id}-{signal.metric}-{index}",
                        text=text,
                        label=Label.ANSWERABLE,
                        mechanism=Mechanism.SYMPTOM,
                        gold_document_id=pattern.runbook_id,
                        group=pattern.runbook_id,
                    )
                )
    return questions


# ── Answerable: section questions from runbook headings ────────────────────

_SECTION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "When this applies": (
        "when does {name} apply",
        "how do I know I am looking at {name}",
    ),
    "What is happening": (
        "what is actually happening during {name}",
        "explain the mechanism behind {name}",
    ),
    "Diagnosis": (
        "how do I diagnose {name}",
        "what should I check to confirm {name}",
    ),
    "Remediation": (
        "how do I fix {name}",
        "what is the remediation for {name}",
    ),
    "Escalation": (
        "when should I escalate {name}",
        "who do I page for {name}",
    ),
    "Common misdiagnosis": (
        "what is {name} commonly confused with",
        "what else looks like {name}",
    ),
    "Prevention": ("how do I prevent {name}",),
    "Procedure": ("what is the procedure for {name}",),
    "Root cause": ("what was the root cause of {title}",),
    "Timeline": ("what happened during {title}",),
    "Corrective actions": ("what corrective actions followed {title}",),
    "Impact": ("what was the impact of {title}",),
}


def generate_section_questions(documents: list[Document], chunks: list[Chunk]) -> list[Question]:
    """One or two questions per authored section.

    The heading is the author's own statement of what the section is about, so a
    question derived from it is answered by that section by construction.
    """
    titles = {d.id: d.title for d in documents}
    questions: list[Question] = []

    for chunk in chunks:
        if chunk.heading is None:
            continue
        templates = _SECTION_TEMPLATES.get(chunk.heading)
        if not templates:
            continue
        title = titles.get(chunk.document_id, chunk.document_id)
        # Runbook titles read as "Connection pool exhaustion on orders-db"; the
        # leading clause is the fault name.
        name = title.split(" on ")[0].split(" after ")[0].lower()
        for index, template in enumerate(templates):
            questions.append(
                Question(
                    id=f"q-sec-{chunk.id}-{index}",
                    text=template.format(name=name, title=title.lower()),
                    label=Label.ANSWERABLE,
                    mechanism=Mechanism.SECTION,
                    gold_document_id=chunk.document_id,
                    group=chunk.document_id,
                )
            )
    return questions


# ── Answerable: policy lookups the corpus genuinely states ─────────────────

_POLICY_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("what severity is a tier 0 service being unavailable", "pol-incident-severity"),
    ("what severity is a tier 2 service degrading", "pol-incident-severity"),
    ("how long before a severity 1 escalates to the engineering manager", "pol-incident-severity"),
    ("how long before a severity 1 escalates to the director", "pol-incident-severity"),
    ("does a certificate expiry on a tier 0 listener page out of hours", "pol-incident-severity"),
    ("which team gets paged when the root service is not yet known", "pol-incident-severity"),
    ("does an interesting root cause raise the severity", "pol-incident-severity"),
    ("what is the maximum acceptable freshness lag for tier 1 consumers", "pol-data-freshness"),
    ("what is the maximum acceptable freshness lag for tier 2", "pol-data-freshness"),
    ("what is the freshness commitment for batch consumers", "pol-data-freshness"),
    ("where is freshness lag measured, at the publisher or the consumer", "pol-data-freshness"),
    ("is a freshness breach an incident if nothing is erroring", "pol-data-freshness"),
    ("when must a replay be throttled and announced", "pol-data-freshness"),
    ("what are the deploy windows for tier 0 services", "pol-change-management"),
    ("what is the first response to an incident correlated with a deploy", "pol-change-management"),
    (
        "do configuration changes carry the same rollback expectation as code",
        "pol-change-management",
    ),
    ("is retroactive approval permitted for an emergency change", "pol-change-management"),
    ("what must every deploy emit", "pol-change-management"),
    (
        "what risk level is a change to a tier 0 connection pool ceiling",
        "pol-change-risk-classification",
    ),
    (
        "what risk level is an application deploy on the checkout path",
        "pol-change-risk-classification",
    ),
    ("what risk level is a documentation change", "pol-change-risk-classification"),
    ("when does a change escalate a risk level automatically", "pol-change-risk-classification"),
    ("what evidence must a high risk change proposal state", "pol-change-risk-classification"),
    ("is change risk classified on how confident the author is", "pol-change-risk-classification"),
)


def generate_policy_questions() -> list[Question]:
    return [
        Question(
            id=f"q-pol-{index:03d}",
            text=text,
            label=Label.ANSWERABLE,
            mechanism=Mechanism.POLICY,
            gold_document_id=document_id,
            group=document_id,
        )
        for index, (text, document_id) in enumerate(_POLICY_QUESTIONS)
    ]


# ── Unanswerable: topics GAPS.md records as absent, verified ───────────────

#: Each entry is (question, the terms whose ABSENCE makes it unanswerable).
#: The terms are searched for in the corpus; if a chunk contains them all, the
#: example is rejected rather than shipped with a label that is no longer true.
_GAP_QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("the disk is full on the host, what should I do", ("disk", "full")),
    ("how do I free disk space on a node", ("disk", "space")),
    ("how do we handle a dns resolution failure", ("dns",)),
    ("what is the dns failover configuration", ("dns",)),
    ("what is the disaster recovery procedure", ("disaster", "recovery")),
    ("how do we fail over to another region", ("fail over",)),
    ("what is the data retention obligation", ("retention", "obligation")),
    ("how long is customer data kept before deletion", ("retention", "deletion")),
    ("what are the kubernetes scheduler settings", ("kubernetes",)),
    ("which service mesh do we run", ("mesh",)),
    ("what is the rate limit for external api consumers", ("rate", "limit", "consumers")),
    ("what quota applies to third party api clients", ("api quota",)),
    ("who is on call for edge-gateway overnight", ("rota",)),
    ("what is the on call shift handover process", ("handover",)),
    ("how is on call compensated", ("compensat",)),
    ("what is the security incident response process", ("security incident",)),
    ("how do we report a data breach", ("breach",)),
    ("what feature flag system do we use", ("feature flag",)),
    ("how do we run a progressive delivery experiment", ("progressive",)),
    ("what does a deploy cost", ("deploy cost",)),
    ("who approves the infrastructure budget", ("infrastructure budget",)),
    ("how long are heap dumps retained", ("heap dump", "retained")),
    ("how long is the observation period between regions", ("observation period", "minutes")),
    ("what is the minimum time between regional rollout steps", ("rollout", "minutes")),
    ("what is the checkout availability slo", ("slo",)),
    ("what is the error budget for checkout", ("error budget",)),
)


def _corpus_contains_all(chunks: list[Chunk], terms: tuple[str, ...]) -> bool:
    lowered = [chunk.body.lower() for chunk in chunks]
    return any(all(term in body for term in terms) for body in lowered)


def generate_gap_questions(chunks: list[Chunk]) -> list[Question]:
    """Questions on topics the corpus does not cover.

    Absence is verified here, not asserted. A gap list is a claim about the
    corpus, and one entry in it has already been wrong once: 'who approves an
    emergency change' was listed as unanswerable when the corpus answers it. The
    verification is what keeps that from silently poisoning training labels.
    """
    questions: list[Question] = []
    for index, (text, terms) in enumerate(_GAP_QUESTIONS):
        if _corpus_contains_all(chunks, terms):
            continue  # the corpus grew to cover it; the label is no longer true
        questions.append(
            Question(
                id=f"q-gap-{index:03d}",
                text=text,
                label=Label.UNANSWERABLE,
                mechanism=Mechanism.GAP_TOPIC,
                gold_document_id=None,
                group="__gaps__",
            )
        )
    return questions


# ── Unanswerable: a property documented for one entity, asked of another ───

#: (property phrase, the entity that DOES document it, terms proving it).
_DOCUMENTED_PROPERTIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("connection pool ceiling", "orders-db", ("ceiling", "100")),
    ("maximum acceptable freshness lag", "tier 1 consumers", ("freshness", "300")),
    ("escalation timer", "severity 1", ("30 minutes",)),
    ("idle transaction termination threshold", "orders-db", ("60 seconds",)),
)

#: Entities the corpus never documents the above properties for.
_UNDOCUMENTED_ENTITIES = (
    "sessions-cache",
    "catalog-search",
    "events-bus",
    "edge-gateway",
    "pricing-engine",
    "fraud-scoring",
    "recommendation-service",
    "notification-service",
)


def generate_property_transfer_questions(chunks: list[Chunk]) -> list[Question]:
    """The hard class: full vocabulary overlap, no answer present.

    Asking for the connection pool ceiling on sessions-cache retrieves the
    orders-db passage that states a ceiling of 100, at a high score, because
    every term in the question is there. This is the class that defeated the
    heuristic gate in Sprint 2, and it must be represented in proportion rather
    than by luck.
    """
    questions: list[Question] = []
    index = 0
    for prop, documented_for, proof_terms in _DOCUMENTED_PROPERTIES:
        if not _corpus_contains_all(chunks, proof_terms):
            # The property is not actually documented anywhere, so transferring
            # it proves nothing about the hard class.
            continue
        for entity in _UNDOCUMENTED_ENTITIES:
            if entity in documented_for:
                continue
            if _corpus_contains_all(chunks, (entity.lower(), prop.split()[0].lower())):
                continue  # the corpus does document it for this entity after all
            for template in (
                "what is the {prop} for {entity}",
                "what {prop} is configured on {entity}",
            ):
                questions.append(
                    Question(
                        id=f"q-prop-{index:03d}",
                        text=template.format(prop=prop, entity=entity),
                        label=Label.UNANSWERABLE,
                        mechanism=Mechanism.PROPERTY_TRANSFER,
                        gold_document_id=None,
                        group=f"__prop__{entity}",
                    )
                )
                index += 1
    return questions


def generate_presupposition_questions(chunks: list[Chunk]) -> list[Question]:
    """A fault asked about a service whose runtime cannot exhibit it.

    Connection pool exhaustion is a Postgres fault; catalog-search runs
    OpenSearch. The corpus documents the fault and documents the service and
    never connects them, so the honest response is that it does not say - not a
    confident answer assembled from the two halves.
    """
    questions: list[Question] = []
    index = 0
    for pattern in PATTERNS:
        wrong = [s for s in estate.services() if not pattern.applies_to(s.runtime)]
        if not wrong:
            continue
        signal = pattern.primary[0]
        for service in wrong[:3]:
            if _corpus_contains_all(chunks, (service.name.lower(), signal.metric.lower())):
                continue
            questions.append(
                Question(
                    id=f"q-pre-{index:03d}",
                    text=f"what is the expected {signal.metric} baseline on {service.name}",
                    label=Label.UNANSWERABLE,
                    mechanism=Mechanism.PRESUPPOSITION,
                    gold_document_id=None,
                    group=f"__pre__{pattern.id}",
                )
            )
            index += 1
    return questions


# ── Assembly and splitting ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Dataset:
    train: tuple[Question, ...]
    test: tuple[Question, ...]

    @property
    def all(self) -> tuple[Question, ...]:
        return self.train + self.test

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for question in self.all:
            key = f"{question.label}/{question.mechanism}"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))


def build_questions(
    documents: list[Document] | None = None, chunks: list[Chunk] | None = None
) -> list[Question]:
    documents = documents if documents is not None else load_corpus()
    chunks = chunks if chunks is not None else chunk_corpus(documents)

    questions = [
        *generate_symptom_questions(),
        *generate_section_questions(documents, chunks),
        *generate_policy_questions(),
        *generate_gap_questions(chunks),
        *generate_property_transfer_questions(chunks),
        *generate_presupposition_questions(chunks),
    ]

    # Deduplicate on normalised text: several templates converge on the same
    # phrasing, and a duplicate inflates whichever split it lands in.
    seen: set[tuple[str, ...]] = set()
    unique: list[Question] = []
    for question in sorted(questions, key=lambda q: q.id):
        key = tuple(tokenize(question.text))
        if key in seen:
            continue
        seen.add(key)
        unique.append(question)
    return unique


def split_by_group(
    questions: list[Question], *, test_fraction: float = 0.25, seed: int = 20260820
) -> Dataset:
    """Split on the SOURCE DOCUMENT, never on the question.

    Two questions generated from one chunk share nearly all their retrieval
    features. Splitting per question puts near-duplicates on both sides, and
    every score comes out inflated in a way no metric reveals.
    """
    groups = sorted({q.group for q in questions})
    rng = random.Random(seed)
    rng.shuffle(groups)

    test_size = max(1, round(len(groups) * test_fraction))
    test_groups = set(groups[:test_size])

    train = tuple(q for q in questions if q.group not in test_groups)
    test = tuple(q for q in questions if q.group in test_groups)
    return Dataset(train=train, test=test)


def build_dataset(*, test_fraction: float = 0.25, seed: int = 20260820) -> Dataset:
    return split_by_group(build_questions(), test_fraction=test_fraction, seed=seed)
