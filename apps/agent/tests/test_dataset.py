"""The labelled dataset, and the property its validity rests on.

ADR-0010 says labels are true by construction and never model-generated. That is
a claim about a process, so it is tested as one: the generation path is executed
with the HTTP transport rigged to explode, and any model call would surface as a
failure rather than as a slightly-better-looking score months later.
"""

from __future__ import annotations

import pytest

from meridian_agent.evaluation.dataset import (
    MAX_MECHANISM_SHARE,
    Label,
    Mechanism,
    build_dataset,
    build_questions,
    cap_mechanisms,
    split_by_group,
)
from meridian_agent.retrieval.corpus import chunk_corpus, load_corpus


@pytest.fixture(scope="module")
def questions():
    return build_questions()


@pytest.fixture(scope="module")
def dataset():
    return build_dataset()


class TestLabelsAreTrueByConstruction:
    """ADR-0010."""

    def test_generation_makes_no_network_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def explode(*args: object, **kwargs: object) -> object:
            raise AssertionError(
                "the dataset generator made an HTTP call; labels must be derived, "
                "not obtained from a model (ADR-0010)"
            )

        monkeypatch.setattr(httpx.Client, "send", explode)
        monkeypatch.setattr(httpx.Client, "request", explode)
        assert build_questions()

    def test_generator_does_not_import_the_router(self) -> None:
        """A model call cannot happen from a module that cannot reach one."""
        import inspect

        from meridian_agent.evaluation import dataset

        source = inspect.getsource(dataset)
        for forbidden in ("router", "adapters", "chat", "complete("):
            assert forbidden not in source, f"generator references {forbidden!r}"

    def test_every_answerable_question_names_its_gold_document(self, questions) -> None:
        answerable = [q for q in questions if q.label is Label.ANSWERABLE]
        assert answerable
        assert all(q.gold_document_id for q in answerable)

    def test_every_unanswerable_question_has_no_gold_document(self, questions) -> None:
        """None by definition, not by omission."""
        unanswerable = [q for q in questions if q.label is Label.UNANSWERABLE]
        assert unanswerable
        assert all(q.gold_document_id is None for q in unanswerable)

    def test_gold_documents_exist_in_the_corpus(self, questions) -> None:
        known = {d.id for d in load_corpus()}
        for question in questions:
            if question.gold_document_id is not None:
                assert question.gold_document_id in known, question.gold_document_id

    def test_gap_topics_are_verified_absent_not_assumed(self) -> None:
        """A gap list is a claim about the corpus, and one entry was wrong once.

        If a topic marked absent is in fact present, the generator must drop the
        example rather than ship a label that is no longer true.
        """
        from meridian_agent.evaluation.dataset import _GAP_QUESTIONS, generate_gap_questions

        chunks = chunk_corpus(load_corpus())
        produced = {q.text for q in generate_gap_questions(chunks)}
        bodies = [c.body.lower() for c in chunks]

        for text, terms in _GAP_QUESTIONS:
            covered = any(all(term in body for term in terms) for body in bodies)
            if covered:
                assert text not in produced, (
                    f"{text!r} is labelled unanswerable but the corpus covers {terms}"
                )


class TestComposition:
    def test_dataset_is_large_enough_to_fit_a_model(self, questions) -> None:
        assert len(questions) >= 500, f"only {len(questions)} examples"

    def test_classes_are_roughly_balanced(self, questions) -> None:
        answerable = sum(q.label is Label.ANSWERABLE for q in questions)
        share = answerable / len(questions)
        assert 0.40 <= share <= 0.60, f"answerable share is {share:.0%}"

    def test_no_mechanism_dominates(self, questions) -> None:
        """Property transfer generates combinatorially and reached 52% unchecked.

        A classifier fed that learns to recognise one template's phrasing and
        scores well for doing it.
        """
        counts: dict[str, int] = {}
        for question in questions:
            counts[str(question.mechanism)] = counts.get(str(question.mechanism), 0) + 1
        for mechanism, count in counts.items():
            share = count / len(questions)
            assert share <= MAX_MECHANISM_SHARE + 0.001, f"{mechanism} is {share:.1%}"

    def test_every_mechanism_is_represented(self, questions) -> None:
        assert {q.mechanism for q in questions} == set(Mechanism)

    def test_question_ids_are_unique(self, questions) -> None:
        assert len({q.id for q in questions}) == len(questions)

    def test_no_duplicate_question_text(self, questions) -> None:
        from meridian_agent.retrieval.tokenize import tokenize

        keys = [tuple(tokenize(q.text)) for q in questions]
        assert len(set(keys)) == len(keys)

    def test_generation_is_deterministic(self) -> None:
        assert [q.id for q in build_questions()] == [q.id for q in build_questions()]


class TestCapping:
    def test_capping_reaches_a_fixed_point(self) -> None:
        """One pass is not enough: the cap is a fraction of the total and
        capping reduces the total."""
        capped = build_questions()
        recapped = cap_mechanisms(list(capped), MAX_MECHANISM_SHARE)
        assert len(recapped) == len(capped), "another pass still removed examples"

    def test_capping_preserves_group_diversity(self, questions) -> None:
        """Round-robin, not truncation. Truncating would drop whole entities,
        and the entity is what makes a property-transfer example hard."""
        transfers = [q for q in questions if q.mechanism is Mechanism.PROPERTY_TRANSFER]
        assert len({q.group for q in transfers}) >= 10


class TestSplitting:
    def test_no_group_appears_in_both_splits(self, dataset) -> None:
        """Two questions from one chunk share nearly all their retrieval
        features. Splitting per question inflates every score invisibly."""
        assert not ({q.group for q in dataset.train} & {q.group for q in dataset.test})

    def test_both_splits_contain_both_classes(self, dataset) -> None:
        for split in (dataset.train, dataset.test):
            labels = {q.label for q in split}
            assert labels == {Label.ANSWERABLE, Label.UNANSWERABLE}

    def test_split_is_reproducible_from_its_seed(self, questions) -> None:
        first = split_by_group(list(questions), seed=7)
        second = split_by_group(list(questions), seed=7)
        assert [q.id for q in first.test] == [q.id for q in second.test]

    def test_a_different_seed_produces_a_different_split(self, questions) -> None:
        a = split_by_group(list(questions), seed=1)
        b = split_by_group(list(questions), seed=2)
        assert [q.id for q in a.test] != [q.id for q in b.test]

    def test_splits_partition_the_dataset(self, dataset, questions) -> None:
        assert len(dataset.train) + len(dataset.test) == len(questions)
        assert not ({q.id for q in dataset.train} & {q.id for q in dataset.test})
