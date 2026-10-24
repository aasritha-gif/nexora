from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    student_id: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9\-]+$")
    email: str = Field(..., min_length=3, max_length=254)
    department_code: str = Field(..., min_length=2, max_length=8)
    academic_year: int = Field(..., ge=1, le=8)
    semester: int = Field(..., ge=1, le=10)
    password: str = Field(..., min_length=10, max_length=128)
    # No role field: registration always creates a student account. Role
    # changes go through the admin surface only.


class LoginRequest(BaseModel):
    identifier: str = Field(
        ...,
        min_length=3,
        max_length=254,
        description="Email or student ID",
    )
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = False


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    tokens: TokenPair
    user: "UserResponse"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    student_id: str | None
    name: str
    role: Role
    department_code: str | None
    academic_year: int | None
    semester: int | None
    created_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10, max_length=128)


class MessageResponse(BaseModel):
    message: str


AuthResponse.model_rebuild()
