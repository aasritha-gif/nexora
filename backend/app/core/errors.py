from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class NexoraError(Exception):
    """Base for all domain errors. Rendered as {"error": {"code", "message"}}."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, *, code: str | None = None, details: Any = None):
        if message:
            self.message = message
        if code:
            self.code = code
        self.details = details
        super().__init__(self.message)


class AuthenticationError(NexoraError):
    status_code = 401
    code = "authentication_failed"
    message = "Authentication required"


class AuthorizationError(NexoraError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action"


class NotFoundError(NexoraError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(NexoraError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with existing state"


class InvalidInputError(NexoraError):
    status_code = 422
    code = "invalid_input"
    message = "Invalid input"


class RateLimitExceededError(NexoraError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests — please slow down"


class ServiceUnavailableError(NexoraError):
    status_code = 503
    code = "service_unavailable"
    message = "A required service is currently unavailable"


class DatabaseUnavailableError(ServiceUnavailableError):
    code = "database_unavailable"

    def __init__(self, database: str):
        super().__init__(f"The {database} database is currently unavailable")
        self.database = database


class AIProviderNotConfiguredError(ServiceUnavailableError):
    code = "ai_not_configured"
    message = (
        "AI features are not configured on this deployment. Set NEXORA_AI_PROVIDER "
        "and NEXORA_AI_API_KEY (see docs/setup.md) to enable AI Overview, AI Reading, "
        "and the resource chatbot."
    )


class PaymentProviderNotConfiguredError(ServiceUnavailableError):
    code = "payment_not_configured"
    message = (
        "Premium purchases require a payment provider. Set NEXORA_PAYMENT_PROVIDER=stripe "
        "and NEXORA_STRIPE_SECRET_KEY to enable checkout."
    )


def error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NexoraError)
    async def _nexora_error(_: Request, exc: NexoraError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, getattr(exc, "details", None)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Full traceback goes to structured logs only — never to the client.
        request.app.state.logger.error(
            "Unhandled exception",
            extra={"event": "unhandled_exception"},
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Internal server error"),
        )
