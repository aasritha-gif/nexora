from __future__ import annotations

import json
import logging

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import (
    AuthenticationError,
    AuthorizationError,
    DatabaseUnavailableError,
)
from app.core.rate_limit import RateLimiter
from app.databases import Databases
from app.models.user import Role, User
from app.repositories.analytics import AnalyticsRepository
from app.repositories.cache import CacheRepository
from app.repositories.engagement import (
    BookmarkRepository,
    ReadingHistoryRepository,
    ReviewRepository,
)
from app.repositories.graph import GraphRepository
from app.repositories.purchases import PurchaseRepository
from app.repositories.resources import ResourceRepository
from app.repositories.sessions import SessionStore
from app.repositories.taxonomy import TaxonomyRepository
from app.repositories.users import UserRepository

log = logging.getLogger(__name__)


class AppState:
    """Process-wide wiring created once at startup and owned by the app."""

    def __init__(self, settings: Settings, databases: Databases):
        self.settings = settings
        self.databases = databases

        mongo_db = databases.mongo.db
        if mongo_db is None:
            # Defensive: mongo adapter failed at startup. Repositories created
            # lazily will still raise meaningful errors per request.
            raise RuntimeError("MongoDB is required for NEXORA to operate")

        self.users = UserRepository(mongo_db)
        self.resources = ResourceRepository(mongo_db)
        self.taxonomy = TaxonomyRepository(mongo_db)
        self.bookmarks = BookmarkRepository(mongo_db)
        self.history = ReadingHistoryRepository(mongo_db)
        self.reviews = ReviewRepository(mongo_db)
        self.sessions = SessionStore(databases.redis.client, mongo_db)
        self.graph = GraphRepository(databases.neo4j)
        self.analytics = AnalyticsRepository(databases.monetdb)
        self.cache = CacheRepository(databases.redis.client)
        self.purchases = PurchaseRepository(mongo_db)
        self.rate_limiter = RateLimiter(
            settings.rate_limit_requests, settings.rate_limit_window_seconds
        )
        self.auth_rate_limiter = RateLimiter(
            settings.auth_rate_limit_requests, settings.auth_rate_limit_window_seconds
        )

        # Late imports avoid circular dependency at module load time
        from app.ai.provider import build_provider
        from app.payments.provider import build_payment_provider
        from app.services.ai_service import AIService
        from app.services.auth_service import AuthService
        from app.services.discovery import DiscoveryService
        from app.services.ingestion import IngestionService
        from app.services.recommendation import RecommendationService
        from app.services.resource_service import ResourceService
        from app.services.search_service import SearchService
        from app.services.youtube_service import YouTubeService

        self.ai_provider = build_provider(settings)
        self.payments = build_payment_provider(settings)
        self.youtube = YouTubeService(settings, self.cache)
        self.auth = AuthService(settings, self.users, self.sessions, mongo_db)
        self.ai_service = AIService(settings, self.ai_provider, mongo_db, self.cache)
        self.resource_service = ResourceService(
            settings, self.resources, self.taxonomy, self.graph,
            self.analytics, self.cache, self.purchases,
        )
        self.search_service = SearchService(
            settings, self.resources, self.taxonomy, self.ai_provider,
            self.analytics, self.cache,
        )
        self.recommendations = RecommendationService(
            self.users, self.resources, self.history, self.bookmarks,
            self.graph, self.analytics, self.cache,
        )
        self.ingestion = IngestionService(
            settings, mongo_db, self.resources, self.taxonomy,
            self.graph, self.analytics, self.cache,
            youtube=self.youtube, ai_service=self.ai_service,
        )
        self.discovery = DiscoveryService(self.youtube, self.resources)

    async def close(self) -> None:
        """Release outbound HTTP clients owned by services."""
        for closer in (self.youtube.close, self.payments.close, self.ai_provider.close):
            try:
                await closer()
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise
                log.warning("Service close failed: %s", exc, extra={"event": "shutdown_warning"})
        await self.analytics.flush()


def get_app_state(request: Request) -> AppState:
    state = getattr(request.app.state, "app_state", None)
    if state is None:
        raise DatabaseUnavailableError("MongoDB")
    return state


def get_current_user_optional(request: Request) -> User | None:
    return getattr(request.state, "user", None)


def get_current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    # Surface the reason the bearer token was rejected (expired, revoked,
    # malformed) rather than a generic "no credentials" when we have one.
    error = getattr(request.state, "auth_error", None)
    if error is not None:
        raise error
    raise AuthenticationError("Authentication required")


def require_role(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AuthorizationError("Insufficient permissions for this action")
        return user

    return checker


async def enforce_rate_limit(request: Request) -> None:
    """Per-identity fixed-window throttle.

    Authenticated callers are keyed by user_id so NAT'd campuses share nothing;
    anonymous callers fall back to client IP. Health endpoints are excluded.
    """
    state = get_app_state(request)
    user = getattr(request.state, "user", None)
    identity = f"user:{user.user_id}" if user else f"ip:{_client_ip(request)}"
    await state.rate_limiter.check(state.databases.redis.client, identity)


async def enforce_auth_rate_limit(request: Request) -> None:
    """Dedicated, stricter throttle for anonymous credential endpoints.

    Keyed by client IP (with the same proxy-header caution as the global
    limiter) because these routes are unauthenticated by design; the
    per-account failed-login lock in AuthService complements this per IP.
    """
    state = get_app_state(request)
    identity = f"auth:{_client_ip(request)}"
    await state.auth_rate_limiter.check(state.databases.redis.client, identity)


def _client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when an operator has put a proxy in front;
    # otherwise a client could forge the header to escape its own limit.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and request.app.state.settings.trust_proxy_headers:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def dumps(value) -> str:
    return json.dumps(value, default=str)
