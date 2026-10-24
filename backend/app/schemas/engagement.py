from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.resource import ResourceType


class BookmarkRequest(BaseModel):
    resource_id: str


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)


class ReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(default=None, max_length=140)
    body: str = Field(..., min_length=10, max_length=4000)


class ProgressRequest(BaseModel):
    percent: int = Field(..., ge=0, le=100)
    last_chunk: int = Field(default=0, ge=0)


class RecommendationItem(BaseModel):
    resource_id: str
    reason: str
    section: str
    score: float = 0.0
