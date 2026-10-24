from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import Role, User
from app.repositories.counters import next_id

log = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users

    async def new_user_id(self) -> str:
        return await next_id(self.db, "user")

    async def create(self, user: User) -> User:
        try:
            await self.collection.insert_one(_document(user))
        except DuplicateKeyError as exc:
            field = "email" if "email" in str(exc) else "student ID"
            raise ConflictError(f"A user with this {field} already exists") from exc
        log.info(
            "User created",
            extra={"event": "user_created", "user_id": user.user_id},
        )
        return user

    async def get_by_email(self, email: str) -> User | None:
        doc = await self.collection.find_one({"email": User.normalize_email(email)})
        return User(**doc) if doc else None

    async def get_by_student_id(self, student_id: str) -> User | None:
        doc = await self.collection.find_one({"student_id": student_id})
        return User(**doc) if doc else None

    async def get_by_login_identifier(self, identifier: str) -> User | None:
        lowered = identifier.strip().lower()
        user = await self.get_by_email(lowered)
        if user is None:
            user = await self.get_by_student_id(identifier.strip())
        return user

    async def get_by_id(self, user_id: str) -> User:
        doc = await self.collection.find_one({"user_id": user_id})
        if not doc:
            raise NotFoundError("User not found")
        return User(**doc)

    async def update_password(self, user_id: str, new_password_hash: str) -> None:
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "password_hash": new_password_hash,
                "tokens_invalid_before": _now(),
                "updated_at": _now(),
            }},
        )
        if result.modified_count == 0:
            raise NotFoundError("User not found")

    async def invalidate_tokens(self, user_id: str) -> None:
        """Reject every access token issued before now for this user."""
        await self.collection.update_one(
            {"user_id": user_id}, {"$set": {"tokens_invalid_before": _now()}}
        )

    async def update_profile(self, user_id: str, fields: dict) -> User:
        allowed = {k: v for k, v in fields.items() if k in {
            "name", "department_code", "academic_year", "semester", "profile"
        }}
        doc = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": {**allowed, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("User not found")
        return User(**doc)

    async def set_role(self, user_id: str, role: Role) -> User:
        doc = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": {
                "role": role.value,
                "tokens_invalid_before": _now(),
                "updated_at": _now(),
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("User not found")
        return User(**doc)

    async def set_active(self, user_id: str, active: bool) -> User:
        doc = await self.collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": {
                "is_active": active,
                "tokens_invalid_before": _now(),
                "updated_at": _now(),
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise NotFoundError("User not found")
        return User(**doc)

    async def list_users(
        self, *, page: int = 1, page_size: int = 20, search: str = "", role: Role | None = None
    ) -> tuple[list[User], int]:
        query: dict = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": _escape(search), "$options": "i"}},
                {"email": {"$regex": _escape(search), "$options": "i"}},
                {"student_id": {"$regex": _escape(search), "$options": "i"}},
            ]
        if role:
            query["role"] = role.value
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        users = [User(**doc) async for doc in cursor]
        return users, total

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def count_active_admins(self) -> int:
        return await self.collection.count_documents(
            {"role": Role.ADMIN.value, "is_active": True}
        )

    async def ensure_admin(self, email: str, password: str) -> User | None:
        """Create the bootstrap admin if no admin exists. Returns created user."""
        if await self.collection.find_one({"role": Role.ADMIN.value}):
            return None
        user_id = await next_id(self.db, "user")
        user = User(
            user_id=user_id,
            email=User.normalize_email(email),
            name="NEXORA Administrator",
            password_hash=hash_password(password),
            role=Role.ADMIN,
            department_code=None,
        )
        await self.collection.insert_one(_document(user))
        log.warning(
            "Bootstrap admin created (first boot only): %s", email,
            extra={"event": "admin_bootstrap", "user_id": user_id},
        )
        return user


def _document(user: User) -> dict:
    """`password_hash` carries Field(exclude=True) so it can never leak through a
    generic model_dump() into an API response — persistence re-attaches it."""
    return {**user.model_dump(), "password_hash": user.password_hash}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("$", "\\$").replace("^", "\\^")


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
