from __future__ import annotations

import math
import re
import time
from typing import Any

from app.ai.provider import AIProvider
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.resource import Difficulty, ResourceType
from app.models.user import User
from app.repositories.analytics import AnalyticsRepository
from app.repositories.cache import CacheRepository
from app.repositories.resources import ResourceRepository
from app.repositories.taxonomy import TaxonomyRepository
from app.schemas.search import SearchFilters, SearchResponse

logger = get_logger(__name__)

CANDIDATE_LIMIT = 400
SEMANTIC_CANDIDATE_LIMIT = 100
CACHE_TTL_S = 120

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

_TYPE_HINTS: list[tuple[re.Pattern[str], list[ResourceType]]] = [
    (re.compile(r"question paper|past paper|exam paper", re.I), [ResourceType.QUESTION_PAPER]),
    (re.compile(r"research paper|\bpapers?\b|arxiv", re.I), [ResourceType.RESEARCH_PAPER]),
    (re.compile(r"journal", re.I), [ResourceType.JOURNAL, ResourceType.JOURNAL_ARTICLE]),
    (re.compile(r"thesis|dissertation", re.I), [ResourceType.THESIS, ResourceType.DISSERTATION]),
    (re.compile(r"\bvideos?\b|youtube|playlist", re.I), [ResourceType.VIDEO, ResourceType.PLAYLIST]),
    (re.compile(r"\bbooks?\b|ebooks?|textbook", re.I), [ResourceType.BOOK, ResourceType.EBOOK]),
    (re.compile(r"lecture notes|study notes|notes\b", re.I), [ResourceType.LECTURE_NOTES, ResourceType.STUDY_MATERIAL]),
    (re.compile(r"case stud", re.I), [ResourceType.CASE_STUDY]),
]

_DIFFICULTY_HINTS: list[tuple[re.Pattern[str], Difficulty]] = [
    (re.compile(r"beginner|introductory|easy| starter|first course", re.I), Difficulty.BEGINNER),
    (re.compile(r"advanced|expert|deep dive", re.I), Difficulty.ADVANCED),
]

_POPULARITY_HINT_RE = re.compile(r"\b(best|top|popular|trending|recommended)\b", re.I)
_RECENT_HINT_RE = re.compile(r"\b(recent|latest|new)\b", re.I)


