from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    AppState,
    get_app_state,
    get_current_user,
    get_current_user_optional,
)
from app.core.errors import NotFoundError
from app.models.resource import AccessType, Difficulty, Resource, ResourceType
from app.models.user import User
from app.schemas.engagement import ProgressRequest, RatingRequest, ReviewRequest
from app.schemas.resource import Paginated, RelatedResource, ResourceDetail
from app.schemas.search import SearchFilters

log = logging.getLogger(__name__)
router = APIRouter(tags=["resources"])

_SORTABLE = {
    "newest": [("created_at", -1)],
    "oldest": [("created_at", 1)],
    "popular": [("stats.views", -1)],
    "rating": [("stats.rating_sum", -1)],
    "title": [("title", 1)],
}


@router.get("/resources", response_model=Paginated)
async def list_resources(
    q: str = Query(default="", max_length=512),
    department: str | None = None,
    subject: str | None = None,
    topic: str | None = None,
    type: list[ResourceType] | None = Query(default=None),
    access: AccessType | None = None,
    difficulty: Difficulty | None = None,
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    author: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=12, ge=1, le=48),
    sort: str = Query(default="newest"),
    state: AppState = Depends(get_app_state),
    user: User | None = Depends(get_current_user_optional),
):
    filters = SearchFilters(
        query=q.strip(),
        department=department,
        subject=subject,
        topic=topic,
        types=type or [],
        access=access,
        difficulty=difficulty,
        year_from=year_from,
        year_to=year_to,
        min_rating=min_rating,
        author=author,
    )
    if filters.query:
        result = await state.search_service.search(
            filters,
            page=page,
            page_size=page_size,
            user=user,
            hydrate=state.resource_service.hydrate_many,
        )
        return Paginated(
            items=result.results,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            pages=result.pages,
        )

    resources, total = await state.resources.query(
        filters,
        skip=(page - 1) * page_size,
        limit=page_size,
        sort=_SORTABLE.get(sort, _SORTABLE["newest"]),
    )
    items = await state.resource_service.hydrate_many(resources)
    pages = (total + page_size - 1) // page_size if total else 0
    return Paginated(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.get("/resources/{resource_id}", response_model=ResourceDetail)
async def get_resource(
    resource_id: str,
    state: AppState = Depends(get_app_state),
    user: User | None = Depends(get_current_user_optional),
):
    await _require_resource(state, resource_id)
    detail = await state.resource_service.get_detail(
        resource_id, user_id=user.user_id if user else None
    )
    if user:
        await state.history.record_view(user.user_id, resource_id)
        await _safe_graph_activity(state, user.user_id, resource_id)
    return detail


@router.get("/resources/{resource_id}/related", response_model=list[RelatedResource])
async def related_resources(
    resource_id: str,
    limit: int = Query(default=8, ge=1, le=24),
    state: AppState = Depends(get_app_state),
):
    return await state.resource_service.related(resource_id, limit=limit)


@router.get("/resources/{resource_id}/access")
async def resource_access(
    resource_id: str,
    state: AppState = Depends(get_app_state),
    user: User | None = Depends(get_current_user_optional),
):
    resource = await _require_resource(state, resource_id)
    can_access = await _can_access(state, resource, user)
    return {
        "resource_id": resource_id,
        "access": resource.access.value,
        "premium_price_usd": resource.premium_price_usd,
        "can_access": can_access,
        "requires_purchase": resource.access == AccessType.PREMIUM and not can_access,
        "payment_configured": state.settings.payment_provider != "none",
    }


@router.get("/resources/{resource_id}/reviews")
async def list_reviews(
    resource_id: str,
    state: AppState = Depends(get_app_state),
):
    await _require_resource(state, resource_id)
    reviews = await state.reviews.list_for_resource(resource_id)
    names = await _user_names(state, {r.user_id for r in reviews})
    return [
        {
            "review_id": r.review_id,
            "user_id": r.user_id,
            "user_name": names.get(r.user_id),
            "rating": r.rating,
            "title": r.title,
            "body": r.body,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


@router.post("/resources/{resource_id}/reviews", status_code=201)
async def write_review(
    resource_id: str,
    data: ReviewRequest,
    state: AppState = Depends(get_app_state),
    user: User = Depends(get_current_user),
):
    await _require_resource(state, resource_id)
    review = await state.reviews.upsert(
        user.user_id, resource_id,
        rating=data.rating, title=data.title, body=data.body,
    )
    rating_sum, rating_count = await state.reviews.refresh_resource_rating(resource_id)
    await state.cache.delete(f"resource:{resource_id}", "resource:detail:{resource_id}")
    await _safe_analytics(state, event_type="review", resource_id=resource_id, user_id=user.user_id)
    log.info(
        "Review saved",
        extra={"event": "review_saved", "resource_id": resource_id, "user_id": user.user_id},
    )
    return {
        "review_id": review.review_id,
        "rating": review.rating,
        "rating_sum": rating_sum,
        "rating_count": rating_count,
        "rating_average": round(rating_sum / rating_count, 2) if rating_count else None,
        "message": "Review published",
    }


@router.delete("/resources/{resource_id}/reviews")
async def delete_review(
    resource_id: str,
    state: AppState = Depends(get_app_state),
    user: User = Depends(get_current_user),
):
    removed = await state.reviews.delete_for_user(user.user_id, resource_id)
    if removed:
        await state.reviews.refresh_resource_rating(resource_id)
    return {"removed": removed, "message": "Review removed" if removed else "No review to remove"}


@router.post("/resources/{resource_id}/rate")
async def rate_resource(
    resource_id: str,
    data: RatingRequest,
    state: AppState = Depends(get_app_state),
    user: User = Depends(get_current_user),
):
    """Rating without a written review. Re-rating replaces the previous score."""
    await _require_resource(state, resource_id)
    existing = await state.reviews.collection.find_one(
        {"user_id": user.user_id, "resource_id": resource_id}
    )
    if existing and (existing.get("body") or "").strip():
        raise NotFoundError(
            "You already wrote a review for this resource — update it instead of rating again"
        )
    await state.reviews.upsert(
        user.user_id, resource_id, rating=data.rating, title=None, body=""
    )
    rating_sum, rating_count = await state.reviews.refresh_resource_rating(resource_id)
    await _safe_analytics(state, event_type="rate", resource_id=resource_id, user_id=user.user_id)
    return {
        "rating": data.rating,
        "rating_average": round(rating_sum / rating_count, 2) if rating_count else None,
        "rating_count": rating_count,
    }


@router.post("/resources/{resource_id}/read")
async def mark_read(
    resource_id: str,
    state: AppState = Depends(get_app_state),
    user: User = Depends(get_current_user),
):
    resource = await _require_resource(state, resource_id)
    if not await _can_access(state, resource, user):
        raise NotFoundError("This premium resource is not available to your account")
    await state.resource_service.record_read(resource_id, user.user_id)
    return {"recorded": True, "resource_id": resource_id}


@router.post("/resources/{resource_id}/progress")
async def update_progress(
    resource_id: str,
    data: ProgressRequest,
    state: AppState = Depends(get_app_state),
    user: User = Depends(get_current_user),
):
    await _require_resource(state, resource_id)
    entry = await state.history.update_progress(
        user.user_id, resource_id, percent=data.percent, last_chunk=data.last_chunk
    )
    return {
        "resource_id": resource_id,
        "percent": entry.progress.percent,
        "completed": entry.progress.completed,
    }


@router.get("/home/feed")
async def home_feed(
    department: str | None = None,
    state: AppState = Depends(get_app_state),
):
    return await state.resource_service.homepage_feed(department=department)


@router.get("/trending")
async def trending(
    limit: int = Query(default=12, ge=1, le=48),
    state: AppState = Depends(get_app_state),
):
    return await state.resource_service.trending(limit=limit)


@router.get("/stats/resources")
async def resource_stats(state: AppState = Depends(get_app_state)):
    return {
        "total": await state.resources.count(),
        "by_department": await state.resources.counts_by_department(),
        "by_type": await state.resources.counts_by_type(),
        "seed": await state.resources.seed_count(),
    }


# ── helpers ───────────────────────────────────────────


async def _require_resource(state: AppState, resource_id: str) -> Resource:
    try:
        return await state.resources.get(resource_id)
    except NotFoundError:
        raise NotFoundError(f"Resource '{resource_id}' was not found")


async def _can_access(state: AppState, resource: Resource, user: User | None) -> bool:
    return await state.resource_service.can_user_access(resource, user)


async def _safe_graph_activity(state: AppState, user_id: str, resource_id: str) -> None:
    try:
        await state.graph.record_activity(
            user_id=user_id, resource_id=resource_id, relation="VIEWED"
        )
    except Exception as exc:  # noqa: BLE001 - graph is advisory, never request-blocking
        log.warning(
            "Graph activity not recorded: %s", exc, extra={"event": "degraded_call"}
        )


async def _safe_analytics(state: AppState, **kwargs: Any) -> None:
    try:
        await state.analytics.record(**kwargs)
    except Exception as exc:  # noqa: BLE001 - analytics must never break a request
        log.warning("Analytics record failed: %s", exc, extra={"event": "degraded_call"})


async def _user_names(state: AppState, user_ids: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for user_id in user_ids:
        try:
            user = await state.users.get_by_id(user_id)
        except Exception:  # noqa: BLE001 - a deleted author should not hide the review
            continue
        names[user_id] = user.name
    return names
