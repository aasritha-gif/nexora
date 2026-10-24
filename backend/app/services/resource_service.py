from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.models.resource import AccessType, Resource
from app.models.user import Role
from app.repositories.analytics import AnalyticsRepository
from app.repositories.cache import CacheRepository
from app.repositories.graph import GraphRepository
from app.repositories.purchases import PurchaseRepository
from app.repositories.resources import ResourceRepository
from app.repositories.taxonomy import TaxonomyRepository
from app.schemas.resource import RelatedResource, ResourceDetail, ResourceSummary, TaxonomyInfo

log = logging.getLogger(__name__)

HOMEPAGE_CACHE_TTL = 120
DETAIL_CACHE_TTL = 60


class ResourceService:
    def __init__(
        self,
        settings: Settings,
        resources: ResourceRepository,
        taxonomy: TaxonomyRepository,
        graph: GraphRepository,
        analytics: AnalyticsRepository,
        cache: CacheRepository,
        purchases: PurchaseRepository,
    ):
        self.settings = settings
        self.resources = resources
        self.taxonomy = taxonomy
        self.graph = graph
        self.analytics = analytics
        self.cache = cache
        self.purchases = purchases

    # ── hydration ───────────────────────────────────────

    def _summary(
        self, resource: Resource, names: dict[str, dict[str, str]]
    ) -> ResourceSummary:
        dept = resource.taxonomy.department_code
        subjects = resource.taxonomy.subject_codes
        topics = resource.taxonomy.topic_codes
        taxonomy = TaxonomyInfo(
            department=dept,
            department_name=names["department"].get(dept) if dept else None,
            subjects=subjects,
            subject_names=[names["subject"].get(s, s) for s in subjects],
            topics=topics,
            topic_names=[names["topic"].get(t, t) for t in topics],
        )
        return ResourceSummary(
            resource_id=resource.resource_id,
            type=resource.type,
            title=resource.title,
            subtitle=resource.subtitle,
            description=_truncate(resource.description, 400),
            authors=resource.authors[:6],
            year=resource.year,
            publisher=resource.publisher,
            access=resource.access,
            premium_price_usd=resource.premium_price_usd,
            taxonomy=taxonomy,
            keywords=resource.keywords[:12],
            rating_average=resource.stats.rating_average,
            rating_count=resource.stats.rating_count,
            views=resource.stats.views,
            reads=resource.stats.reads,
            downloads=resource.stats.downloads,
            bookmarks=resource.stats.bookmarks,
            citation_count=resource.citation_count,
            external_url=resource.identifiers.url,
            source_name=resource.source.name if resource.source else None,
            youtube_thumbnail=(
                f"https://i.ytimg.com/vi/{resource.youtube.video_id}/hqdefault.jpg"
                if resource.youtube else None
            ),
            youtube_duration=resource.youtube.duration_seconds if resource.youtube else None,
            is_seed_data=resource.flags.is_seed_data,
            created_at=resource.created_at,
        )

    def _detail(self, resource: Resource, names: dict[str, dict[str, str]]) -> ResourceDetail:
        summary = self._summary(resource, names)
        ai_caps = {
            "overview": resource.content.text_available or bool(resource.description),
            "reading": resource.content.text_available,
            "chat": resource.content.text_available or bool(resource.description),
        }
        return ResourceDetail(
            **summary.model_dump(),
            language=resource.language,
            classification={
                "method": resource.classification.method,
                "confidence": resource.classification.confidence,
                "academic_level": resource.classification.academic_level,
                "difficulty": resource.classification.difficulty,
                "semester": resource.classification.semester,
            },
            identifiers={
                "doi": resource.identifiers.doi,
                "isbn": resource.identifiers.isbn,
                "arxiv_id": resource.identifiers.arxiv_id,
            },
            source=resource.source.model_dump() if resource.source else None,
            youtube=resource.youtube.model_dump() if resource.youtube else None,
            ai_capabilities=ai_caps,
            updated_at=resource.updated_at,
        )

    async def hydrate_many(
        self, resources: list[Resource], *, detail: bool = False
    ) -> list[ResourceSummary | ResourceDetail]:
        names = await self.taxonomy.name_maps()
        if detail:
            return [self._detail(r, names) for r in resources]
        return [self._summary(r, names) for r in resources]

    # ── detail + activity ───────────────────────────────

    async def get_detail(
        self, resource_id: str, *, user_id: str | None
    ) -> ResourceDetail:
        resource = await self.resources.get(resource_id)
        names = await self.taxonomy.name_maps()
        detail = self._detail(resource, names)

        await self.resources.inc_stat(resource_id, "views")
        if user_id:
            await self._safe(
                self.graph.record_activity,
                user_id=user_id, resource_id=resource_id, relation="VIEWED",
            )
        await self._safe(
            self.analytics.record,
            event_type="view",
            resource_id=resource_id,
            user_id=user_id,
            department_code=resource.taxonomy.department_code,
            subject_code=resource.taxonomy.subject_codes[0]
            if resource.taxonomy.subject_codes else None,
        )
        return detail

    async def related(self, resource_id: str, *, limit: int = 8) -> list[RelatedResource]:
        resource = await self.resources.get(resource_id)
        rows = await self._safe(self.graph.related_resources, resource_id, limit=limit)
        if not rows:
            rows = await self._fallback_related(resource, limit=limit)
        ids = [row["resource_id"] for row in rows]
        found = await self.resources.by_ids_ordered(ids)
        names = await self.taxonomy.name_maps()
        related = []
        for row, res in zip([r for r in rows if r["resource_id"] in
                             {f.resource_id for f in found}], found):
            summary = self._summary(res, names)
            related.append(RelatedResource(
                **summary.model_dump(),
                relation="shares topics",
                score=float(row.get("shared", 0)),
            ))
        return related

    async def _fallback_related(self, resource: Resource, *, limit: int) -> list[dict]:
        """Graph unavailable or resource has no edges: fall back to same-subject
        resources from MongoDB."""
        if not resource.taxonomy.subject_codes:
            return []
        from app.schemas.search import SearchFilters

        filters = SearchFilters(subject=resource.taxonomy.subject_codes[0])
        similar, _ = await self.resources.query(filters, limit=limit + 1)
        return [
            {"resource_id": r.resource_id, "shared": 1}
            for r in similar if r.resource_id != resource.resource_id
        ][:limit]

    # ── homepage feeds ──────────────────────────────────

    async def homepage_feed(self, *, department: str | None = None) -> dict:
        cache_key = f"feed:home:{department or 'all'}"
        cached = await self.cache.get(cache_key)
        if cached:
            import json

            try:
                return json.loads(cached)
            except ValueError:
                pass

        trending_ids = await self._safe_list(self.analytics.trending_resources, limit=10)
        trending = await self.resources.by_ids_ordered(
            [t["resource_id"] for t in trending_ids]
        ) if trending_ids else []
        if not trending:
            trending = await self.resources.popular(limit=10, department=department)

        new_research = await self.resources.recent(
            limit=10,
            types=["research_paper", "journal_article", "thesis", "dissertation"],
            department=department,
        )
        recent = await self.resources.recent(limit=10, department=department)
        videos = await self.resources.recent(limit=10, types=["video", "playlist"],
                                             department=department)

        names = await self.taxonomy.name_maps()
        feed = {
            "trending": [self._summary(r, names).model_dump() for r in trending],
            "new_research": [self._summary(r, names).model_dump() for r in new_research],
            "recently_added": [self._summary(r, names).model_dump() for r in recent],
            "best_videos": [self._summary(r, names).model_dump() for r in videos],
        }
        import json

        await self.cache.set(cache_key, json.dumps(feed), ttl_seconds=HOMEPAGE_CACHE_TTL)
        return feed

    async def trending(self, *, limit: int = 12) -> list[ResourceSummary]:
        rows = await self._safe_list(self.analytics.trending_resources, limit=limit)
        resources = await self.resources.by_ids_ordered([r["resource_id"] for r in rows])
        if not resources:
            resources = await self.resources.popular(limit=limit)
        return await self.hydrate_many(resources)

    async def record_read(self, resource_id: str, user_id: str) -> None:
        await self.resources.inc_stat(resource_id, "reads")
        await self._safe(
            self.analytics.record, event_type="read",
            resource_id=resource_id, user_id=user_id,
        )

    async def record_download(self, resource_id: str, user_id: str | None) -> None:
        await self.resources.inc_stat(resource_id, "downloads")
        await self._safe(
            self.analytics.record, event_type="download",
            resource_id=resource_id, user_id=user_id,
        )

    async def record_search(
        self, *, query: str, user_id: str | None, result_count: int, department: str | None
    ) -> None:
        await self._safe(
            self.analytics.record,
            event_type="search",
            user_id=user_id,
            department_code=department,
            search_query=query,
            result_count=result_count,
        )

    # ── free/premium access ─────────────────────────────

    async def can_user_access(self, resource: Resource, user: Any | None) -> bool:
        if resource.access == AccessType.FREE:
            return True
        if user is None:
            return False
        if user.role == Role.ADMIN:
            return True
        return await self.purchases.has_access(user.user_id, resource.resource_id)

    async def _safe(self, coro_fn, *args, **kwargs):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            log.warning(
                "Degraded dependency (%s): %s", coro_fn.__qualname__, exc,
                extra={"event": "degraded_call"},
            )
            return None

    async def _safe_list(self, coro_fn, *args, **kwargs) -> list:
        result = await self._safe(coro_fn, *args, **kwargs)
        return result or []


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
