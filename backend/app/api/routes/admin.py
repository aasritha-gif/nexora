from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.dependencies import AppState, get_app_state, require_role
from app.core.errors import ConflictError, InvalidInputError, NotFoundError
from app.core.logging import get_logger
from app.models.resource import AccessType, AcademicLevel, Difficulty
from app.models.user import Role, User
from app.schemas.ingestion import AdminOverviewResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_role(Role.ADMIN)


class AdminUserResponse(BaseModel):
    user_id: str
    email: str
    student_id: str | None
    name: str
    role: Role
    department_code: str | None
    academic_year: int | None
    semester: int | None
    is_active: bool
    created_at: datetime


class RoleUpdateRequest(BaseModel):
    role: Role


class ActiveUpdateRequest(BaseModel):
    is_active: bool


class ModerationRequest(BaseModel):
    remove: bool = True
    reason: str | None = Field(default=None, max_length=300)


class ClassificationUpdateRequest(BaseModel):
    department_code: str | None = Field(default=None, max_length=8)
    subject_codes: list[str] | None = Field(default=None, max_length=12)
    topic_codes: list[str] | None = Field(default=None, max_length=20)
    difficulty: Difficulty | None = None
    academic_level: AcademicLevel | None = None
    semester: int | None = Field(default=None, ge=1, le=10)
    keywords: list[str] | None = Field(default=None, max_length=24)


class AccessUpdateRequest(BaseModel):
    access: AccessType
    premium_price_usd: float | None = Field(default=None, ge=0.5, le=10000)


# ── overview & monitoring ─────────────────────────────


