from __future__ import annotations

from pydantic import BaseModel, Field


class Department(BaseModel):
    code: str
    name: str
    description: str | None = None
    sort_order: int = 100
    is_active: bool = True
    icon: str | None = None
    color: str | None = None


class Subject(BaseModel):
    code: str
    name: str
    department_code: str
    description: str | None = None
    semester: int | None = Field(default=None, ge=1, le=10)
    is_active: bool = True


class Topic(BaseModel):
    code: str
    name: str
    subject_code: str
    description: str | None = None
    is_active: bool = True
