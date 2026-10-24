from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import AppState, get_app_state, require_role
from app.core.logging import get_logger
from app.models.user import Role, User
from app.schemas.analytics import (
    AnalyticsSummary,
    DailyActivity,
    PopularDepartment,
    PopularSubject,
    TopResource,
    TrendingItem,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def _unavailable_reason(state: AppState) -> str:
    """Reason string safe to show: the adapter already strips credentials and
    host details from driver errors."""
    return state.databases.monetdb.reason or "analytics database not connected"


async def _guarded(coro_fn, *args, **kwargs) -> Any | None:
    """Analytics is MonetDB-only and MonetDB is allowed to be down. A failure
    degrades this section to `available: false` instead of failing the request."""
    try:
        return await coro_fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - degraded analytics must not 500
        logger.warning("analytics_query_failed", reason=str(exc)[:200])
        return None


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    days: int = Query(default=14, ge=1, le=90),
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    if not state.analytics.available:
        return AnalyticsSummary(
            total_events=0, last_7_days=0, available=False,
            unavailable_reason=_unavailable_reason(state),
        )

    counts = await _guarded(state.analytics.summary) or {"total_events": 0, "last_7_days": 0}
    top_rows = await _guarded(state.analytics.top_resources, limit=10) or []
    subjects = await _guarded(state.analytics.popular_subjects, limit=10) or []
    departments = await _guarded(state.analytics.popular_departments) or []
    daily = await _guarded(state.analytics.daily_activity, days=days) or []
    searches = await _guarded(state.analytics.top_searches, limit=10) or []

    names = await state.taxonomy.name_maps()
    ids = [row["resource_id"] for row in top_rows]
    resources = {r.resource_id: r for r in await state.resources.get_many(ids)}

    return AnalyticsSummary(
        total_events=int(counts["total_events"]),
        last_7_days=int(counts["last_7_days"]),
        top_resources=[
            TopResource(
                resource_id=row["resource_id"],
                title=resources[row["resource_id"]].title if row["resource_id"] in resources else None,
                type=resources[row["resource_id"]].type.value if row["resource_id"] in resources else None,
                views=row["count"],
            )
            for row in top_rows
        ],
        popular_subjects=[
            PopularSubject(
                subject_code=row["subject_code"],
                subject_name=names["subject"].get(row["subject_code"]),
                department_code=row.get("department_code"),
                events=row["events"],
            )
            for row in subjects
        ],
        popular_departments=[
            PopularDepartment(department_code=row["department_code"], events=row["events"])
            for row in departments
        ],
        daily_activity=[DailyActivity(**row) for row in daily],
        top_searches=searches,
        available=True,
        unavailable_reason=None,
    )


@router.get("/trending", response_model=list[TrendingItem])
async def trending(
    days: int = Query(default=14, ge=1, le=90),
    limit: int = Query(default=10, ge=1, le=50),
    state: AppState = Depends(get_app_state),
):
    """Public trending signal. Falls back to MongoDB view counters when MonetDB
    is unreachable so the homepage never renders an empty rail for a degraded
    analytics store."""
    rows = await _guarded(state.analytics.trending_resources, days=days, limit=limit) if state.analytics.available else None
    if rows:
        return [
            TrendingItem(resource_id=row["resource_id"], score=float(row["score"]), window=f"{days}d")
            for row in rows
        ]
    popular = await state.resources.popular(limit=limit)
    return [
        TrendingItem(
            resource_id=resource.resource_id,
            score=float(resource.stats.views),
            window="all_time_mongodb_fallback",
        )
        for resource in popular
    ]


@router.get("/top-resources")
async def top_resources(
    event_type: str = Query(default="view", pattern="^(view|read|download|bookmark|search|review)$"),
    limit: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    if not state.analytics.available:
        return {"available": False, "reason": _unavailable_reason(state), "items": []}
    rows = await _guarded(state.analytics.top_resources, event_type=event_type, limit=limit) or []
    resources = {r.resource_id: r for r in await state.resources.get_many([r["resource_id"] for r in rows])}
    return {
        "available": True,
        "reason": None,
        "event_type": event_type,
        "items": [
            {
                "resource_id": row["resource_id"],
                "count": row["count"],
                "title": resources[row["resource_id"]].title if row["resource_id"] in resources else None,
            }
            for row in rows
        ],
    }


@router.get("/searches")
async def top_searches(
    limit: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    if not state.analytics.available:
        return {"available": False, "reason": _unavailable_reason(state), "items": []}
    rows = await _guarded(state.analytics.top_searches, limit=limit) or []
    return {"available": True, "reason": None, "items": rows}


@router.get("/daily")
async def daily_activity(
    days: int = Query(default=30, ge=1, le=365),
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    if not state.analytics.available:
        return {"available": False, "reason": _unavailable_reason(state), "items": []}
    rows = await _guarded(state.analytics.daily_activity, days=days) or []
    return {"available": True, "reason": None, "items": rows}


@router.get("/buffer")
async def buffer_status(
    admin: User = Depends(require_role(Role.ADMIN)),
    state: AppState = Depends(get_app_state),
):
    """Operational view of the in-memory analytics buffer — how many events are
    waiting on MonetDB and whether the store is reachable."""
    flushed = await _guarded(state.analytics.flush) if state.analytics.available else None
    return {
        "available": state.analytics.available,
        "reason": None if state.analytics.available else _unavailable_reason(state),
        "pending_events": state.analytics.pending,
        "flushed_now": flushed if flushed is not None else 0,
        "flush_threshold": state.analytics.flush_threshold,
    }
