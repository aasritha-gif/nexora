from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Bookmark(BaseModel):
    user_id: str
    resource_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadingProgress(BaseModel):
    percent: int = Field(default=0, ge=0, le=100)
    last_chunk: int = 0
    completed: bool = False


class ReadingHistoryEntry(BaseModel):
    user_id: str
    resource_id: str
    first_viewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_viewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    view_count: int = 1
    progress: ReadingProgress = Field(default_factory=ReadingProgress)


class Review(BaseModel):
    review_id: str
    user_id: str
    resource_id: str
    rating: int = Field(..., ge=1, le=5)
    title: str | None = None
    body: str
    status: Literal["published", "flagged", "removed"] = "published"
    moderated_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
