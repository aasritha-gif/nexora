from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.dependencies import (
    AppState,
    get_app_state,
    get_current_user,
    get_current_user_optional,
)
from app.core.errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
)
from app.models.resource import Resource
from app.models.user import User
from app.schemas.ai import (
    AIOverviewResponse,
    AIStatus,
    ChatRequest,
    ChatResponse,
    ReaderDocument,
    ReadingActionRequest,
    ReadingActionResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class SectionRequest(BaseModel):
    chunk_indexes: list[int] = Field(..., min_length=1, max_length=60)


@router.get("/status", response_model=AIStatus)
async def ai_status(state: AppState = Depends(get_app_state)):
    """Honest capability report — the UI hides AI panels when this says no."""
    return AIStatus(**await state.ai_service.status())


# ---------------------------------------------------------------- AI Overview


@router.get("/resources/{resource_id}/overview", response_model=AIOverviewResponse)
async def resource_overview(
    resource_id: str,
    force: bool = Query(default=False),
    user: User | None = Depends(get_current_user_optional),
    state: AppState = Depends(get_app_state),
):
    resource = await state.resources.get(resource_id)
    await _require_access(state, resource, user)
    overview = await state.ai_service.overview(resource, force=force)
    return AIOverviewResponse(
        resource_id=overview.resource_id,
        generated_at=overview.generated_at,
        model=overview.model,
        summary=overview.summary,
        key_concepts=overview.key_concepts,
        important_points=overview.important_points,
        difficulty=overview.difficulty,
        prerequisites=overview.prerequisites,
        who_should_read=overview.who_should_read,
        key_takeaways=overview.key_takeaways,
        research=overview.research,
        sources=[{"chunk_index": i, "label": f"Passage {i + 1}"} for i in overview.source_chunks],
    )


# ----------------------------------------------------------------- AI Reading


@router.post("/resources/{resource_id}/reading", response_model=ReadingActionResponse)
async def reading_action(
    resource_id: str,
    data: ReadingActionRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    resource = await state.resources.get(resource_id)
    await _require_access(state, resource, user)
    result = await state.ai_service.reading_action(
        user.user_id, resource, data.action,
        selection=data.selection, language=data.language,
    )
    return ReadingActionResponse(**result)


@router.get("/resources/{resource_id}/reader", response_model=ReaderDocument)
async def reader_document(
    resource_id: str,
    user: User | None = Depends(get_current_user_optional),
    state: AppState = Depends(get_app_state),
):
    """Split-screen reader source. Restricted material reports `readable: false`
    with the publisher link instead of exposing content."""
    resource = await state.resources.get(resource_id)
    can_access = await state.resource_service.can_user_access(resource, user)
    return ReaderDocument(**await state.ai_service.reader_document(resource, can_access))


@router.post("/resources/{resource_id}/reader/section")
async def read_section(
    resource_id: str,
    data: SectionRequest,
    user: User | None = Depends(get_current_user_optional),
    state: AppState = Depends(get_app_state),
):
    resource = await state.resources.get(resource_id)
    await _require_access(state, resource, user)
    chunks = await state.ai_service.read_section(resource_id, data.chunk_indexes)
    return {"resource_id": resource_id, "chunks": chunks}


# ------------------------------------------------------------- resource chatbot


@router.post("/resources/{resource_id}/chat", response_model=ChatResponse)
async def chat(
    resource_id: str,
    data: ChatRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    resource = await state.resources.get(resource_id)
    await _require_access(state, resource, user)
    return ChatResponse(**await state.ai_service.chat(user.user_id, resource, data.message))


@router.get("/resources/{resource_id}/chat")
async def chat_history(
    resource_id: str,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    if not await state.resources.exists(resource_id):
        raise NotFoundError("Resource not found")
    return {
        "resource_id": resource_id,
        "messages": await state.ai_service.chat_history(user.user_id, resource_id),
    }


@router.delete("/resources/{resource_id}/chat")
async def clear_chat(
    resource_id: str,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    deleted = await state.ai_service.clear_chat(user.user_id, resource_id)
    return {"resource_id": resource_id, "deleted": deleted}


async def _require_access(state: AppState, resource: Resource, user: User | None) -> None:
    """AI features operate on resource content, so they inherit access control."""
    if await state.resource_service.can_user_access(resource, user):
        return
    if user is None:
        raise AuthenticationError("Sign in to use AI features on this resource")
    raise AuthorizationError("This premium resource requires purchase before AI features unlock")
