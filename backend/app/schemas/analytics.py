from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    database: str
    status: str
    reason: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    databases: list[DatabaseHealth]
    connected: int
    total: int


class TrendingItem(BaseModel):
    resource_id: str
    score: float
    window: str


class PopularSubject(BaseModel):
    subject_code: str
    subject_name: str | None = None
    department_code: str | None = None
    events: int


class PopularDepartment(BaseModel):
    department_code: str
    events: int


class TopResource(BaseModel):
    resource_id: str
    title: str | None = None
    type: str | None = None
    views: int = 0
    reads: int = 0
    bookmarks: int = 0


class DailyActivity(BaseModel):
    day: date
    searches: int = 0
    views: int = 0
    reads: int = 0
    new_resources: int = 0


class AnalyticsSummary(BaseModel):
    total_events: int
    last_7_days: int
    top_resources: list[TopResource] = Field(default_factory=list)
    popular_subjects: list[PopularSubject] = Field(default_factory=list)
    popular_departments: list[PopularDepartment] = Field(default_factory=list)
    daily_activity: list[DailyActivity] = Field(default_factory=list)
    top_searches: list[dict] = Field(default_factory=list)
    available: bool = True
    unavailable_reason: str | None = None
