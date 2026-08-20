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

from sandscope_agent.retrieval.corpus import Chunk, Document, chunk_corpus, load_corpus
from sandscope_agent.retrieval.tokenize import tokenize
from sandscope_agent.seed import estate
from sandscope_agent.seed.faults import PATTERNS


class Label(StrEnum):
    ANSWERABLE = "answerable"
    UNANSWERABLE = "unanswerable"


class Mechanism(StrEnum):
    """How the example was built. This is the audit trail for its label."""

    SYMPTOM = "symptom_from_fault_signal"
    SECTION = "section_from_runbook_heading"
    HEADING = "question_from_any_section_heading"
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
    #: The exact chunk the answer lives in, where construction determines it.
    #: Known for section-derived questions, which are generated FROM one chunk.
    #: Symptom and policy questions are answered by a document rather than by a
    #: single identifiable passage, so this stays None rather than being guessed.
    #:
    #: This exists because measuring at document level hid the real gap:
    #: retrieval puts the gold DOCUMENT first 98.3% of the time and the gold
    #: CHUNK first 21.1% of the time, and a citation points at a chunk.
    gold_chunk_id: str | None = None


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
                    gold_chunk_id=chunk.id,
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


_WH_WORDS = ("why", "what", "when", "how", "who", "where", "which")


def _heading_question(heading: str, title: str) -> list[str]:
    """Turn a section heading into questions it answers by construction.

    The heading is the author's own statement of what the section is about, so
    a question derived from it is answered by that section and by no other -
    which is exactly the ground truth a chunk-level metric needs.
    """
    lowered = heading.strip().lower()
    if lowered.startswith(_WH_WORDS):
        return [lowered, f"{lowered}, for {title.lower()}"]
    plural = lowered.split()[-1].endswith("s") and not lowered.endswith("ss")
    verb = "are" if plural else "is"
    return [f"what {verb} the {lowered}", f"explain the {lowered} for {title.lower()}"]


def generate_heading_questions(documents: list[Document], chunks: list[Chunk]) -> list[Question]:
    """One or two questions per headed chunk, covering the whole corpus.

    `generate_section_questions` only covers headings that appear in the
    template table, which reached 53 of 87 chunks. That left the chunk-level
    evaluation with 19 held-out examples - a smoke test rather than a result by
    this project's own standard. This covers every chunk that has a heading.
    """
    titles = {d.id: d.title for d in documents}
    questions: list[Question] = []
    for chunk in chunks:
        if chunk.heading is None:
            continue
        title = titles.get(chunk.document_id, chunk.document_id)
        for index, text in enumerate(_heading_question(chunk.heading, title)):
            questions.append(
                Question(
                    id=f"q-head-{chunk.id}-{index}",
                    text=text,
                    label=Label.ANSWERABLE,
                    mechanism=Mechanism.HEADING,
                    gold_document_id=chunk.document_id,
                    group=chunk.document_id,
                    gold_chunk_id=chunk.id,
                )
            )
    return questions


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
    ("consumer lag paging threshold", "events-bus", ("1,000,000",)),
    ("hit ratio recovery target", "sessions-cache", ("0.70",)),
    ("shard imbalance threshold", "catalog-search", ("2.0",)),
    ("certificate expiry alert threshold", "the edge listener", ("21",)),
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
    "identity-service",
    "checkout-api",
    "catalog-api",
    "inventory-service",
    "order-orchestrator",
    "search-indexer",
    "config-service",
    "analytics-etl",
    "reporting-batch",
    "payments-gateway",
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
                "what value is set as the {prop} on {entity}",
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
        for service in wrong[:6]:
            if _corpus_contains_all(chunks, (service.name.lower(), signal.metric.lower())):
                continue
            for template in (
                "what is the expected {metric} baseline on {service}",
                "what threshold is set for {metric} on {service}",
            ):
                questions.append(
                    Question(
                        id=f"q-pre-{index:03d}",
                        text=template.format(metric=signal.metric, service=service.name),
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


#: No single construction mechanism may exceed this share of the dataset.
#: Property transfer generates combinatorially - properties multiplied by
#: entities multiplied by templates - and reached 52% of all examples on its
#: own. A classifier trained on that learns to recognise one template's
#: phrasing rather than answerability, and reports a high score for doing so.
MAX_MECHANISM_SHARE = 0.30


def _cap_by_mechanism(questions: list[Question], max_share: float) -> list[Question]:
    """Subsample over-represented mechanisms, round-robin across their groups.

    Round-robin rather than truncation: taking the first N would drop entire
    entities, and the entity is what makes a property-transfer example hard.
    Deterministic, because the dataset must be reproducible.
    """
    by_mechanism: dict[str, list[Question]] = {}
    for question in questions:
        by_mechanism.setdefault(str(question.mechanism), []).append(question)

    cap = max(1, int(len(questions) * max_share))

    kept: list[Question] = []
    for mechanism in sorted(by_mechanism):
        members = by_mechanism[mechanism]
        if len(members) <= cap:
            kept.extend(members)
            continue

        by_group: dict[str, list[Question]] = {}
        for question in sorted(members, key=lambda q: q.id):
            by_group.setdefault(question.group, []).append(question)

        selected: list[Question] = []
        groups = sorted(by_group)
        index = 0
        while len(selected) < cap:
            progressed = False
            for group in groups:
                bucket = by_group[group]
                if index < len(bucket):
                    selected.append(bucket[index])
                    progressed = True
                    if len(selected) >= cap:
                        break
            if not progressed:
                break
            index += 1
        kept.extend(selected)

    return sorted(kept, key=lambda q: q.id)


def cap_mechanisms(questions: list[Question], max_share: float) -> list[Question]:
    """Apply the share cap to a fixed point.

    One pass is not enough and the reason is easy to miss: the cap is a fraction
    of the total, and capping reduces the total. A single pass capped property
    transfer at 30% of 785 and left it at 38.6% of the resulting 609. Iterating
    converges - each pass lowers the ceiling as the total falls - and it stops
    when nothing changes rather than after a guessed number of rounds.
    """
    current = questions
    for _ in range(20):
        capped = _cap_by_mechanism(current, max_share)
        if len(capped) == len(current):
            return capped
        current = capped
    return current


def build_questions(
    documents: list[Document] | None = None, chunks: list[Chunk] | None = None
) -> list[Question]:
    documents = documents if documents is not None else load_corpus()
    chunks = chunks if chunks is not None else chunk_corpus(documents)

    questions = [
        *generate_symptom_questions(),
        *generate_section_questions(documents, chunks),
        *generate_heading_questions(documents, chunks),
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
    return cap_mechanisms(unique, MAX_MECHANISM_SHARE)


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