@router.get("/overview", response_model=AdminOverviewResponse)
async def overview(
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    total = await state.resources.count()
    seed = await state.resources.seed_count()
    return AdminOverviewResponse(
        total_resources=total,
        total_users=await state.users.count(),
        resources_by_type=await state.resources.counts_by_type(),
        resources_by_department=await state.resources.counts_by_department(),
        seed_resources=seed,
        discovered_resources=max(total - seed, 0),
        flagged_reviews=len(await state.reviews.flagged()),
        analytics=await _analytics_block(state),
    )


@router.get("/databases")
async def databases(
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    """Live adapter status. Reasons are already credential-stripped."""
    await state.databases.refresh_health()
    return state.databases.status()


@router.get("/system")
async def system(
    request: Request,
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    import time as _time

    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = round(_time.time() - started_at, 1) if started_at is not None else None
    return {
        "app_name": state.settings.app_name,
        "version": state.settings.app_version,
        "uptime_seconds": uptime_seconds,
        "configuration": state.settings.safe_summary(),
        "rate_limit": {
            "requests": state.settings.rate_limit_requests,
            "window_seconds": state.settings.rate_limit_window_seconds,
        },
        "auth_rate_limit": {
            "requests": state.settings.auth_rate_limit_requests,
            "window_seconds": state.settings.auth_rate_limit_window_seconds,
        },
        "sync": {
            "enabled": state.settings.sync_enabled,
            "interval_minutes": state.settings.sync_interval_minutes,
        },
        "ai": await state.ai_service.status(),
        "payments": state.payments.status(),
        "analytics_buffer": {
            "pending_events": state.analytics.pending,
            "flush_threshold": state.analytics.flush_threshold,
        },
    }


# ── user management ───────────────────────────────────


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default="", max_length=120),
    role: Role | None = None,
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    users, total = await state.users.list_users(
        page=page, page_size=page_size, search=search.strip(), role=role
    )
    return {
        "items": [AdminUserResponse.model_validate(u.model_dump()) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
async def change_role(
    user_id: str,
    data: RoleUpdateRequest,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    target = await state.users.get_by_id(user_id)
    if target.user_id == admin.user_id and data.role is not Role.ADMIN:
        raise ConflictError("You cannot remove your own administrator role")
    demoting_admin = target.role is Role.ADMIN and data.role is not Role.ADMIN
    if (demoting_admin or not target.is_active) and await _is_last_admin(state, target):
        raise ConflictError("At least one active administrator must remain")
    updated = await state.users.set_role(user_id, data.role)
    logger.info("admin_role_changed", target=user_id, by=admin.user_id, role=data.role.value)
    await _sync_graph_user(state, updated)
    return AdminUserResponse.model_validate(updated.model_dump())


@router.patch("/users/{user_id}/active", response_model=AdminUserResponse)
async def change_active(
    user_id: str,
    data: ActiveUpdateRequest,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    target = await state.users.get_by_id(user_id)
    if target.user_id == admin.user_id and not data.is_active:
        raise ConflictError("You cannot deactivate your own account")
    if target.role is Role.ADMIN and not data.is_active and await _is_last_admin(state, target):
        raise ConflictError("At least one active administrator must remain")
    updated = await state.users.set_active(user_id, data.is_active)
    revoked = 0
    if not data.is_active:
        try:
            revoked = await state.sessions.revoke_all_for_user(user_id)
        except Exception as exc:  # noqa: BLE001 - Redis down must not block the action
            logger.warning("session_revoke_failed", user=user_id, reason=exc.__class__.__name__)
    logger.info("admin_account_status_changed", target=user_id, by=admin.user_id,
                is_active=data.is_active, sessions_revoked=revoked)
    await _sync_graph_user(state, updated)
    return AdminUserResponse.model_validate(updated.model_dump())


# ── review moderation ─────────────────────────────────


@router.get("/reviews/flagged")
async def flagged_reviews(
    state: AppState = Depends(get_app_state),
    _: User = Depends(admin_only),
):
    reviews = await state.reviews.flagged()
    names = await _user_names(state, {r.user_id for r in reviews})
    titles = await _resource_titles(state, {r.resource_id for r in reviews})
    return [
        {
            "review_id": r.review_id,
            "user_id": r.user_id,
            "user_name": names.get(r.user_id),
            "resource_id": r.resource_id,
            "resource_title": titles.get(r.resource_id),
            "rating": r.rating,
            "title": r.title,
            "body": r.body,
            "status": r.status,
            "moderated_reason": r.moderated_reason,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


@router.post("/reviews/{review_id}/flag")
async def flag_review(
    review_id: str,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    review = await state.reviews.flag(review_id)
    logger.info("review_flagged", review_id=review_id, by=admin.user_id)
    return {"review_id": review.review_id, "status": review.status}


@router.post("/reviews/{review_id}/moderate")
async def moderate_review(
    review_id: str,
    data: ModerationRequest,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    if data.remove and not (data.reason or "").strip():
        raise InvalidInputError("A reason is required when removing a review")
    review = await state.reviews.moderate(
        review_id, remove=data.remove, reason=(data.reason or "").strip() or None
    )
    rating_sum, rating_count = await state.reviews.refresh_resource_rating(review.resource_id)
    await _invalidate_resource_cache(state, review.resource_id)
    logger.info("review_moderated", review_id=review_id, by=admin.user_id,
                removed=data.remove, resource_id=review.resource_id)
    return {
        "review_id": review.review_id,
        "status": review.status,
        "resource_id": review.resource_id,
        "rating_sum": rating_sum,
        "rating_count": rating_count,
    }


# ── classification correction ─────────────────────────


@router.patch("/resources/{resource_id}/classification")
async def correct_classification(
    resource_id: str,
    data: ClassificationUpdateRequest,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    resource = await _require_resource(state, resource_id)
    fields: dict[str, Any] = {}

    taxonomy_patch: dict[str, Any] = {}
    if data.department_code is not None:
        code = data.department_code.strip().upper()
        if not await state.taxonomy.department_exists(code):
            raise NotFoundError(f"Department '{code}' does not exist")
        taxonomy_patch["department_code"] = code
    if data.subject_codes is not None:
        subjects = [s.strip().upper() for s in data.subject_codes if s and s.strip()]
        for code in subjects:
            if not await state.taxonomy.subject_exists(code):
                raise NotFoundError(f"Subject '{code}' does not exist")
        taxonomy_patch["subject_codes"] = subjects
    if data.topic_codes is not None:
        topics = [t.strip().upper() for t in data.topic_codes if t and t.strip()]
        for code in topics:
            if not await state.taxonomy.topic_exists(code):
                raise NotFoundError(f"Topic '{code}' does not exist")
        taxonomy_patch["topic_codes"] = topics
    if taxonomy_patch:
        fields["taxonomy"] = {**resource.taxonomy.model_dump(), **taxonomy_patch}

    classification_patch: dict[str, Any] = {
        "method": "admin",
        "confidence": 1.0,
        "notes": f"Corrected by administrator {admin.user_id}",
    }
    if data.difficulty is not None:
        classification_patch["difficulty"] = data.difficulty.value
    if data.academic_level is not None:
        classification_patch["academic_level"] = data.academic_level.value
    if data.semester is not None:
        classification_patch["semester"] = data.semester
    fields["classification"] = {**resource.classification.model_dump(), **classification_patch}

    if data.keywords is not None:
        keywords = [k.strip().lower()[:60] for k in data.keywords if k and k.strip()]
        fields["keywords"] = list(dict.fromkeys(keywords))[:24]

    updated = await state.resources.update_fields(resource_id, fields)
    if updated is None:
        raise NotFoundError(f"Resource '{resource_id}' was not found")
    await _invalidate_resource_cache(state, resource_id)
    await _safe_graph_sync(state, updated)
    logger.info("resource_reclassified", resource_id=resource_id, by=admin.user_id,
                department=updated.taxonomy.department_code)
    return {
        "resource_id": resource_id,
        "taxonomy": updated.taxonomy.model_dump(),
        "classification": updated.classification.model_dump(),
        "keywords": updated.keywords,
    }


@router.patch("/resources/{resource_id}/access")
async def change_access(
    resource_id: str,
    data: AccessUpdateRequest,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    resource = await _require_resource(state, resource_id)
    if (
        data.access is AccessType.PREMIUM
        and data.premium_price_usd is None
        and not resource.premium_price_usd
    ):
        raise InvalidInputError("Set premium_price_usd when marking a resource as premium")
    fields: dict[str, Any] = {"access": data.access.value}
    if data.premium_price_usd is not None:
        fields["premium_price_usd"] = data.premium_price_usd
    elif data.access is AccessType.FREE:
        fields["premium_price_usd"] = None
    updated = await state.resources.update_fields(resource_id, fields)
    if updated is None:
        raise NotFoundError(f"Resource '{resource_id}' was not found")
    await _invalidate_resource_cache(state, resource_id)
    await _safe_graph_sync(state, updated)
    logger.info("resource_access_changed", resource_id=resource_id, by=admin.user_id,
                access=data.access.value)
    return {
        "resource_id": resource_id,
        "access": updated.access.value,
        "premium_price_usd": updated.premium_price_usd,
    }


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    state: AppState = Depends(get_app_state),
    admin: User = Depends(admin_only),
):
    await _require_resource(state, resource_id)
    await state.resources.delete(resource_id)
    try:
        await state.graph.delete_resource(resource_id)
    except Exception as exc:  # noqa: BLE001 - graph lag must not fail the deletion
        logger.warning("graph_delete_failed", resource_id=resource_id,
                       reason=exc.__class__.__name__)
    await state.cache.delete_prefix(f"resource:{resource_id}")
    await state.cache.delete_prefix("home:")
    await state.cache.delete_prefix("search:v1:")
    logger.warning("admin_resource_deleted", resource_id=resource_id, by=admin.user_id)
    return {"deleted": True, "resource_id": resource_id}


# ── helpers ───────────────────────────────────────────


async def _analytics_block(state: AppState) -> dict[str, Any]:
    if not state.databases.monetdb.available:
        return {
            "available": False,
            "reason": state.databases.monetdb.reason or "analytics database not connected",
            "pending_events": state.analytics.pending,
        }
    try:
        summary = await state.analytics.summary()
    except Exception as exc:  # noqa: BLE001 - a degraded warehouse is not an admin 500
        logger.warning("admin_analytics_failed", reason=exc.__class__.__name__)
        return {"available": False, "reason": "analytics query failed",
                "pending_events": state.analytics.pending}
    return {"available": True, "reason": None, "pending_events": state.analytics.pending,
            **summary}


async def _is_last_admin(state: AppState, target: User) -> bool:
    return target.is_active and await state.users.count_active_admins() <= 1


async def _require_resource(state: AppState, resource_id: str):
    try:
        return await state.resources.get(resource_id)
    except NotFoundError:
        raise NotFoundError(f"Resource '{resource_id}' was not found")


async def _user_names(state: AppState, user_ids: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for user_id in user_ids:
        try:
            names[user_id] = (await state.users.get_by_id(user_id)).name
        except NotFoundError:
            continue
    return names


async def _resource_titles(state: AppState, resource_ids: set[str]) -> dict[str, str]:
    if not resource_ids:
        return {}
    resources = await state.resources.get_many(list(resource_ids))
    return {r.resource_id: r.title for r in resources}


async def _invalidate_resource_cache(state: AppState, resource_id: str) -> None:
    await state.cache.delete(f"resource:{resource_id}", f"resource:detail:{resource_id}")
    await state.cache.delete_prefix("home:")
    await state.cache.delete_prefix("search:v1:")


async def _safe_graph_sync(state: AppState, resource) -> None:
    if not state.graph.available:
        return
    try:
        await state.graph.upsert_resource(
            resource_id=resource.resource_id,
            title=resource.title,
            type=resource.type.value,
            access=resource.access.value,
            year=resource.year,
            department_code=resource.taxonomy.department_code,
            subject_codes=resource.taxonomy.subject_codes,
            topic_codes=resource.taxonomy.topic_codes,
            source_name=resource.source.name if resource.source else None,
        )
    except Exception as exc:  # noqa: BLE001 - graph is advisory
        logger.warning("graph_sync_failed", resource_id=resource.resource_id,
                       reason=exc.__class__.__name__)


async def _sync_graph_user(state: AppState, user: User) -> None:
    if not state.graph.available:
        return
    try:
        await state.graph.sync_user(
            user_id=user.user_id, department_code=user.department_code, role=user.role.value
        )
    except Exception as exc:  # noqa: BLE001 - graph is advisory
        logger.warning("graph_user_sync_failed", user_id=user.user_id,
                       reason=exc.__class__.__name__)
