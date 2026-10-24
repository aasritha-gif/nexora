from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorDatabase

log = logging.getLogger(__name__)


class SessionStore:
    """Refresh-token sessions.

    Primary store: Redis (TTL-managed, fast revocation). Mirror: MongoDB
    `sessions` with a TTL index so refresh tokens survive Redis restarts and
    still work when Redis is degraded.
    """

    def __init__(self, redis: aioredis.Redis | None, db: AsyncIOMotorDatabase):
        self.redis = redis
        self.db = db

    async def create(
        self,
        *,
        user_id: str,
        refresh_jti: str,
        token_fingerprint: str,
        ttl_seconds: int,
        remember_me: bool = False,
    ) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        payload = {
            "user_id": user_id,
            "fingerprint": token_fingerprint,
            "remember_me": remember_me,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "revoked": False,
        }
        try:
            if self.redis is not None:
                await self.redis.setex(
                    f"session:{user_id}:{refresh_jti}", ttl_seconds, token_fingerprint
                )
        except Exception:
            log.warning(
                "Redis session write failed (Mongo mirror in effect)",
                extra={"event": "session_redis_unavailable", "user_id": user_id},
            )
        await self.db.sessions.update_one(
            {"user_id": user_id, "jti": refresh_jti},
            {"$set": {**payload, "jti": refresh_jti}},
            upsert=True,
        )

    async def validate(
        self, *, user_id: str, refresh_jti: str, token_fingerprint: str
    ) -> bool:
        if self.redis is not None:
            try:
                stored = await self.redis.get(f"session:{user_id}:{refresh_jti}")
                if stored is not None:
                    return stored == token_fingerprint
                # Absent in Redis: fall through to Mongo (Redis may have flushed).
            except Exception:
                log.warning(
                    "Redis session read failed; using Mongo mirror",
                    extra={"event": "session_redis_unavailable", "user_id": user_id},
                )
        doc = await self.db.sessions.find_one(
            {"user_id": user_id, "jti": refresh_jti, "revoked": False}
        )
        if not doc:
            return False
        if doc.get("expires_at") and doc["expires_at"] <= datetime.now(timezone.utc):
            return False
        return doc.get("fingerprint") == token_fingerprint

    async def revoke(self, *, user_id: str, refresh_jti: str) -> None:
        if self.redis is not None:
            try:
                await self.redis.delete(f"session:{user_id}:{refresh_jti}")
            except Exception:
                pass
        await self.db.sessions.update_one(
            {"user_id": user_id, "jti": refresh_jti},
            {"$set": {"revoked": True}},
        )

    async def revoke_all_for_user(self, user_id: str) -> int:
        removed = 0
        if self.redis is not None:
            try:
                keys = await self.redis.keys(f"session:{user_id}:*")
                if keys:
                    removed = await self.redis.delete(*keys)
            except Exception:
                pass
        result = await self.db.sessions.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {"revoked": True}},
        )
        return max(removed, result.modified_count)

    async def rotate(
        self,
        *,
        user_id: str,
        old_jti: str,
        new_jti: str,
        token_fingerprint: str,
        ttl_seconds: int,
    ) -> None:
        """Revoke the presented refresh token and issue a new session."""
        await self.revoke(user_id=user_id, refresh_jti=old_jti)
        await self.create(
            user_id=user_id,
            refresh_jti=new_jti,
            token_fingerprint=token_fingerprint,
            ttl_seconds=ttl_seconds,
        )
