from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.errors import AuthenticationError
from app.core.logging import utc_now_iso

_BCRYPT_ROUNDS = 12

TokenType = Literal["access", "refresh", "password_reset"]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _token(
    subject: str,
    token_type: TokenType,
    secret: str,
    lifetime: timedelta,
    *,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": "nexora",
    }
    if extra:
        claims.update(extra)
    return jwt.encode(claims, secret, algorithm="HS256")


def create_access_token(
    subject: str, secret: str, *, role: str, minutes: int
) -> tuple[str, str]:
    """Returns (token, jti)."""
    token = _token(
        subject, "access", secret, timedelta(minutes=minutes), extra={"role": role}
    )
    return token, _jti_of(token, secret)


def create_refresh_token(subject: str, secret: str, *, days: int) -> tuple[str, str]:
    token = _token(subject, "refresh", secret, timedelta(days=days))
    return token, _jti_of(token, secret)


def create_password_reset_token(subject: str, secret: str, *, minutes: int = 30) -> str:
    return _token(subject, "password_reset", secret, timedelta(minutes=minutes))


def _jti_of(token: str, secret: str) -> str:
    return decode_token(token, secret, expected_type=None)["jti"]


def decode_token(
    token: str, secret: str, *, expected_type: TokenType | None
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer="nexora")
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token", code="token_invalid") from exc
    if expected_type is not None and payload.get("typ") != expected_type:
        raise AuthenticationError("Invalid token type", code="token_invalid")
    return payload


def new_jti() -> str:
    return uuid.uuid4().hex


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def token_fingerprint(token: str) -> str:
    """Stable hash of a token for server-side storage (never store raw tokens)."""
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return utc_now_iso()