class SearchService:
    """Unified academic search: keyword ($text with field weights) + metadata
    filters + popularity/rating/recency ranking + optional semantic re-rank."""

    def __init__(
        self,
        settings: Settings,
        resources: ResourceRepository,
        taxonomy: TaxonomyRepository,
        ai_provider: AIProvider,
        analytics: AnalyticsRepository,
        cache: CacheRepository,
    ) -> None:
        self._settings = settings
        self._resources = resources
        self._taxonomy = taxonomy
        self._ai = ai_provider
        self._analytics = analytics
        self._cache = cache

    async def search(
        self, filters: SearchFilters, *, page: int, page_size: int,
        semantic: bool = True, user: User | None = None,
        hydrate=None,
    ) -> SearchResponse:
        started = time.monotonic()
        interpreted: dict[str, Any] = {}
        effective = filters
        if filters.query.strip():
            effective, interpreted = await self.interpret(filters)
        cache_key = f"search:v1:{effective.cache_key()}|p{page}|n{page_size}|s{int(semantic)}"
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            response = SearchResponse.model_validate(cached)
            response.cached = True
            return response

        query_text = effective.query.strip()
        semantic_used = False
        if query_text:
            candidates = await self._resources.text_candidates(effective, limit=CANDIDATE_LIMIT)
            pool: list[tuple[Any, float]] = list(candidates)
            ranked = self._rank(pool, popularity_boost=bool(_POPULARITY_HINT_RE.search(query_text)))
            if semantic and self._ai.is_configured and self._ai.embeddings_available:
                try:
                    ranked = await self._semantic_rerank(query_text, ranked)
                    semantic_used = True
                except Exception as exc:  # noqa: BLE001 - semantic layer is optional
                    logger.warning("semantic_rerank_failed", reason=str(exc)[:200])
            total = len(ranked)
            start = (page - 1) * page_size
            page_items = ranked[start:start + page_size]
        else:
            resources, total = await self._resources.query(
                effective, skip=(page - 1) * page_size, limit=page_size,
                sort=[("stats.views", -1), ("created_at", -1)],
            )
            page_items = [(r, 0.0) for r in resources]

        if hydrate:
            import inspect
            h_res = hydrate([r for r, _ in page_items])
            summaries = await h_res if inspect.isawaitable(h_res) else h_res
        else:
            summaries = [
                {"resource_id": r.resource_id, "title": r.title} for r, _ in page_items
            ]
        response = SearchResponse(
            results=summaries,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)) if total else 0,
            interpreted=interpreted,
            semantic_used=semantic_used,
            cached=False,
            took_ms=round((time.monotonic() - started) * 1000.0, 1),
        )
        if total:
            await self._cache.set_json(cache_key, response.model_dump(mode="json"),
                                       ttl_seconds=CACHE_TTL_S)
        try:
            await self._analytics.record(
                event_type="search",
                user_id=user.user_id if user else None,
                department_code=effective.department,
                subject_code=effective.subject,
                search_query=effective.query[:512] or None,
                result_count=total,
            )
        except Exception as exc:  # noqa: BLE001 - analytics must never break search
            logger.warning("search_analytics_failed", reason=str(exc)[:200])
        return response

    # ------------------------------------------------------- interpretation

    async def interpret(self, filters: SearchFilters) -> tuple[SearchFilters, dict[str, Any]]:
        """Natural-language query understanding without an LLM: deterministic
        extraction of type/year/difficulty/access/department/subject hints."""
        text = filters.query
        notes: list[dict[str, str]] = []
        effective = filters.model_copy()

        years = [int(y) for y in _YEAR_RE.findall(text)]
        if years and filters.year_from is None and filters.year_to is None:
            effective.year_to = years[-1]
            effective.year_from = years[0]
            notes.append({"kind": "year", "detail": f"{effective.year_from}-{effective.year_to}"})
        elif _RECENT_HINT_RE.search(text) and filters.year_from is None:
            from datetime import date
            effective.year_from = date.today().year - 3
            notes.append({"kind": "year", "detail": f"since {effective.year_from} (recent)"})

        if not effective.types:
            for pattern, types in _TYPE_HINTS:
                if pattern.search(text):
                    effective.types = types
                    notes.append({"kind": "type", "detail": ", ".join(t.value for t in types)})
                    break

        if effective.difficulty is None:
            for pattern, difficulty in _DIFFICULTY_HINTS:
                if pattern.search(text):
                    effective.difficulty = difficulty
                    notes.append({"kind": "difficulty", "detail": difficulty.value})
                    break

        if effective.access is None and re.search(r"\bfree\b", text, re.I):
            effective.access = None  # "free" is common in queries; don't over-filter
            notes.append({"kind": "note", "detail": "'free' treated as keyword, not a filter"})

        maps = await self._taxonomy.name_maps()
        department_names: dict[str, str] = maps.get("departments", {})
        subject_names: dict[str, str] = maps.get("subjects", {})
        lowered = " " + re.sub(r"[^a-z0-9& ]", " ", text.lower()) + " "
        if effective.department is None:
            for code, name in department_names.items():
                tokens = [t for t in name.lower().split() if len(t) > 3 and t not in ("and", "&")]
                if tokens and all(f" {t} " in lowered or f" {t}s " in lowered for t in tokens):
                    effective.department = code
                    notes.append({"kind": "department", "detail": name})
                    break
        if effective.subject is None and effective.department:
            for code, name in subject_names.items():
                if len(name) > 4 and f" {name.lower()} " in lowered:
                    effective.subject = code
                    notes.append({"kind": "subject", "detail": name})
                    break

        return effective, {
            "original_query": text,
            "adjusted": notes,
            "keywords": self._keyword_terms(effective.query),
            "popularity_boost": bool(_POPULARITY_HINT_RE.search(text)),
        }

    def _keyword_terms(self, query: str) -> list[str]:
        stop = {
            "find", "best", "need", "want", "learn", "learning", "about", "from",
            "papers", "paper", "resources", "resource", "give", "show", "some",
            "the", "for", "with", "and", "recent", "latest", "new", "good",
            "videos", "video", "books", "book", "question",
        }
        terms = [
            t for t in re.findall(r"[a-zA-Z0-9+#.-]{2,}", query.lower())
            if t not in stop
        ]
        return terms[:12]

    # --------------------------------------------------------------- ranking

    def _rank(self, pool: list[tuple[Any, float]], *, popularity_boost: bool) -> list[tuple[Any, float]]:
        if not pool:
            return []
        max_text = max((score for _, score in pool), default=1.0) or 1.0
        max_views = max(
            (r.stats.views + 2 * r.stats.reads + r.stats.downloads for r, _ in pool),
            default=1,
        ) or 1
        w_text = 0.55 if not popularity_boost else 0.35
        w_pop = 0.45 if popularity_boost else 0.25
        w_rating = 0.15
        w_recency = 0.05
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        scored: list[tuple[float, Any]] = []
        for resource, text_score in pool:
            text_norm = text_score / max_text
            views = resource.stats.views + 2 * resource.stats.reads + resource.stats.downloads
            popularity = math.log1p(views) / math.log1p(max_views)
            rating = (resource.stats.rating_average or 0.0) / 5.0
            age_days = max(0.0, (now - resource.created_at).total_seconds() / 86400.0) \
                if resource.created_at else 9999.0
            recency = 1.0 / (1.0 + age_days / 365.0)
            composite = (
                w_text * text_norm
                + w_pop * popularity
                + w_rating * rating
                + w_recency * recency
            )
            scored.append((composite, resource))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [(resource, score) for score, resource in scored]

    async def _semantic_rerank(
        self, query: str, ranked: list[tuple[Any, float]]
    ) -> list[tuple[Any, float]]:
        top = ranked[:SEMANTIC_CANDIDATE_LIMIT]
        texts = []
        for resource, _ in top:
            parts = [resource.title]
            if resource.description:
                parts.append(resource.description[:400])
            if resource.keywords:
                parts.append(" ".join(resource.keywords[:12]))
            texts.append(" — ".join(parts))
        vectors = await self._ai.embed(texts)
        query_vectors = await self._ai.embed([query])
        if not query_vectors or len(vectors) != len(top):
            return ranked
        query_vector = query_vectors[0]

        def _cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb) if na and nb else 0.0

        sem_scores = [_cosine(query_vector, v) for v in vectors]
        max_sem = max(sem_scores) or 1.0
        blended: list[tuple[float, Any]] = []
        for (resource, base_score), sem in zip(top, sem_scores):
            blended.append((0.6 * base_score + 0.4 * (sem / max_sem), resource))
        blended.sort(key=lambda pair: pair[0], reverse=True)
        reranked = [(resource, score) for score, resource in blended]
        return reranked + ranked[SEMANTIC_CANDIDATE_LIMIT:]

    # ------------------------------------------------------------ suggestions

    async def suggestions(self) -> list[dict[str, str]]:
        return [
            {"text": "Find beginner resources for operating systems", "kind": "example"},
            {"text": "Research papers about AI in healthcare", "kind": "example"},
            {"text": "DBMS question papers from 2024", "kind": "example"},
            {"text": "Best videos to learn graph algorithms", "kind": "example"},
            {"text": "What should I study before learning neural networks?", "kind": "conversational"},
        ]
