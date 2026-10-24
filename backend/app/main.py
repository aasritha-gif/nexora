from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import AppState, enforce_rate_limit
from app.api.router import api_router
from app.api.routes import health
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, DatabaseUnavailableError, register_exception_handlers
from app.core.logging import (
    configure_logging,
    get_logger,
    monotonic_ms,
    new_request_id,
    request_id_var,
)
from app.databases import Databases

# MongoDB is mandatory: the API is useless without it, so boot waits a bounded
# time for it rather than starting permanently degraded.
MONGO_BOOT_ATTEMPTS = 10
MONGO_RECOVERY_INTERVAL_SECONDS = 5

MAX_REQUEST_ID_LENGTH = 64
_PUBLIC_PATHS = frozenset({"/", "/docs", "/redoc", "/openapi.json"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    log = app.state.logger
    databases = Databases(settings)
    app.state.databases = databases
    app.state.app_state = None

    await databases.startup()
    state = await _build_state(app, databases, log)
    recovery: asyncio.Task | None = None
    if state is not None:
        app.state.app_state = state
        await _bootstrap(state, log)
    else:
        log.error(
            "Starting in degraded mode: MongoDB is unreachable. Only /health is "
            "serving; a background task keeps retrying.",
            event="startup_degraded",
        )
        recovery = asyncio.create_task(_recover_state(app, databases, log))

    log.info(
        "NEXORA API ready",
        event="startup_complete",
        version=settings.app_version,
        **settings.safe_summary(),
    )
    try:
        yield
    finally:
        if recovery is not None:
            recovery.cancel()
        if app.state.app_state is not None:
            await app.state.app_state.close()
        await databases.shutdown()
        log.info("NEXORA API stopped", event="shutdown_complete")


async def _build_state(app: FastAPI, databases: Databases, log) -> AppState | None:
    for attempt in range(1, MONGO_BOOT_ATTEMPTS + 1):
        try:
            return AppState(app.state.settings, databases)
        except RuntimeError:
            pass
        log.warning(
            "MongoDB unavailable at startup (attempt %d/%d)",
            attempt,
            MONGO_BOOT_ATTEMPTS,
            event="mongo_boot_retry",
        )
        # health_check() re-runs connect(), so this is also the reconnect path.
        await databases.mongo.health_check()
        if attempt < MONGO_BOOT_ATTEMPTS:
            await asyncio.sleep(min(2 ** attempt, 8))
    return None


async def _recover_state(app: FastAPI, databases: Databases, log) -> None:
    while True:
        await asyncio.sleep(MONGO_RECOVERY_INTERVAL_SECONDS)
        await databases.mongo.health_check()
        try:
            state = AppState(app.state.settings, databases)
        except RuntimeError:
            continue
        app.state.app_state = state
        await _bootstrap(state, log)
        log.warning(
            "MongoDB recovered — NEXORA is fully operational", event="mongo_recovered"
        )
        return


async def _bootstrap(state: AppState, log) -> None:
    """Idempotent first-run wiring: source registry, admin account, taxonomy."""
    await state.ingestion.ensure_sources()

    if state.settings.admin_email and state.settings.admin_password:
        await state.users.ensure_admin(
            state.settings.admin_email, state.settings.admin_password
        )
    else:
        log.warning(
            "NEXORA_ADMIN_EMAIL / NEXORA_ADMIN_PASSWORD are not set. No bootstrap "
            "admin will be created — admin routes stay unreachable until one is "
            "promoted directly in MongoDB.",
            event="admin_bootstrap_skipped",
        )

    if await state.taxonomy.is_empty():
        await _auto_seed_taxonomy(state, log)


async def _auto_seed_taxonomy(state: AppState, log) -> None:
    """Install the department taxonomy on first boot.

    This is reference data, not demo data: registration validates a department
    against it and ingestion classification votes against its subject/topic
    names, so an empty taxonomy leaves the product half-functional. It is safe
    to install unconditionally. Illustrative users/resources are *not* seeded
    here — that stays opt-in via `scripts/seed.py --demo`."""
    from app.seed import seed_taxonomy  # local import: keeps boot light, no import cycle

    try:
        report = await seed_taxonomy(state)
        log.info(
            "Taxonomy installed on first boot",
            event="taxonomy_seeded",
            departments=report.departments,
            subjects=report.subjects,
            topics=report.topics,
        )
    except Exception:  # noqa: BLE001 - boot must not die on a seed failure
        log.exception(
            "Taxonomy auto-seed failed; registration and ingestion classification "
            "need it. Re-run `python scripts/seed.py --taxonomy` once MongoDB is "
            "healthy.",
            event="taxonomy_seed_failed",
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.debug)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "NEXORA — an academic resource discovery platform spanning MongoDB "
            "(canonical documents), Neo4j (knowledge graph), MonetDB (analytics) "
            "and Redis (cache, sessions, rate limits)."
        ),
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )
    app.state.settings = settings
    app.state.logger = get_logger("nexora")
    app.state.started_at = time.time()

    app.include_router(health.router)
    app.include_router(
        api_router, prefix="/api", dependencies=[Depends(enforce_rate_limit)]
    )

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "api": "/api",
            "health": "/health",
            "readiness": "/health/readiness",
            "docs": "/docs" if not settings.is_production else "disabled in production",
        }

    register_exception_handlers(app)

    # add_middleware() prepends, so registration order is the reverse of the
    # resulting stack. Desired outermost→innermost: CORS → observability →
    # bearer auth → routes. CORS must wrap everything so preflight OPTIONS and
    # error responses both carry the right headers.
    app.middleware("http")(bearer_auth_middleware)
    app.middleware("http")(observability_middleware)
    cors_origins = (
        [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        if isinstance(settings.cors_origins, str)
        else list(settings.cors_origins)
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    return app


async def bearer_auth_middleware(request: Request, call_next):
    """Populate request.state.user from a bearer token, if one is presented.

    Never raises: middleware sits outside FastAPI's exception handlers, so a
    rejection is stored on request.state and surfaced as a proper 401 by the
    get_current_user dependency of whichever route actually requires identity.
    Public routes therefore keep working when a stale token is sent.
    """
    request.state.user = None
    request.state.auth_error = None

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() == "bearer" and token:
        state: AppState | None = getattr(request.app.state, "app_state", None)
        if state is None:
            request.state.auth_error = DatabaseUnavailableError("MongoDB")
        else:
            try:
                request.state.user = await state.auth.resolve_access_token(token)
            except AuthenticationError as exc:
                request.state.auth_error = exc
    return await call_next(request)


async def observability_middleware(request: Request, call_next):
    log = request.app.state.logger
    request_id = _request_id(request)
    context = request_id_var.set(request_id)
    request.state.request_id = request_id
    started = monotonic_ms()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        log.error(
            "Request failed", event="request_error", method=request.method,
            path=request.url.path, status_code=500, request_id=request_id,
        )
        raise
    finally:
        duration_ms = round(monotonic_ms() - started, 1)
        if not _is_probe(request.url.path):
            log.log(
                logging.ERROR if status_code >= 500 else logging.INFO,
                "request",
                event="http_request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                client=_client_address(request),
                user_id=getattr(getattr(request.state, "user", None), "user_id", None),
            )
        request_id_var.reset(context)


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "")
    # Bounded, and stripped of control characters: this value is echoed into a
    # response header and into every log line for the request.
    cleaned = "".join(ch for ch in supplied if ch.isalnum() or ch in "-_.")
    return cleaned[:MAX_REQUEST_ID_LENGTH] or new_request_id()


def _client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_probe(path: str) -> bool:
    return path in _PUBLIC_PATHS or path.startswith("/health")


app = create_app()
