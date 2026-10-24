from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.resource import AccessType, Difficulty, ResourceType
from app.schemas.resource import ResourceSummary


class SearchFilters(BaseModel):
    query: str = Field(default="", max_length=512)
    department: str | None = None
    subject: str | None = None
    topic: str | None = None
    types: list[ResourceType] = Field(default_factory=list)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    difficulty: Difficulty | None = None
    access: AccessType | None = None
    author: str | None = Field(default=None, max_length=120)

    def cache_key(self) -> str:
        parts = [
            self.query.strip().lower(),
            self.department or "-",
            self.subject or "-",
            self.topic or "-",
            ",".join(sorted(t.value for t in self.types)),
            str(self.year_from or "-"),
            str(self.year_to or "-"),
            str(self.min_rating or "-"),
            self.difficulty.value if self.difficulty else "-",
            self.access.value if self.access else "-",
            (self.author or "-").lower(),
        ]
        return "|".join(parts)


class SearchRequest(BaseModel):
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = Field(default=1, ge=1, le=200)
    page_size: int = Field(default=12, ge=1, le=48)
    semantic: bool = True


class SearchResponse(BaseModel):
    results: list[ResourceSummary]
    total: int
    page: int
    page_size: int
    pages: int
    interpreted: dict = Field(default_factory=dict)
    semantic_used: bool = False
    cached: bool = False
    took_ms: float = 0.0

    @property
    def items(self) -> list[ResourceSummary]:
        return self.results

    @property
    def total_pages(self) -> int:
        return self.pages

    def model_dump(self, *args, **kwargs) -> dict:
        d = super().model_dump(*args, **kwargs)
        d["items"] = d.get("results", [])
        d["total_pages"] = d.get("pages", 0)
        return d


class SearchSuggestion(BaseModel):
    text: str
    kind: str = "example"
