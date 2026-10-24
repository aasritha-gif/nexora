from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    DatabaseUnavailableError,
    NexoraError,
    NotFoundError,
    error_body,
    register_exception_handlers,
)


class _Payload(BaseModel):
    name: str


def _build_app() -> FastAPI:
    import logging

    app = FastAPI()
    app.state.logger = logging.getLogger("nexora-test")
    register_exception_handlers(app)

    @app.get("/not-found")
    async def _not_found():
        raise NotFoundError("No such resource")

    @app.get("/unavailable")
    async def _unavailable():
        raise DatabaseUnavailableError("Neo4j")

    @app.get("/http")
    async def _http():
        raise HTTPException(status_code=404, detail="gone")

    @app.post("/validated")
    async def _validated(_: _Payload):
        return {"ok": True}

    @app.get("/boom")
    async def _boom():
        raise ValueError("programmer error")

    return app


client = TestClient(_build_app(), raise_server_exceptions=False)


class TestErrorBody:
    def test_shape(self):
        body = error_body("some_code", "Some message")
        assert body == {"error": {"code": "some_code", "message": "Some message"}}

    def test_details_included_only_when_present(self):
        assert "details" not in error_body("c", "m")
        assert error_body("c", "m", details=[1])["error"]["details"] == [1]


class TestHandlers:
    def test_domain_error_status_and_code(self):
        resp = client.get("/not-found")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
        assert resp.json()["error"]["message"] == "No such resource"

    def test_database_unavailable_is_503_with_specific_code(self):
        resp = client.get("/unavailable")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "database_unavailable"
        assert "Neo4j" in resp.json()["error"]["message"]

    def test_plain_http_exception_wrapped(self):
        resp = client.get("/http")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "http_error"

    def test_validation_error_carries_details(self):
        resp = client.post("/validated", json={"name": 42})
        assert resp.status_code == 422
        body = resp.json()["error"]
        assert body["code"] == "validation_error"
        assert body["details"]

    def test_unhandled_exception_becomes_generic_500(self):
        resp = client.get("/boom")
        assert resp.status_code == 500
        body = resp.json()["error"]
        assert body["code"] == "internal_error"
        assert "ValueError" not in resp.text  # traceback stays in server logs


class TestHierarchy:
    def test_database_unavailable_inherits_service_unavailable(self):
        assert issubclass(DatabaseUnavailableError, NexoraError)
        assert DatabaseUnavailableError("X").status_code == 503
