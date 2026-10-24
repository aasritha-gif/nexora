from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class AIOverview(BaseModel):
    resource_id: str
    model: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str
    key_concepts: list[str] = Field(default_factory=list)
    important_points: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    who_should_read: str | None = None
    key_takeaways: list[str] = Field(default_factory=list)
    research: dict | None = None  # problem/methodology/results/limitations/future_work
    source_chunks: list[int] = Field(default_factory=list)


class ChatMessage(BaseModel):
    message_id: str
    resource_id: str
    user_id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[dict] = Field(default_factory=list)  # {chunk_index, snippet}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserNote(BaseModel):
    note_id: str
    user_id: str
    resource_id: str
    title: str | None = None
    body: str
    source: Literal["manual", "ai_reading"] = "manual"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Flashcard(BaseModel):
    card_id: str
    user_id: str
    resource_id: str
    front: str
    back: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GeneratedQuestion(BaseModel):
    question_id: str
    user_id: str
    resource_id: str
    kind: Literal["exam", "viva", "practice"]
    question: str
    answer: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceChunk(BaseModel):
    resource_id: str
    chunk_index: int
    text: str
    section: str | None = None
    embedding: list[float] | None = None
    embedding_model: str | None = None
