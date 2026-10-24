from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Purchase(BaseModel):
    """A completed premium purchase. Access to a premium resource is granted
    only by a persisted purchase record — never by client assertion."""

    purchase_id: str
    user_id: str
    resource_id: str
    amount_usd: float = Field(..., ge=0)
    currency: str = "usd"
    provider: str
    provider_reference: str | None = None
    status: Literal["pending", "paid", "refunded"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: datetime | None = None
