from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.dependencies import AppState, get_app_state, get_current_user
from app.core.errors import ConflictError, InvalidInputError, PaymentProviderNotConfiguredError
from app.core.logging import get_logger
from app.models.resource import AccessType
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    resource_id: str


@router.get("/status")
async def payment_status(state: AppState = Depends(get_app_state)):
    """Tells the UI whether premium checkout exists at all, so it can show a
    real configuration notice instead of a button that cannot work."""
    return state.payments.status()


@router.post("/checkout")
async def create_checkout(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
    state: AppState = Depends(get_app_state),
):
    if not state.payments.is_configured:
        raise PaymentProviderNotConfiguredError()

    resource = await state.resources.get(data.resource_id)
    if resource.access != AccessType.PREMIUM:
        raise InvalidInputError("This resource is free — no purchase is required")
    if await state.purchases.has_access(user.user_id, resource.resource_id):
        raise ConflictError("You already own access to this resource")

    amount_usd = resource.premium_price_usd or state.settings.premium_default_price_usd
    purchase = await state.purchases.create_pending(
        user_id=user.user_id,
        resource_id=resource.resource_id,
        amount_usd=amount_usd,
        provider=state.payments.name,
    )
    base = state.settings.frontend_url.rstrip("/")
    session = await state.payments.create_checkout(
        purchase_id=purchase.purchase_id,
        title=resource.title,
        amount_usd=amount_usd,
        success_url=f"{base}/library?purchase=success&resource={resource.resource_id}",
        cancel_url=f"{base}/library?purchase=cancelled",
    )
    await state.purchases.attach_reference(purchase.purchase_id, session.session_id)
    logger.info(
        "checkout_created",
        user_id=user.user_id, resource_id=resource.resource_id, provider=session.provider,
    )
    return {
        "purchase_id": purchase.purchase_id,
        "provider": session.provider,
        "session_id": session.session_id,
        "checkout_url": session.url,
        "amount_usd": session.amount_usd,
        "currency": "usd",
        "status": purchase.status,
    }


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, state: AppState = Depends(get_app_state)):
    """Provider-confirmed payment. Signature verification happens before any
    state change, and access is granted only for a matching pending purchase."""
    payload = await request.body()
    event = state.payments.verify_webhook(payload, request.headers.get("stripe-signature"))

    event_id = str(event.get("id") or "")
    if event_id and await _already_processed(state, event_id):
        logger.info("payment_webhook_duplicate", event_id=event_id)
        return {"received": True, "duplicate": True}

    event_type = str(event.get("type") or "")
    obj: dict[str, Any] = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        await _fulfil(state, obj)
    elif event_type in ("charge.refunded", "checkout.session.expired"):
        await _revoke(state, obj, event_type)
    else:
        logger.info("payment_webhook_ignored", event_type=event_type)

    return {"received": True}


async def _already_processed(state: AppState, event_id: str) -> bool:
    """Redis SET NX dedup. Degrades gracefully: if Redis is unavailable, we
    process anyway (mark_paid / mark_refunded are idempotent) and log a warning
    so the operator can investigate without a dropped payment."""
    redis = state.databases.redis.client
    if redis is None:
        return False
    try:
        # SET NX returns None when the key already existed → replay.
        return await redis.set(f"stripe:event:{event_id}", "1", nx=True, ex=86400) is None
    except Exception:
        logger.warning("payment_webhook_dedup_unavailable")
        return False


async def _fulfil(state: AppState, session: dict[str, Any]) -> None:
    reference = str(session.get("id") or "")
    purchase_id = str(session.get("client_reference_id") or "") or str(
        (session.get("metadata") or {}).get("purchase_id") or ""
    )
    purchase = None
    if purchase_id:
        purchase = await state.purchases.get(purchase_id)
    elif reference:
        purchase = await state.purchases.get_by_reference(state.payments.name, reference)
    if purchase is None:
        logger.warning("payment_webhook_unmatched", reference=reference)
        return
    # The provider, not the client, confirms payment — but the amount it
    # reports must match what we priced. Never grant access on a cheaper charge.
    amount_total = session.get("amount_total")
    if amount_total is not None:
        expected_cents = int(round((purchase.amount_usd or 0.0) * 100))
        try:
            received_cents = int(amount_total)
        except (TypeError, ValueError):
            received_cents = -1
        if received_cents != expected_cents:
            logger.warning(
                "payment_webhook_amount_mismatch",
                purchase_id=purchase.purchase_id,
                expected_cents=expected_cents,
                received_cents=received_cents,
            )
            return
    marked = await state.purchases.mark_paid(purchase.purchase_id)
    logger.info(
        "premium_access_granted",
        user_id=marked.user_id,
        resource_id=marked.resource_id,
    )


async def _revoke(state: AppState, obj: dict[str, Any], event_type: str) -> None:
    reference = str(obj.get("id") or obj.get("payment_intent") or "")
    if not reference:
        return
    purchase = await state.purchases.get_by_reference(state.payments.name, reference)
    if purchase is None:
        logger.warning("payment_revoke_unmatched", event_type=event_type, reference=reference)
        return
    await state.purchases.mark_refunded(purchase.purchase_id)
    logger.info(
        "premium_access_revoked",
        user_id=purchase.user_id, resource_id=purchase.resource_id, event_type=event_type,
    )
