from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.dependencies import AppState, get_app_state, require_role
from app.core.logging import get_logger
from app.models.user import Role, User
from app.schemas.ingestion import (
    IngestionRunResponse,
    SourceConfigRequest,
    SourceResponse,
    SourceUpdateRequest,
    SyncStatusResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

admin_only = require_role(Role.ADMIN)

# Adapters that only work with a real credential. Reported, never faked.
_API_KEY_SOURCES = {"youtube"}


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status(
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    payload = await state.ingestion.status()
    sources = [_source_response(state, doc) for doc in payload["sources"]]
    runs = [IngestionRunResponse.model_validate(run) for run in payload["recent_runs"]]
    return SyncStatusResponse(
        last_synchronization=max(
            (s.last_run_at for s in sources if s.last_run_at), default=None
        ),
        sources=sources,
        recent_runs=runs,
        retry_queue_size=int(payload["totals"]["retry_queue"]),
    )


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    return [_source_response(state, doc) for doc in await state.ingestion.list_sources()]


@router.patch("/sources/{source_key}", response_model=SourceResponse)
async def update_source(
    source_key: str,
    data: SourceUpdateRequest,
    state: AppState = Depends(get_app_state),
    user: User = Depends(admin_only),
):
    source = await state.ingestion.update_source(
        source_key, enabled=data.enabled, schedule_minutes=data.schedule_minutes
    )
    logger.info("source_updated", source=source_key, by=user.user_id,
                enabled=source.enabled, schedule_minutes=source.schedule_minutes)
    return _source_response(state, source.model_dump(mode="json"))


@router.put("/sources/{source_key}/config", response_model=SourceResponse)
async def update_source_config(
    source_key: str,
    data: SourceConfigRequest,
    state: AppState = Depends(get_app_state),
    user: User = Depends(admin_only),
):
    source = await state.ingestion.update_source_config(
        source_key, data.model_dump(exclude_none=True)
    )
    logger.info("source_config_updated", source=source_key, by=user.user_id,
                queries=len(source.config.get("queries") or []))
    return _source_response(state, source.model_dump(mode="json"))


@router.post("/sources/{source_key}/run", response_model=IngestionRunResponse)
async def run_source_now(
    source_key: str,
    limit: int = Query(default=10, ge=1, le=60),
    state: AppState = Depends(get_app_state),
    user: User = Depends(admin_only),
):
    """Runs inline so the admin sees the real result, including failures."""
    run = await state.ingestion.run_source(source_key, triggered_by="admin", limit=limit)
    logger.info("ingestion_run_triggered", source=source_key, by=user.user_id,
                run_id=run.run_id, status=run.status, added=run.added)
    return IngestionRunResponse.model_validate(run.model_dump(mode="json"))


@router.post("/sync")
async def sync_all_now(
    background: BackgroundTasks,
    state: AppState = Depends(get_app_state),
    user: User = Depends(admin_only),
):
    """Full sync runs in the background: it may take minutes across sources."""
    background.add_task(_background_sync, state, user.user_id)
    return {
        "status": "scheduled",
        "message": "Synchronization started in the background. Poll /ingestion/runs for results.",
        "sync_enabled": state.settings.sync_enabled,
    }


@router.post("/retries/process")
async def process_retries(
    limit: int = Query(default=25, ge=1, le=100),
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    result = await state.ingestion.process_retries(limit=limit)
    return {**result, "queue_remaining": await state.ingestion.retry_queue_depth()}


@router.get("/runs", response_model=list[IngestionRunResponse])
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    return [
        IngestionRunResponse.model_validate(run)
        for run in await state.ingestion.recent_runs(limit=limit)
    ]


async def _background_sync(state: AppState, user_id: str) -> None:
    try:
        result = await state.ingestion.sync_all(triggered_by="admin")
        logger.info("sync_all_complete", by=user_id, ran=len(result["ran"]),
                    skipped=len(result["skipped"]))
    except Exception as exc:  # noqa: BLE001 - background tasks must not raise
        logger.error("sync_all_failed", by=user_id, reason=str(exc)[:300])


def _source_response(state: AppState, doc: dict[str, Any]) -> SourceResponse:
    adapter = doc.get("adapter", "")
    available, reason = state.ingestion.adapter_availability(adapter)
    requires_key = bool(doc.get("requires_api_key")) or adapter in _API_KEY_SOURCES
    return SourceResponse(
        source_key=doc["source_key"],
        name=doc.get("name") or doc["source_key"],
        adapter=adapter,
        enabled=bool(doc.get("enabled", True)),
        requires_api_key=requires_key,
        api_key_configured=(
            bool(state.settings.youtube_api_key) if adapter in _API_KEY_SOURCES else True
        ),
        adapter_available=available,
        unavailable_reason=reason,
        schedule_minutes=int(doc.get("schedule_minutes") or 360),
        last_run_at=_as_datetime(doc.get("last_run_at")),
        last_run_status=str(doc.get("last_run_status") or "never"),
        config=doc.get("config") or {},
    )


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
