from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    AppState,
    enforce_auth_rate_limit,
    get_app_state,
    get_current_user,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    data: RegisterRequest,
    state: AppState = Depends(get_app_state),
    _: None = Depends(enforce_auth_rate_limit),
):
    user = await state.auth.register(data)
    response = await state.auth.login(
        data.email, data.password, remember_me=False
    )
    log.info("Registration complete", extra={"event": "registered", "user_id": user.user_id})
    return response


@router.post("/login", response_model=AuthResponse)
async def login(
    data: LoginRequest,
    state: AppState = Depends(get_app_state),
    _: None = Depends(enforce_auth_rate_limit),
):
    return await state.auth.login(
        data.identifier, data.password, remember_me=data.remember_me
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    data: RefreshRequest,
    state: AppState = Depends(get_app_state),
):
    return await state.auth.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: RefreshRequest | None = None,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    token = data.refresh_token if data else None
    await state.auth.logout(token)
    return MessageResponse(message="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    revoked = await state.auth.logout_all(user.user_id)
    return MessageResponse(message=f"Revoked {revoked} sessions")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    state: AppState = Depends(get_app_state),
    _: None = Depends(enforce_auth_rate_limit),
):
    await state.auth.request_password_reset(str(data.email))
    return MessageResponse(
        message="If an account exists for that email, a reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    state: AppState = Depends(get_app_state),
    _: None = Depends(enforce_auth_rate_limit),
):
    await state.auth.reset_password(data.reset_token, data.new_password)
    return MessageResponse(message="Password updated — please sign in again")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    await state.auth.change_password(user.user_id, data.current_password, data.new_password)
    return MessageResponse(message="Password changed; other sessions were signed out")


@router.get("/departments", response_model=list[dict])
async def registration_departments(state: AppState = Depends(get_app_state)):
    """Active departments for the registration form."""
    departments = await state.taxonomy.list_departments()
    return [{"code": d.code, "name": d.name} for d in departments]
