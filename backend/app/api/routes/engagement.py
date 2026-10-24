from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.dependencies import (
    AppState,
    get_app_state,
    get_current_user,
    get_current_user_optional,
)
from app.core.errors import NotFoundError
from app.models.user import User
from app.schemas.engagement import BookmarkRequest, ProgressRequest

router = APIRouter(tags=["engagement"])


class NoteRequest(BaseModel):
    resource_id: str
    title: str | None = Field(default=None, max_length=160)
    body: str = Field(..., min_length=1, max_length=20000)


# ------------------------------------------------------------------ bookmarks


@router.get("/me/bookmarks")
async def list_bookmarks(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    rows = await state.bookmarks.user_bookmarks(user.user_id)
    saved_at = {row["resource_id"]: row["created_at"] for row in rows}
    resources = await state.resources.by_ids_ordered(list(saved_at))
    hydrated = await state.resource_service.hydrate_many(resources)
    return {
        "items": [
            {**item.model_dump(mode="json"), "bookmarked_at": saved_at[item.resource_id]}
            for item in hydrated
        ],
        "total": len(hydrated),
    }


@router.post("/me/bookmarks", status_code=201)
async def add_bookmark(
    data: BookmarkRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    if not await state.resources.exists(data.resource_id):
        raise NotFoundError("Resource not found")
    created = await state.bookmarks.add(user.user_id, data.resource_id)
    await state.resources.inc_stat(data.resource_id, "bookmarks", 1 if created else 0)
    return {"resource_id": data.resource_id, "bookmarked": True, "created": created}


@router.delete("/me/bookmarks/{resource_id}")
async def remove_bookmark(
    resource_id: str,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    removed = await state.bookmarks.remove(user.user_id, resource_id)
    if removed:
        await state.resources.inc_stat(resource_id, "bookmarks", -1)
    return {"resource_id": resource_id, "bookmarked": False}


@router.get("/me/bookmarks/status/{resource_id}")
async def bookmark_status(
    resource_id: str,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    return {
        "resource_id": resource_id,
        "bookmarked": await state.bookmarks.is_bookmarked(user.user_id, resource_id),
    }


# -------------------------------------------------------------- reading history


@router.get("/me/history")
async def reading_history(
    limit: int = Query(default=30, ge=1, le=100),
    state_filter: str | None = Query(default=None, alias="status", pattern="^(in_progress|completed)$"),
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    if state_filter == "in_progress":
        entries = await state.history.in_progress(user.user_id, limit=limit)
    elif state_filter == "completed":
        entries = await state.history.completed(user.user_id)[:limit]
    else:
        entries = await state.history.user_history(user.user_id, limit=limit)

    resources = await state.resources.by_ids_ordered([e.resource_id for e in entries])
    hydrated = {r.resource_id: r for r in await state.resource_service.hydrate_many(resources)}
    return {
        "items": [
            {
                **entry.model_dump(mode="json"),
                "resource": hydrated[entry.resource_id].model_dump(mode="json")
                if entry.resource_id in hydrated else None,
            }
            for entry in entries
        ],
        "total": len(entries),
    }


@router.post("/me/history/{resource_id}/progress")
async def update_progress(
    resource_id: str,
    data: ProgressRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    entry = await state.history.update_progress(
        user.user_id, resource_id, percent=data.percent, last_chunk=data.last_chunk
    )
    await state.resource_service.record_read(resource_id, user.user_id)
    return entry.model_dump(mode="json")


# ------------------------------------------------------------- recommendations


@router.get("/recommendations")
async def recommendations(
    user: User | None = Depends(get_current_user_optional),
    state: AppState = Depends(get_app_state),
):
    """Personalised when signed in, popularity-driven when not. Neither path
    invents resources — every card comes from the live library."""
    feed = await state.recommendations.for_user(user) if user else await state.recommendations.anonymous_feed()
    return await _serialize_feed(state, feed)


@router.get("/me/recommendations")
async def my_recommendations(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    return await _serialize_feed(state, await state.recommendations.for_user(user))


async def _serialize_feed(state: AppState, feed: dict[str, Any]) -> dict[str, Any]:
    """Turn Resource/section mixes from the service into JSON-safe cards."""
    out: dict[str, Any] = {"personalized": feed.get("personalized", False), "sections": {}}

    for key in ("recommended", "because_you_read", "students_also_explored", "continue_learning"):
        out["sections"][key] = [_card(item) for item in feed.get(key) or []]

    seeds = feed.get("because_you_read_seeds") or []
    if seeds:
        resources = await state.resources.get_many(list(seeds))
        hydrated = await state.resource_service.hydrate_many(resources)
        out["because_you_read_seeds"] = [item.model_dump(mode="json") for item in hydrated]
    return out


def _card(item: Any) -> dict[str, Any]:
    dump = getattr(item, "model_dump", None)
    if dump is None:
        return dict(item)
    return dump(mode="json")


# ------------------------------------------------------ notes / study artifacts


@router.get("/me/notes")
async def my_notes(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    return {"items": await state.ai_service.list_notes(user.user_id)}


@router.post("/me/notes", status_code=201)
async def create_note(
    data: NoteRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    if not await state.resources.exists(data.resource_id):
        raise NotFoundError("Resource not found")
    note = await state.ai_service.add_note(
        user.user_id, data.resource_id, data.body, title=data.title
    )
    return note


@router.get("/me/flashcards")
async def my_flashcards(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    return {"items": await state.ai_service.list_flashcards(user.user_id)}


@router.get("/me/questions")
async def my_questions(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    return {"items": await state.ai_service.list_questions(user.user_id)}


# ------------------------------------------------------------------- purchases


@router.get("/me/purchases")
async def my_purchases(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    purchases = await state.purchases.list_for_user(user.user_id)
    return {
        "items": [
            {
                "purchase_id": p.purchase_id,
                "resource_id": p.resource_id,
                "amount_usd": p.amount_usd,
                "currency": p.currency,
                "provider": p.provider,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in purchases
        ]
    }
