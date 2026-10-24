from __future__ import annotations

import re

from app.seed.taxonomy_data import build_departments, build_subjects, build_topics


class TestReferentialIntegrity:
    def test_subject_codes_unique(self):
        subjects = build_subjects()
        codes = [s.code for s in subjects]
        assert len(codes) == len(set(codes))

    def test_topic_codes_unique(self):
        topics = build_topics()
        codes = [t.code for t in topics]
        assert len(codes) == len(set(codes))

    def test_every_subject_references_a_department(self):
        departments = {d.code for d in build_departments()}
        for subject in build_subjects():
            assert subject.department_code in departments, subject.code

    def test_every_topic_references_a_subject(self):
        subjects = {s.code for s in build_subjects()}
        for topic in build_topics():
            assert topic.subject_code in subjects, topic.code

    def test_subject_code_format_is_dept_slug(self):
        for subject in build_subjects():
            assert subject.code.startswith(f"{subject.department_code}-")
            assert re.fullmatch(r"[A-Z0-9\-]+", subject.code)

    def test_topic_code_format_is_subject_slug(self):
        for topic in build_topics():
            assert topic.code.startswith(f"{topic.subject_code}-")
            assert re.fullmatch(r"[A-Z0-9\-]+", topic.code)


class TestDataQuality:
    def test_department_codes_unique(self):
        codes = [d.code for d in build_departments()]
        assert len(codes) == len(set(codes))

    def test_names_present_and_nonempty(self):
        for entity in (*build_departments(), *build_subjects(), *build_topics()):
            assert entity.name and entity.name.strip() == entity.name

    def test_semester_within_valid_range(self):
        for subject in build_subjects():
            assert subject.semester is None or 1 <= subject.semester <= 10

    def test_every_subject_has_topics(self):
        topic_counts: dict[str, int] = {}
        for topic in build_topics():
            topic_counts[topic.subject_code] = topic_counts.get(topic.subject_code, 0) + 1
        for subject in build_subjects():
            assert topic_counts.get(subject.code, 0) >= 3, subject.code
