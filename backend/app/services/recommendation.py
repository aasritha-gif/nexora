from __future__ import annotations

from typing import Any

from app.core.errors import DatabaseUnavailableError
from app.core.logging import get_logger
from app.models.engagement import ReadingHistoryEntry
from app.models.resource import Resource
from app.models.user import User
from app.repositories.analytics import AnalyticsRepository
from app.repositories.cache import CacheRepository
from app.repositories.engagement import BookmarkRepository, ReadingHistoryRepository
from app.repositories.graph import GraphRepository
from app.repositories.resources import ResourceRepository
from app.repositories.users import UserRepository

logger = get_logger(__name__)

_RECOMMENDED_LIMIT = 12
_FALLBACK_POPULAR_LIMIT = 12


class RecommendationService:
    """Personalization. Neo4j relationships are the primary signal; MongoDB
    subject/popularity queries are the fallback when the graph is unavailable."""

    def __init__(
        self,
        users: UserRepository,
        resources: ResourceRepository,
        history: ReadingHistoryRepository,
        bookmarks: BookmarkRepository,
        graph: GraphRepository,
        analytics: AnalyticsRepository,
        cache: CacheRepository,
    ) -> None:
        self._users = users
        self._resources = resources
        self._history = history
        self._bookmarks = bookmarks
        self._graph = graph
        self._analytics = analytics
        self._cache = cache

    async def for_user(self, user: User) -> dict[str, Any]:
        recent = await self._history.user_history(user.user_id, limit=20)
        in_progress = await self._history.in_progress(user.user_id, limit=6)
        because, because_seeds = await self._because_you_read(user.user_id, recent)
        recommended = await self._recommended(user, recent, because)
        also_explored = await self._students_also_explored(recent)
        continue_sections = await self._continue_learning(in_progress)
        return {
            "recommended": recommended,
            "because_you_read": because,
            "because_you_read_seeds": because_seeds,
            "continue_learning": continue_sections,
            "students_also_explored": also_explored,
            "personalized": bool(recent),
        }

    async def anonymous_feed(self) -> dict[str, Any]:
        trending_ids = await self._safe_trending_ids()
        if trending_ids:
            trending = await self._resources.by_ids_ordered(trending_ids[:_RECOMMENDED_LIMIT])
        else:
            trending = []
        if not trending:
            trending = await self._resources.popular(limit=_FALLBACK_POPULAR_LIMIT)
        return {
            "recommended": trending,
            "because_you_read": [],
            "because_you_read_seeds": [],
            "continue_learning": [],
            "students_also_explored": await self._resources.popular(limit=8),
            "personalized": False,
        }

    # ------------------------------------------------------------- sections

    async def _because_you_read(
        self, user_id: str, recent: list[ReadingHistoryEntry]
    ) -> tuple[list[Resource], list[str]]:
        if not recent:
            return [], []
        seed_ids = [entry.resource_id for entry in recent[:5]]
        try:
            rows = await self._graph.because_you_read(user_id, limit=_RECOMMENDED_LIMIT)
        except DatabaseUnavailableError:
            rows = []
        except Exception as exc:  # noqa: BLE001 - graph failure must not break the feed
            logger.warning("graph_because_you_read_failed", reason=str(exc)[:200])
            rows = []
        resources = await self._resources.by_ids_ordered(
            [row["resource_id"] for row in rows if row.get("resource_id")]
        )
        if resources:
            seeds = await self._resources.get_many(seed_ids[:2])
            return resources, [r.title for r in seeds]
        # Fallback: resources sharing subjects with recent reads.
        subject_codes = await self._subjects_of(seed_ids)
        if subject_codes:
            from app.models.resource import AccessType, Difficulty, ResourceType
            from app.schemas.search import SearchFilters
            fallback_filters = SearchFilters(
                subject=subject_codes[0],
                types=[],
            )
            fallback, _total = await self._resources.query(
                fallback_filters, limit=_RECOMMENDED_LIMIT,
                sort=[("stats.views", -1)],
            )
            return fallback, []
        return [], []

    async def _recommended(
        self, user: User, recent: list[ReadingHistoryEntry],
        because: list[Resource],
    ) -> list[Resource]:
        exclude = {entry.resource_id for entry in recent} | {r.resource_id for r in because}
        department = user.department_code
        candidates = await self._resources.popular(
            limit=_RECOMMENDED_LIMIT * 2, department=department
        )
        if len(candidates) < _RECOMMENDED_LIMIT:
            candidates += await self._resources.popular(limit=_RECOMMENDED_LIMIT * 2)
        seen: list[Resource] = []
        seen_ids: set[str] = set()
        for resource in candidates:
            if resource.resource_id in exclude or resource.resource_id in seen_ids:
                continue
            seen_ids.add(resource.resource_id)
            seen.append(resource)
            if len(seen) >= _RECOMMENDED_LIMIT:
                break
        return seen

    async def _students_also_explored(self, recent: list[ReadingHistoryEntry]) -> list[Resource]:
        if not recent:
            return []
        try:
            rows = await self._graph.students_also_explored(
                recent[0].resource_id, limit=8
            )
        except DatabaseUnavailableError:
            rows = []
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_students_also_explored_failed", reason=str(exc)[:200])
            rows = []
        resources = await self._resources.by_ids_ordered(
            [row["resource_id"] for row in rows if row.get("resource_id")]
        )
        if resources:
            return resources
        return await self._resources.popular(limit=8)

    async def _continue_learning(
        self, in_progress: list[ReadingHistoryEntry]
    ) -> list[dict[str, Any]]:
        if not in_progress:
            return []
        resources = await self._resources.get_many(
            [entry.resource_id for entry in in_progress]
        )
        by_id = {r.resource_id: r for r in resources}
        sections = []
        for entry in in_progress:
            resource = by_id.get(entry.resource_id)
            if resource is None:
                continue
            sections.append({
                "resource": resource,
                "progress_percent": entry.progress.percent,
                "last_chunk": entry.progress.last_chunk,
                "last_viewed_at": entry.last_viewed_at,
            })
        return sections

    # -------------------------------------------------------------- helpers

    async def _subjects_of(self, resource_ids: list[str]) -> list[str]:
        resources = await self._resources.get_many(resource_ids)
        codes: set[str] = set()
        for resource in resources:
            codes.update(resource.taxonomy.subject_codes)
        return sorted(codes)

    async def _safe_trending_ids(self) -> list[str]:
        try:
            rows = await self._analytics.trending_resources(days=14, limit=_RECOMMENDED_LIMIT)
            return [row.get("resource_id") for row in rows if row.get("resource_id")]
        except Exception as exc:  # noqa: BLE001 - analytics is optional for the feed
            logger.warning("trending_lookup_failed", reason=str(exc)[:200])
            return []
