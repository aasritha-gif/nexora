from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Role(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    ADMIN = "admin"


class User(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    email: str = Field(..., description="Lowercased email; unique")
    student_id: str | None = None
    name: str
    password_hash: str = Field(exclude=True, repr=False)
    role: Role = Role.STUDENT
    department_code: str | None = None
    academic_year: int | None = Field(default=None, ge=1, le=8)
    semester: int | None = Field(default=None, ge=1, le=10)
    is_active: bool = True
    # Access tokens issued before this instant are rejected outright. Bumped on
    # password change, role change, deactivation and "log out everywhere" so
    # privilege-affecting events take effect without waiting for token expiry.
    tokens_invalid_before: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile: dict = Field(default_factory=dict)

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()


class UserPublic(BaseModel):
    user_id: str
    email: str
    student_id: str | None
    name: str
    role: Role
    department_code: str | None
    academic_year: int | None
    semester: int | None
    created_at: datetime


def to_public(user: User) -> UserPublic:
    return UserPublic(**user.model_dump(exclude={"password_hash"}))
