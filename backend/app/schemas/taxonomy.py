from __future__ import annotations

from pydantic import BaseModel, Field


class DepartmentResponse(BaseModel):
    code: str
    name: str
    description: str | None
    icon: str | None = None
    color: str | None = None
    resource_count: int = 0
    subject_count: int = 0
    trending_topics: list[str] = Field(default_factory=list)


class SubjectResponse(BaseModel):
    code: str
    name: str
    department_code: str
    description: str | None
    semester: int | None
    resource_count: int = 0
    topic_count: int = 0
    topics: list["TopicResponse"] = Field(default_factory=list)


class TopicResponse(BaseModel):
    code: str
    name: str
    subject_code: str
    description: str | None
    resource_count: int = 0


class DepartmentDetailResponse(DepartmentResponse):
    subjects: list[SubjectResponse] = Field(default_factory=list)
    popular_resources: list[dict] = Field(default_factory=list)
    new_resources: list[dict] = Field(default_factory=list)


class TaxonomyBrowseResponse(BaseModel):
    departments: list[DepartmentResponse] = Field(default_factory=list)


class DepartmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None


class SubjectCreateRequest(BaseModel):
    code: str = Field(..., pattern=r"^[a-z0-9_\-]{2,16}$")
    name: str = Field(..., min_length=2, max_length=140)
    department_code: str
    semester: int | None = Field(default=None, ge=1, le=10)
    description: str | None = Field(default=None, max_length=500)


class TopicCreateRequest(BaseModel):
    code: str = Field(..., pattern=r"^[a-z0-9_\-]{2,24}$")
    name: str = Field(..., min_length=2, max_length=140)
    subject_code: str
    description: str | None = Field(default=None, max_length=500)
