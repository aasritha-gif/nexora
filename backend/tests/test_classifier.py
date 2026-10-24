from __future__ import annotations

import pytest

from app.ingestion.classifier import RuleClassifier, _SYNONYMS
from app.models.resource import (
    AcademicLevel,
    Difficulty,
    ResourceType,
)
from app.models.taxonomy import Department, Subject, Topic
from tests.conftest import make_item


class FakeTaxonomy:
    def __init__(self, departments=(), subjects=(), topics=()):
        self._departments = list(departments)
        self._subjects = list(subjects)
        self._topics = list(topics)

    async def list_departments(self, active_only: bool = True):
        return list(self._departments)

    async def list_subjects(self, department_code: str | None = None):
        return list(self._subjects)

    async def list_topics(self, subject_code: str | None = None):
        return list(self._topics)


def _fixture_classifier() -> RuleClassifier:
    taxonomy = FakeTaxonomy(
        departments=[Department(code="CSE", name="Computer Science & Engineering")],
        subjects=[
            Subject(code="CSE-AI", name="Artificial Intelligence", department_code="CSE"),
            Subject(code="CSE-DSA", name="Data Structures", department_code="CSE"),
        ],
        topics=[
            Topic(code="CSE-AI-SEARCH", name="Search Strategies", subject_code="CSE-AI"),
            Topic(code="CSE-AI-ML", name="Machine Learning", subject_code="CSE-AI"),
            Topic(code="CSE-DSA-TREES", name="Trees", subject_code="CSE-DSA"),
        ],
    )
    classifier = RuleClassifier(taxonomy)
    return classifier


@pytest.fixture
async def classifier():
    c = _fixture_classifier()
    await c.load()
    return c


class TestLoad:
    async def test_classify_before_load_raises(self):
        with pytest.raises(RuntimeError, match="load"):
            _fixture_classifier().classify(make_item())

    async def test_load_pulls_all_three_levels(self):
        c = _fixture_classifier()
        await c.load()
        assert len(c._departments) == 1
        assert len(c._subjects) == 2
        assert len(c._topics) == 3


class TestClassification:
    async def test_ai_paper_classified_into_ai_department(self, classifier):
        item = make_item(
            title="Introduction to Artificial Intelligence and Machine Learning",
            type=ResourceType.STUDY_MATERIAL,
        )
        taxonomy, classification, keywords = classifier.classify(item)
        assert taxonomy.department_code == "CSE"
        assert taxonomy.subject_codes[0] == "CSE-AI"
        assert classification.academic_level == AcademicLevel.INTRODUCTORY
        assert classification.difficulty == Difficulty.BEGINNER
        assert classification.method == "rules"

    async def test_synonym_expansion_matches_subject(self, classifier):
        item = make_item(
            title="Deep neural networks for vision",
            type=ResourceType.RESEARCH_PAPER,
        )
        taxonomy, classification, _ = classifier.classify(item)
        assert "CSE-AI" in taxonomy.subject_codes
        assert classification.academic_level == AcademicLevel.RESEARCH

    async def test_topics_restricted_to_chosen_subjects(self, classifier):
        item = make_item(title="Balanced Trees: a data structures perspective",
                         description=None, keywords=[])
        taxonomy, _, _ = classifier.classify(item)
        assert taxonomy.subject_codes == ["CSE-DSA"]
        assert taxonomy.topic_codes == ["CSE-DSA-TREES"]

    async def test_advanced_signal_detected(self, classifier):
        item = make_item(title="Advanced study of sorting", description=None, keywords=[])
        _, classification, _ = classifier.classify(item)
        assert classification.difficulty == Difficulty.ADVANCED

    async def test_no_match_yields_empty_taxonomy_with_floor_confidence(self, classifier):
        item = make_item(title="Zz unmatchable xyzzy title", description=None, keywords=[])
        taxonomy, classification, _ = classifier.classify(item)
        assert taxonomy.department_code is None
        assert taxonomy.subject_codes == []
        assert classification.confidence == 0.25

    async def test_confidence_is_capped(self, classifier):
        item = make_item(
            title="Artificial intelligence machine learning trees search strategies",
            keywords=["algorithms", "graphs"],
        )
        _, classification, _ = classifier.classify(item)
        assert classification.confidence <= 0.95


class TestSynonymTaxonomyAlignment:
    def test_every_synonym_key_is_a_real_subject_name(self):
        from app.seed.taxonomy_data import build_subjects

        subject_names = {s.name.lower() for s in build_subjects()}
        assert set(_SYNONYMS) <= subject_names
