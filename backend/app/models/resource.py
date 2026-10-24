from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceType(str, Enum):
    BOOK = "book"
    EBOOK = "ebook"
    STUDY_MATERIAL = "study_material"
    RESEARCH_PAPER = "research_paper"
    JOURNAL = "journal"
    JOURNAL_ARTICLE = "journal_article"
    ARTICLE = "article"
    NEWSPAPER = "newspaper"
    QUESTION_PAPER = "question_paper"
    LECTURE_NOTES = "lecture_notes"
    THESIS = "thesis"
    DISSERTATION = "dissertation"
    CASE_STUDY = "case_study"
    ACADEMIC_REPORT = "academic_report"
    VIDEO = "video"
    PLAYLIST = "playlist"


class AccessType(str, Enum):
    FREE = "free"
    PREMIUM = "premium"


class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AcademicLevel(str, Enum):
    INTRODUCTORY = "introductory"
    CORE = "core"
    ADVANCED = "advanced"
    RESEARCH = "research"


class ResourceIdentifiers(BaseModel):
    doi: str | None = None
    isbn: str | None = None
    arxiv_id: str | None = None
    source_id: str | None = None
    url: str | None = None


class ResourceTaxonomy(BaseModel):
    department_code: str | None = None
    subject_codes: list[str] = Field(default_factory=list)
    topic_codes: list[str] = Field(default_factory=list)


class ResourceClassification(BaseModel):
    method: Literal["rules", "admin", "ai"] = "rules"
    confidence: float = 0.0
    academic_level: AcademicLevel | None = None
    difficulty: Difficulty | None = None
    semester: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class ResourceSource(BaseModel):
    name: str
    url: str | None = None
    license: str | None = None
    id: str | None = None


class ResourceStats(BaseModel):
    views: int = 0
    reads: int = 0
    downloads: int = 0
    bookmarks: int = 0
    rating_sum: int = 0
    rating_count: int = 0

    @property
    def rating_average(self) -> float | None:
        return round(self.rating_sum / self.rating_count, 2) if self.rating_count else None


class ResourceContent(BaseModel):
    text_available: bool = False
    text_source: Literal["description", "pdf", "html", "manual", "seed"] | None = None
    text_length: int = 0
    chunk_count: int = 0


class YouTubeInfo(BaseModel):
    video_id: str
    channel_title: str | None = None
    channel_id: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    published_at: str | None = None
    playlist_id: str | None = None
    item_count: int | None = None


class ResourceFlags(BaseModel):
    is_seed_data: bool = False
    seed_label: str | None = None
    is_purchased_by_user: bool = False


class Resource(BaseModel):
    """Canonical resource document — lives in MongoDB. One resource = one
    RES-xxxxxx identity across all four databases."""

    model_config = ConfigDict(populate_by_name=True)

    resource_id: str
    type: ResourceType
    title: str
    subtitle: str | None = None
    description: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    publisher: str | None = None
    language: str = "en"
    access: AccessType = AccessType.FREE
    premium_price_usd: float | None = None
    identifiers: ResourceIdentifiers = Field(default_factory=ResourceIdentifiers)
    fingerprint: str | None = None
    taxonomy: ResourceTaxonomy = Field(default_factory=ResourceTaxonomy)
    classification: ResourceClassification = Field(default_factory=ResourceClassification)
    keywords: list[str] = Field(default_factory=list)
    stats: ResourceStats = Field(default_factory=ResourceStats)
    content: ResourceContent = Field(default_factory=ResourceContent)
    source: ResourceSource | None = None
    youtube: YouTubeInfo | None = None
    flags: ResourceFlags = Field(default_factory=ResourceFlags)
    citation_count: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
