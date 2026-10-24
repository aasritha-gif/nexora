from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestionRunResponse(BaseModel):
    run_id: str
    source_key: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    discovered: int
    added: int
    updated: int
    duplicates_skipped: int
    merged: int
    failures: int
    error_samples: list[str] = Field(default_factory=list)
    triggered_by: str


class SourceResponse(BaseModel):
    source_key: str
    name: str
    adapter: str
    enabled: bool
    requires_api_key: bool
    api_key_configured: bool
    adapter_available: bool = True
    unavailable_reason: str | None = None
    schedule_minutes: int
    last_run_at: datetime | None
    last_run_status: str
    config: dict = Field(default_factory=dict)


class SourceConfigRequest(BaseModel):
    queries: list[str] | None = Field(default=None, max_length=40)
    limit: int | None = Field(default=None, ge=1, le=60)
    fetch_full_text: bool | None = None


class SourceUpdateRequest(BaseModel):
    enabled: bool | None = None
    schedule_minutes: int | None = Field(default=None, ge=10, le=10080)


class SyncStatusResponse(BaseModel):
    last_synchronization: datetime | None
    sources: list[SourceResponse]
    recent_runs: list[IngestionRunResponse]
    retry_queue_size: int


class AdminOverviewResponse(BaseModel):
    total_resources: int
    total_users: int
    resources_by_type: dict[str, int]
    resources_by_department: dict[str, int]
    seed_resources: int
    discovered_resources: int
    flagged_reviews: int
    analytics: dict = Field(default_factory=dict)
