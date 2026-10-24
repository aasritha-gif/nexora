from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import AppState, get_app_state, get_current_user
from app.core.errors import NotFoundError
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    department_code: str | None = Field(default=None, max_length=8)
    academic_year: int | None = Field(default=None, ge=1, le=8)
    semester: int | None = Field(default=None, ge=1, le=10)
    preferences: dict[str, Any] | None = None


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if "department_code" in fields:
        fields["department_code"] = fields["department_code"].upper()
        if not await state.taxonomy.department_exists(fields["department_code"]):
            raise NotFoundError(f"Department '{fields['department_code']}' not found")
    if "preferences" in fields:
        # Preferences merge rather than replace, so a client updating one key
        # does not silently wipe the others.
        fields["profile"] = {**(user.profile or {}), "preferences": fields.pop("preferences")}
    updated = await state.users.update_profile(user.user_id, fields)
    if state.graph.available:
        await _safe_graph_sync(state, updated)
    return UserResponse.model_validate(updated)


@router.get("/me/library")
async def my_library(state: AppState = Depends(get_app_state), user: User = Depends(get_current_user)):
    """One call for the profile page: everything the learner has collected."""
    bookmarks = await state.bookmarks.user_bookmarks(user.user_id)
    in_progress = await state.history.in_progress(user.user_id, limit=8)
    completed = await state.history.completed(user.user_id)
    notes = await state.ai_service.list_notes(user.user_id)
    flashcards = await state.ai_service.list_flashcards(user.user_id)
    questions = await state.ai_service.list_questions(user.user_id)
    purchases = await state.purchases.list_for_user(user.user_id)

    bookmark_ids = [row["resource_id"] for row in bookmarks]
    saved_at = {row["resource_id"]: row["created_at"] for row in bookmarks}
    resources = await state.resources.by_ids_ordered(bookmark_ids)
    hydrated = await state.resource_service.hydrate_many(resources)

    progress_ids = [entry.resource_id for entry in in_progress]
    progress_resources = {
        r.resource_id: r for r in await state.resource_service.hydrate_many(
            await state.resources.by_ids_ordered(progress_ids)
        )
    }

    return {
        "counts": {
            "bookmarks": len(bookmarks),
            "in_progress": len(in_progress),
            "completed": len(completed),
            "notes": len(notes),
            "flashcards": len(flashcards),
            "questions": len(questions),
            "premium_owned": sum(1 for p in purchases if p.status == "paid"),
        },
        "bookmarks": [
            {**item.model_dump(mode="json"), "bookmarked_at": saved_at[item.resource_id]}
            for item in hydrated
        ],
        "continue_learning": [
            {
                "resource": progress_resources[entry.resource_id].model_dump(mode="json")
                if entry.resource_id in progress_resources else None,
                "percent": entry.progress.percent,
                "last_viewed_at": entry.last_viewed_at.isoformat(),
            }
            for entry in in_progress
        ],
        "completed": [entry.resource_id for entry in completed],
    }


@router.get("/me/activity")
async def my_activity(state: AppState = Depends(get_app_state), user: User = Depends(get_current_user)):
    entries = await state.history.user_history(user.user_id, limit=40)
    resources = {
        r.resource_id: r
        for r in await state.resource_service.hydrate_many(
            await state.resources.by_ids_ordered([e.resource_id for e in entries])
        )
    }
    return {
        "items": [
            {
                "resource_id": entry.resource_id,
                "title": resources[entry.resource_id].title if entry.resource_id in resources else None,
                "view_count": entry.view_count,
                "percent": entry.progress.percent,
                "completed": entry.progress.completed,
                "last_viewed_at": entry.last_viewed_at.isoformat(),
            }
            for entry in entries
        ]
    }


async def _safe_graph_sync(state: AppState, user: User) -> None:
    try:
        await state.graph.sync_user(
            user_id=user.user_id,
            department_code=user.department_code,
            role=user.role.value,
        )
    except Exception:  # noqa: BLE001 - a graph lag must not fail a profile edit
        pass
