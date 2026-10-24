from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import AppState, get_app_state
from app.schemas.analytics import DatabaseHealth, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/liveness")
async def liveness():
    """Process is up and serving. Deliberately touches no database."""
    return {"status": "ok"}


@router.get("/health/readiness")
async def readiness(request: Request):
    """Can this instance serve traffic? 503 when MongoDB is unreachable."""
    state: AppState | None = getattr(request.app.state, "app_state", None)
    if state is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "MongoDB is not connected"},
        )
    await state.databases.refresh_health()
    if not state.databases.mongo.available:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "reason": state.databases.mongo.reason or "MongoDB is not connected",
            },
        )
    return {"status": "ready"}


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    state: AppState = request.app.state.app_state
    await state.databases.refresh_health()
    payload = state.databases.status()
    mongo_ok = state.databases.mongo.available
    return HealthResponse(
        status="ok" if mongo_ok else "degraded",
        environment=state.settings.environment,
        version=state.settings.app_version,
        databases=[DatabaseHealth(**entry) for entry in payload["databases"]],
        connected=payload["summary"]["connected"],
        total=payload["summary"]["total"],
    )


@router.get("/config/public")
async def public_config(state: AppState = Depends(get_app_state)):
    """Non-secret configuration the frontend needs to render honest UI state."""
    ai_status = await state.ai_service.status()
    youtube_status = await state.youtube.status()
    return {
        "app_name": state.settings.app_name,
        "version": state.settings.app_version,
        "environment": state.settings.environment,
        "ai": {
            "configured": ai_status["configured"],
            "provider": ai_status["provider"],
            "embeddings_available": ai_status["embeddings_available"],
            "capabilities": ai_status["capabilities"],
        },
        "youtube": {"configured": youtube_status["configured"]},
        "payments_configured": state.settings.payment_provider != "none",
        "sync_enabled": state.settings.sync_enabled,
    }
