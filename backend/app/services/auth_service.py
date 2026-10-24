from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    RateLimitExceededError,
)
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_fingerprint,
    verify_password,
)
from app.models.user import Role, User
from app.repositories.sessions import SessionStore
from app.repositories.users import UserRepository
from app.schemas.auth import AuthResponse, TokenPair

log = logging.getLogger(__name__)

RESET_TOKEN_MINUTES = 30
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 300
_LOGIN_FAILURE_MAP_LIMIT = 10_000


class AuthService:
    def __init__(
        self,
        settings: Settings,
        users: UserRepository,
        sessions: SessionStore,
        db: AsyncIOMotorDatabase,
        email_sender=None,
    ):
        self.settings = settings
        self.users = users
        self.sessions = sessions
        self.db = db
        self.email_sender = email_sender  # EmailSender | None
        # identifier -> (consecutive failures, lock expiry epoch). In-memory by
        # design: this is a brute-force speed bump, not a durable lockout — the
        # dedicated auth limiter (per IP) covers the multi-process case.
        self._login_failures: dict[str, tuple[int, float]] = {}

    async def register(self, data) -> User:
        if await self.users.get_by_email(data.email):
            raise ConflictError("An account with this email already exists")
        if await self.users.get_by_student_id(data.student_id):
            raise ConflictError("An account with this student ID already exists")
        if not await self._department_exists(data.department_code):
            raise InvalidInputError(f"Unknown department code: {data.department_code}")

        user_id = await self.users.new_user_id()
        user = User(
            user_id=user_id,
            email=User.normalize_email(str(data.email)),
            student_id=data.student_id.strip(),
            name=data.name.strip(),
            password_hash=hash_password(data.password),
            role=Role.STUDENT,  # self-service registration never grants elevated roles
            department_code=data.department_code.upper(),
            academic_year=data.academic_year,
            semester=data.semester,
        )
        user = await self.users.create(user)
        return user

    async def login(self, identifier: str, password: str, *, remember_me: bool) -> AuthResponse:
        key = identifier.strip().lower()
        failures, locked_until = self._login_failures.get(key, (0, 0.0))
        if time.time() < locked_until:
            raise RateLimitExceededError("Too many failed attempts — try again later")

        user = await self.users.get_by_login_identifier(identifier)
        if user is None or not verify_password(password, user.password_hash):
            self._record_login_failure(key)
            # Uniform message — never reveal which field failed.
            raise AuthenticationError("Invalid credentials")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        self._login_failures.pop(key, None)
        tokens = await self._issue_tokens(user, remember_me=remember_me)
        return AuthResponse(tokens=tokens, user=_to_response(user))

    def _record_login_failure(self, key: str) -> None:
        failures, _ = self._login_failures.get(key, (0, 0.0))
        failures += 1
        locked_until = 0.0
        if failures >= LOGIN_MAX_FAILURES:
            locked_until = time.time() + LOGIN_LOCK_SECONDS
            log.warning(
                "Login temporarily locked after repeated failures",
                extra={"event": "login_locked", "identifier": key[:64]},
            )
        self._login_failures[key] = (failures, locked_until)
        if len(self._login_failures) > _LOGIN_FAILURE_MAP_LIMIT:
            # Bound memory: drop entries that are not actively locked.
            now = time.time()
            self._login_failures = {
                k: v for k, v in self._login_failures.items() if v[1] > now
            }

    async def refresh(self, refresh_token: str) -> AuthResponse:
        secret = self.settings.effective_secret_key()
        payload = decode_token(refresh_token, secret, expected_type="refresh")
        user_id = payload.get("sub")
        jti = payload.get("jti", "")
        fingerprint = token_fingerprint(refresh_token)
        if not user_id:
            raise AuthenticationError("Invalid refresh token")
        valid = await self.sessions.validate(
            user_id=user_id, refresh_jti=jti, token_fingerprint=fingerprint
        )
        if not valid:
            raise AuthenticationError("Refresh token is revoked or expired")
        try:
            user = await self.users.get_by_id(user_id)
        except NotFoundError as exc:
            raise AuthenticationError("User no longer exists") from exc
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        new_refresh, new_jti = create_refresh_token(
            user.user_id, secret, days=self.settings.refresh_token_days
        )
        await self.sessions.rotate(
            user_id=user.user_id,
            old_jti=jti,
            new_jti=new_jti,
            token_fingerprint=token_fingerprint(new_refresh),
            ttl_seconds=self.settings.refresh_token_days * 86400,
        )
        access, _ = create_access_token(
            user.user_id, secret, role=user.role.value,
            minutes=self.settings.access_token_minutes,
        )
        tokens = TokenPair(
            access_token=access,
            refresh_token=new_refresh,
            expires_in=self.settings.access_token_minutes * 60,
        )
        return AuthResponse(tokens=tokens, user=_to_response(user))

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        secret = self.settings.effective_secret_key()
        try:
            payload = decode_token(refresh_token, secret, expected_type="refresh")
        except AuthenticationError:
            return
        await self.sessions.revoke(
            user_id=payload.get("sub", ""), refresh_jti=payload.get("jti", "")
        )

    async def logout_all(self, user_id: str) -> int:
        await self.users.invalidate_tokens(user_id)
        return await self.sessions.revoke_all_for_user(user_id)

    async def resolve_access_token(self, token: str) -> User:
        """Validate a bearer access token against live account state.

        The token proves identity; MongoDB remains authoritative for role and
        active status, and `tokens_invalid_before` short-circuits any token
        minted before a password change, role change, or global logout.
        """
        payload = decode_token(
            token, self.settings.effective_secret_key(), expected_type="access"
        )
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid access token", code="token_invalid")
        try:
            user = await self.users.get_by_id(user_id)
        except NotFoundError as exc:
            raise AuthenticationError("Account no longer exists") from exc
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        invalidated = user.tokens_invalid_before
        issued_at = payload.get("iat")
        if invalidated is not None and issued_at is not None:
            if isinstance(invalidated, datetime):
                if invalidated.tzinfo is None:
                    invalidated = invalidated.replace(tzinfo=timezone.utc)
                issued_epoch = int(invalidated.timestamp())
            else:
                issued_epoch = int(invalidated)
            if int(issued_at) < issued_epoch:
                raise AuthenticationError(
                    "Session expired — please sign in again", code="token_expired"
                )
        return user

    async def request_password_reset(self, email: str) -> None:
        """Always succeeds from the caller's view (no account enumeration)."""
        user = await self.users.get_by_email(email)
        if user is None:
            log.info(
                "Password reset requested for unknown email",
                extra={"event": "reset_unknown_email"},
            )
            return
        token = create_password_reset_token(
            user.user_id, self.settings.effective_secret_key(), minutes=RESET_TOKEN_MINUTES
        )
        expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_MINUTES)
        await self.db.password_resets.update_one(
            {"user_id": user.user_id},
            {"$set": {"token_hash": token_fingerprint(token), "expires_at": expires,
                      "used": False}},
            upsert=True,
        )
        if self.email_sender is not None:
            await self.email_sender.send_reset(user.email, user.name, token)
        elif self.settings.environment != "production":
            # No SMTP configured: development mode surfaces the link in logs
            # only. A truncated prefix is enough to correlate; the full token
            # is a live credential and must never reach logs.
            log.warning(
                "Password reset requested but SMTP is not configured. "
                "Reset link (dev only): /auth/reset?token=%s…",
                token[:8],
                extra={"event": "reset_dev_link", "user_id": user.user_id},
            )
        else:
            log.warning(
                "Password reset requested but SMTP is not configured; no email sent",
                extra={"event": "reset_no_smtp", "user_id": user.user_id},
            )

    async def reset_password(self, reset_token: str, new_password: str) -> None:
        secret = self.settings.effective_secret_key()
        payload = decode_token(reset_token, secret, expected_type="password_reset")
        user_id = payload.get("sub", "")
        record = await self.db.password_resets.find_one({"user_id": user_id})
        if (
            not record
            or record.get("used")
            or record.get("token_hash") != token_fingerprint(reset_token)
            or record.get("expires_at", datetime.now(timezone.utc) - timedelta(seconds=1))
            <= datetime.now(timezone.utc)
        ):
            raise AuthenticationError("Reset link is invalid or has expired")
        await self.users.update_password(user_id, hash_password(new_password))
        await self.db.password_resets.update_one(
            {"user_id": user_id}, {"$set": {"used": True}}
        )
        await self.sessions.revoke_all_for_user(user_id)
        log.info("Password reset completed", extra={"event": "password_reset", "user_id": user_id})

    async def change_password(self, user_id: str, current: str, new: str) -> None:
        user = await self.users.get_by_id(user_id)
        if not verify_password(current, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        await self.users.update_password(user_id, hash_password(new))
        await self.sessions.revoke_all_for_user(user_id)

    async def _issue_tokens(self, user: User, *, remember_me: bool) -> TokenPair:
        secret = self.settings.effective_secret_key()
        refresh_days = (
            self.settings.refresh_token_days * 4 if remember_me
            else self.settings.refresh_token_days
        )
        access, _ = create_access_token(
            user.user_id, secret, role=user.role.value,
            minutes=self.settings.access_token_minutes,
        )
        refresh, jti = create_refresh_token(user.user_id, secret, days=refresh_days)
        await self.sessions.create(
            user_id=user.user_id,
            refresh_jti=jti,
            token_fingerprint=token_fingerprint(refresh),
            ttl_seconds=refresh_days * 86400,
            remember_me=remember_me,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.settings.access_token_minutes * 60,
        )

    async def _department_exists(self, code: str) -> bool:
        return await self.db.departments.find_one({"code": code.upper()}) is not None


def _to_response(user: User):
    from app.schemas.auth import UserResponse

    return UserResponse(**user.model_dump(exclude={"password_hash"}))
