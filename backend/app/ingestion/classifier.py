from __future__ import annotations

import re
from typing import Any

from app.ingestion.sources.base import DiscoveredItem
from app.models.resource import (
    AcademicLevel,
    Difficulty,
    ResourceClassification,
    ResourceTaxonomy,
)
from app.repositories.taxonomy import TaxonomyRepository

_STOPWORDS = {
    "and", "the", "of", "for", "with", "in", "on", "to", "a", "an", "using",
    "based", "via", "from", "by", "towards", "study", "introduction",
}

_SYNONYMS: dict[str, list[str]] = {
    "artificial intelligence": ["ai", "machine learning", "ml", "neural network",
                                 "deep learning", "llm", "large language model"],
    "operating systems": ["os", "process scheduling", "kernel", "concurrency", "deadlock"],
    "database management": ["dbms", "sql", "query processing", "transaction", "nosql",
                             "database system"],
    "computer networks": ["networking", "tcp", "routing", "protocol", "dns"],
    "data structures": ["algorithm", "graph algorithm", "tree", "sorting", "hashing"],
    "software engineering": ["agile", "devops", "testing", "requirements engineering"],
    "cyber security": ["cybersecurity", "intrusion detection", "malware", "encryption",
                        "vulnerability", "penetration testing", "infosec"],
    "machine learning": ["supervised learning", "regression", "classification",
                          "clustering", "reinforcement learning"],
    "electronics": ["circuit", "signal", "vlsi", "microcontroller", "embedded"],
    "power systems": ["power grid", "transformer", "load flow"],
    "thermodynamics": ["heat transfer", "entropy", "thermal"],
    "structural analysis": ["finite element", "beam", "concrete design"],
    "biotechnology": ["biotech", "gene", "crispr", "fermentation", "bioinformatics"],
    "linear algebra": ["matrix", "eigenvalue", "vector space"],
    "calculus": ["derivative", "integral", "differential equation"],
    "quantum mechanics": ["quantum physics", "wave function"],
    "organic chemistry": ["reaction mechanism", "synthesis", "alkane", "benzene"],
}

_BEGINNER_RE = re.compile(
    r"\b(introduction|introductory|fundamental|beginner|basics?|primer|first course|"
    r"undergraduate|essential)\b", re.I)
_ADVANCED_RE = re.compile(
    r"\b(advanced|graduate|research|novel|state.of.the.art|expert|deep dive)\b", re.I)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())


class RuleClassifier:
    """Deterministic classification: taxonomy keyword voting over the item's
    title/keywords/description. Admin corrections always win over this."""

    def __init__(self, taxonomy: TaxonomyRepository) -> None:
        self._taxonomy = taxonomy
        self._subjects: list[dict[str, Any]] = []
        self._topics: list[dict[str, Any]] = []
        self._departments: dict[str, str] = {}
        self._loaded = False

    async def load(self) -> None:
        departments = await self._taxonomy.list_departments(active_only=True)
        self._departments = {d.code: d.name for d in departments}
        subjects = await self._taxonomy.list_subjects()
        self._subjects = [{"code": s.code, "name": s.name, "dept": s.department_code}
                          for s in subjects]
        topics = await self._taxonomy.list_topics()
        self._topics = [{"code": t.code, "name": t.name, "subject": t.subject_code}
                        for t in topics]
        self._loaded = True

    def classify(self, item: DiscoveredItem) -> tuple[ResourceTaxonomy, ResourceClassification, list[str]]:
        if not self._loaded:
            raise RuntimeError("Classifier not loaded — call load() first")
        haystack = _norm(
            " ".join([item.title, " ".join(item.keywords), (item.description or "")[:2000]])
        )
        subject_votes: dict[str, int] = {}
        topic_codes: set[str] = set()
        matched_keywords: list[str] = []
        for subject in self._subjects:
            score = self._phrase_score(haystack, subject["name"])
            for synonym in _SYNONYMS.get(subject["name"].lower(), []):
                score += self._phrase_score(haystack, synonym)
            if score > 0:
                subject_votes[subject["code"]] = subject_votes.get(subject["code"], 0) + score
                matched_keywords.append(subject["name"])
        for topic in self._topics:
            if self._phrase_score(haystack, topic["name"]) > 0:
                topic_codes.add(topic["code"])
                matched_keywords.append(topic["name"])

        ranked_subjects = sorted(subject_votes.items(), key=lambda kv: kv[1], reverse=True)
        chosen_subjects = [code for code, _ in ranked_subjects[:2]]
        # Topics only from chosen subjects keep the graph coherent.
        if chosen_subjects:
            subject_set = set(chosen_subjects)
            topic_codes = {t for t in topic_codes
                           if any(tp["code"] == t and tp["subject"] in subject_set
                                  for tp in self._topics)}
        department_code = None
        if chosen_subjects:
            subject_map = {s["code"]: s for s in self._subjects}
            department_code = subject_map[chosen_subjects[0]]["dept"]

        difficulty = Difficulty.INTERMEDIATE
        if _BEGINNER_RE.search(haystack):
            difficulty = Difficulty.BEGINNER
        elif _ADVANCED_RE.search(haystack):
            difficulty = Difficulty.ADVANCED

        is_research = item.type.value in ("research_paper", "journal_article", "thesis",
                                          "dissertation")
        level = (AcademicLevel.RESEARCH if is_research else
                 AcademicLevel.INTRODUCTORY if difficulty == Difficulty.BEGINNER else
                 AcademicLevel.CORE if difficulty == Difficulty.INTERMEDIATE else
                 AcademicLevel.ADVANCED)

        confidence = min(0.95, 0.25 + 0.15 * len(chosen_subjects) + 0.05 * len(topic_codes))
        taxonomy = ResourceTaxonomy(
            department_code=department_code,
            subject_codes=chosen_subjects,
            topic_codes=sorted(topic_codes)[:4],
        )
        classification = ResourceClassification(
            method="rules",
            confidence=round(confidence, 2),
            academic_level=level,
            difficulty=difficulty,
        )
        keywords = sorted(set(matched_keywords) | set(item.keywords))[:16]
        return taxonomy, classification, keywords

    def _phrase_score(self, haystack: str, phrase: str) -> int:
        words = [w for w in _norm(phrase).split() if w not in _STOPWORDS and len(w) > 2]
        if not words:
            return 0
        hits = sum(1 for w in words if f" {w} " in f" {haystack} ")
        if hits == len(words):
            return 2 + len(words)
        return 1 if hits >= max(1, len(words) - 1) else 0
