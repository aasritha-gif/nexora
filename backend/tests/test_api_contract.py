from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.api.router import api_router
from app.core.errors import AuthenticationError
from app.main import _is_probe, _request_id

EXPECTED_PREFIXES = {
    "/api/auth",
    "/api/users",
    "/api/resources",
    "/api/home",
    "/api/search",
    "/api/me",
    "/api/ai",
    "/api/youtube",
    "/api/payments",
    "/api/analytics",
    "/api/ingestion",
    "/api/admin",
    # Taxonomy router mounts its public surface at the root:
    "/api/browse",
    "/api/departments",
    "/api/subjects",
    "/api/topics",
    "/api/graph",
}


def _collect_routes(router, prefix: str = "") -> list[tuple[str, tuple[str, ...]]]:
    """(path, methods) pairs — one path may legally serve several methods."""
    routes: list[tuple[str, tuple[str, ...]]] = []
    for route in router.routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            routes.extend(_collect_routes(context.included_router, prefix + context.prefix))
            continue
        sub = getattr(route, "router", None)
        if sub is not None:
            routes.extend(_collect_routes(sub, prefix + route.prefix))
        else:
            path = getattr(route, "path", None)
            if path:
                methods = tuple(sorted(getattr(route, "methods", None) or ()))
                routes.append((prefix + path, methods))
    return routes


class TestRouterComposition:
    def test_all_domain_routers_are_mounted(self):
        paths = [p for p, _ in _collect_routes(api_router, "/api")]
        prefixes = {p for path in paths for p in EXPECTED_PREFIXES if path.startswith(p)}
        assert prefixes == EXPECTED_PREFIXES

    def test_no_duplicate_method_on_same_path(self):
        routes = _collect_routes(api_router, "/api")
        seen: dict[tuple[str, str], None] = {}
        for path, methods in routes:
            for method in methods:
                key = (method, path)
                assert key not in seen, f"duplicate route: {method} {path}"
                seen[key] = None


class TestRequestIdHygiene:
    def _request(self, header_value: str) -> Request:
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-request-id", header_value.encode())] if header_value else [],
        })

    def test_supplied_id_echoed(self):
        assert _request_id(self._request("abc-123")) == "abc-123"

    def test_control_characters_stripped(self):
        rid = _request_id(self._request("a\nb\tc\x07d<script>"))
        assert all(ord(ch) > 32 for ch in rid)
        assert "<" not in rid and ">" not in rid

    def test_length_capped(self):
        assert len(_request_id(self._request("x" * 200))) <= 64

    def test_missing_header_generates_one(self):
        generated = _request_id(self._request(""))
        assert generated


class TestProbePaths:
    def test_health_and_public_paths_are_probes(self):
        for path in ("/", "/docs", "/openapi.json", "/health", "/health/readiness"):
            assert _is_probe(path)

    def test_api_paths_are_logged(self):
        assert not _is_probe("/api/resources")


class TestBearerAuthMiddleware:
    async def test_rejected_token_stored_not_raised(self):
        from types import SimpleNamespace

        from app.main import bearer_auth_middleware

        class FailingAuth:
            async def resolve_access_token(self, _token):
                raise AuthenticationError("Token has expired", code="token_expired")

        app = SimpleNamespace(state=SimpleNamespace(app_state=SimpleNamespace(auth=FailingAuth())))
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/api/resources",
            "headers": [(b"authorization", b"Bearer stale-token")],
            "app": app,
        })

        async def call_next(_):
            return PlainTextResponse("ok")

        response = await bearer_auth_middleware(request, call_next)
        assert response.status_code == 200  # public routes keep working
        assert request.state.user is None
        assert isinstance(request.state.auth_error, AuthenticationError)

    async def test_no_token_leaves_clean_state(self):
        from types import SimpleNamespace

        from app.main import bearer_auth_middleware

        app = SimpleNamespace(state=SimpleNamespace(app_state=None))
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
            "app": app,
        })

        async def call_next(_):
            return PlainTextResponse("ok")

        await bearer_auth_middleware(request, call_next)
        assert request.state.user is None
        assert request.state.auth_error is None
