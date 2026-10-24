from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    source_key: str
    name: str
    adapter: str
    enabled: bool = True
    requires_api_key: bool = False
    schedule_minutes: int = 360
    last_run_at: datetime | None = None
    last_run_status: Literal["ok", "partial", "failed", "never"] = "never"
    config: dict = Field(default_factory=dict)


class IngestionRun(BaseModel):
    run_id: str
    source_key: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: Literal["running", "ok", "partial", "failed"] = "running"
    discovered: int = 0
    added: int = 0
    updated: int = 0
    duplicates_skipped: int = 0
    merged: int = 0
    failures: int = 0
    error_samples: list[str] = Field(default_factory=list, max_length=10)
    triggered_by: Literal["scheduler", "admin", "startup"] = "scheduler"


class RetryItem(BaseModel):
    item_id: str
    source_key: str
    stage: Literal["fetch", "validate", "normalize", "classify", "persist", "graph", "analytics", "cache"]
    payload: dict
    attempts: int = 0
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: str | None = None
