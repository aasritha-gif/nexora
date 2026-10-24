from __future__ import annotations

import abc
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import (
    InvalidInputError,
    PaymentProviderNotConfiguredError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_STRIPE_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"
_SIGNATURE_TOLERANCE_SECONDS = 300


@dataclass
class CheckoutSession:
    provider: str
    session_id: str
    url: str
    amount_usd: float


class PaymentProvider(abc.ABC):
    """Premium checkout. A purchase only grants access after the provider
    confirms payment — never on the client's say-so."""

    name: str = "none"

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool: ...

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": self.is_configured,
            "premium_purchases_enabled": self.is_configured,
        }

    @abc.abstractmethod
    async def create_checkout(
        self, *, purchase_id: str, title: str, amount_usd: float,
        success_url: str, cancel_url: str,
    ) -> CheckoutSession: ...

    @abc.abstractmethod
    def verify_webhook(self, payload: bytes, signature_header: str | None) -> dict[str, Any]: ...

    async def close(self) -> None:
        return None


class NonePaymentProvider(PaymentProvider):
    """Honest no-op: premium checkout reports that it is not configured."""

    name = "none"

    @property
    def is_configured(self) -> bool:
        return False

    async def create_checkout(self, **_: Any) -> CheckoutSession:
        raise PaymentProviderNotConfiguredError()

    def verify_webhook(self, payload: bytes, signature_header: str | None) -> dict[str, Any]:
        raise PaymentProviderNotConfiguredError()


class StripePaymentProvider(PaymentProvider):
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    @property
    def is_configured(self) -> bool:
        return bool(self._secret_key)

    async def create_checkout(
        self, *, purchase_id: str, title: str, amount_usd: float,
        success_url: str, cancel_url: str,
    ) -> CheckoutSession:
        if not self.is_configured:
            raise PaymentProviderNotConfiguredError()
        amount_cents = int(round(amount_usd * 100))
        if amount_cents < 50:
            raise InvalidInputError("Minimum charge is $0.50")
        data = {
            "mode": "payment",
            "client_reference_id": purchase_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": title[:200],
            "metadata[purchase_id]": purchase_id,
        }
        try:
            response = await self._client.post(
                _STRIPE_CHECKOUT_URL,
                data=data,
                headers={"Authorization": f"Bearer {self._secret_key}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("stripe_checkout_request_failed", reason=exc.__class__.__name__)
            raise ServiceUnavailableError("Could not reach the payment provider") from exc
        if response.status_code >= 400:
            logger.warning("stripe_checkout_rejected", status=response.status_code)
            raise ServiceUnavailableError("The payment provider rejected the checkout request")
        try:
            body = response.json()
        except ValueError as exc:
            raise ServiceUnavailableError("The payment provider returned an invalid response") from exc
        if not body.get("id") or not body.get("url"):
            raise ServiceUnavailableError("The payment provider did not return a checkout URL")
        return CheckoutSession(
            provider=self.name,
            session_id=str(body["id"]),
            url=str(body["url"]),
            amount_usd=amount_usd,
        )

    def verify_webhook(self, payload: bytes, signature_header: str | None) -> dict[str, Any]:
        if not self._webhook_secret:
            raise PaymentProviderNotConfiguredError(
                "Stripe webhooks require NEXORA_STRIPE_WEBHOOK_SECRET"
            )
        if not signature_header:
            raise InvalidInputError("Missing Stripe-Signature header")
        timestamp = None
        signatures: list[str] = []
        for part in signature_header.split(","):
            key, _, value = part.strip().partition("=")
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)
        if timestamp is None or not signatures:
            raise InvalidInputError("Malformed Stripe-Signature header")
        try:
            issued_at = int(timestamp)
        except ValueError as exc:
            raise InvalidInputError("Malformed Stripe-Signature timestamp") from exc
        if abs(time.time() - issued_at) > _SIGNATURE_TOLERANCE_SECONDS:
            raise InvalidInputError("Stripe webhook timestamp outside tolerance")
        expected = hmac.new(
            self._webhook_secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + payload,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            raise InvalidInputError("Stripe webhook signature verification failed")
        try:
            return json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidInputError("Stripe webhook payload is not valid JSON") from exc

    async def close(self) -> None:
        await self._client.aclose()


def build_payment_provider(settings: Any) -> PaymentProvider:
    if settings.payment_provider == "stripe" and settings.stripe_secret_key:
        return StripePaymentProvider(settings.stripe_secret_key, settings.stripe_webhook_secret)
    return NonePaymentProvider()
