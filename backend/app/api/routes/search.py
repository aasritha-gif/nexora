from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    AppState,
    get_app_state,
    get_current_user_optional,
)
from app.models.resource import AccessType, Difficulty, ResourceType
from app.models.user import User
from app.schemas.search import SearchFilters

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


def _filters(
    q: str,
    department: str | None,
    subject: str | None,
    topic: str | None,
    types: list[ResourceType] | None,
    access: AccessType | None,
    difficulty: Difficulty | None,
    year_from: int | None,
    year_to: int | None,
    min_rating: float | None,
    author: str | None,
) -> SearchFilters:
    return SearchFilters(
        query=q.strip(),
        department=department,
        subject=subject,
        topic=topic,
        types=types or [],
        access=access,
        difficulty=difficulty,
        year_from=year_from,
        year_to=year_to,
        min_rating=min_rating,
        author=author,
    )


@router.get("")
@router.get("/")
async def search_get(
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
    semantic: bool = True,
    state: AppState = Depends(get_app_state),
    user: User | None = Depends(get_current_user_optional),
):
    filters = _filters(
        q, department, subject, topic, type, access, difficulty,
        year_from, year_to, min_rating, author,
    )
    return await state.search_service.search(
        filters,
        page=page,
        page_size=page_size,
        semantic=semantic,
        user=user,
        hydrate=state.resource_service.hydrate_many,
    )


@router.post("")
@router.post("/")
async def search_post(
    payload: dict,
    state: AppState = Depends(get_app_state),
    user: User | None = Depends(get_current_user_optional),
):
    from app.schemas.search import SearchRequest

    request = SearchRequest.model_validate(payload)
    return await state.search_service.search(
        request.filters,
        page=request.page,
        page_size=request.page_size,
        semantic=request.semantic,
        user=user,
        hydrate=state.resource_service.hydrate_many,
    )


@router.get("/suggestions")
async def suggestions(state: AppState = Depends(get_app_state)):
    return await state.search_service.suggestions()


@router.get("/filters")
async def available_filters(state: AppState = Depends(get_app_state)):
    """Everything the filter sidebar needs, sourced from real taxonomy data."""
    departments = await state.taxonomy.list_departments()
    names = await state.taxonomy.name_maps()
    return {
        "departments": [
            {"code": d.code, "name": d.name} for d in departments
        ],
        "types": [t.value for t in ResourceType],
        "difficulty": [d.value for d in Difficulty],
        "access": [a.value for a in AccessType],
        "authors": await state.resources.author_list(limit=40),
        "by_type": await state.resources.counts_by_type(),
        "subject_names": names["subject"],
        "topic_names": names["topic"],
    }
