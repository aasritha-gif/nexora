from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.resources import ResourceRepository
from app.schemas.search import SearchFilters
from app.services.youtube_service import YouTubeService

logger = get_logger(__name__)

_LIBRARY_LIMIT = 6


class DiscoveryService:
    """Read-only discovery surface: pairs external YouTube results with what the
    library already holds on the same topic. Persistence of discovered items is
    the ingestion pipeline's job (IngestionService.run_source("youtube"))."""

    def __init__(self, youtube: YouTubeService, resources: ResourceRepository) -> None:
        self._youtube = youtube
        self._resources = resources

    async def status(self) -> dict[str, Any]:
        youtube_status = await self._youtube.status()
        return {
            "youtube": youtube_status,
            "library_total": await self._resources.count(),
        }

    async def discover(
        self,
        query: str,
        *,
        max_results: int = 12,
        department_code: str | None = None,
        subject_code: str | None = None,
        topic_name: str | None = None,
        subject_name: str | None = None,
    ) -> dict[str, Any]:
        search_query = _build_query(query or " ".join(p for p in (topic_name, subject_name) if p))
        result = await self._youtube.discover(search_query, max_results=max_results)
        return {
            "available": result.available,
            "reason": result.reason,
            "query": result.query,
            "videos": result.videos,
            "playlists": result.playlists,
            "library": await self._library_matches(
                search_query, department_code=department_code, subject_code=subject_code
            ),
            "context": {
                "department_code": department_code,
                "subject_code": subject_code,
                "topic_name": topic_name,
                "subject_name": subject_name,
            },
        }

    async def discover_for_topic(
        self,
        topic_name: str,
        *,
        subject_name: str | None = None,
        department_code: str | None = None,
        subject_code: str | None = None,
        max_results: int = 12,
    ) -> dict[str, Any]:
        return await self.discover(
            "",
            max_results=max_results,
            department_code=department_code,
            subject_code=subject_code,
            topic_name=topic_name,
            subject_name=subject_name,
        )

    async def _library_matches(
        self,
        query: str,
        *,
        department_code: str | None,
        subject_code: str | None,
    ) -> list[dict[str, Any]]:
        if not query:
            return []
        filters = SearchFilters(
            query=query, department=department_code, subject=subject_code, types=[]
        )
        candidates = await self._resources.text_candidates(filters, limit=_LIBRARY_LIMIT * 4)
        if not candidates:
            resources, _ = await self._resources.query(
                filters, limit=_LIBRARY_LIMIT, sort=[("stats.views", -1)]
            )
            candidates = [(resource, 0.0) for resource in resources]
        return [_library_card(resource) for resource, _ in candidates[:_LIBRARY_LIMIT]]


def _build_query(raw: str) -> str:
    return " ".join(part for part in (raw or "").replace("_", " ").split() if part)


def _library_card(resource: Any) -> dict[str, Any]:
    return {
        "resource_id": resource.resource_id,
        "title": resource.title,
        "type": resource.type.value,
        "access": resource.access.value,
        "year": resource.year,
        "rating": resource.stats.rating_average,
        "views": resource.stats.views,
        "youtube_id": resource.youtube.video_id if resource.youtube else None,
        "url": resource.identifiers.url,
    }
