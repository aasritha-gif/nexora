from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.resource import (
    AccessType,
    Difficulty,
    ResourceType,
)


class TaxonomyInfo(BaseModel):
    department: str | None = None
    department_name: str | None = None
    subjects: list[str] = Field(default_factory=list)
    subject_names: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    topic_names: list[str] = Field(default_factory=list)


class ResourceSummary(BaseModel):
    resource_id: str
    type: ResourceType
    title: str
    subtitle: str | None = None
    description: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    publisher: str | None = None
    access: AccessType
    premium_price_usd: float | None = None
    taxonomy: TaxonomyInfo = Field(default_factory=TaxonomyInfo)
    keywords: list[str] = Field(default_factory=list)
    rating_average: float | None = None
    rating_count: int = 0
    views: int = 0
    reads: int = 0
    downloads: int = 0
    bookmarks: int = 0
    citation_count: int | None = None
    external_url: str | None = None
    source_name: str | None = None
    youtube_thumbnail: str | None = None
    youtube_duration: int | None = None
    is_seed_data: bool = False
    created_at: datetime | None = None


class ResourceDetail(ResourceSummary):
    language: str = "en"
    classification: dict[str, Any] = Field(default_factory=dict)
    identifiers: dict[str, str | None] = Field(default_factory=dict)
    source: dict[str, Any] | None = None
    youtube: dict[str, Any] | None = None
    ai_capabilities: dict[str, bool] = Field(default_factory=dict)
    updated_at: datetime | None = None


class RelatedResource(ResourceSummary):
    relation: str | None = None
    score: float | None = None


class ReviewResponse(BaseModel):
    review_id: str
    user_id: str
    user_name: str | None = None
    rating: int
    title: str | None = None
    body: str
    status: str = "published"
    created_at: datetime


class Paginated(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int
