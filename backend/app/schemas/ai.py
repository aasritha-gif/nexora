from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AIStatus(BaseModel):
    provider: str
    configured: bool
    model: str | None = None
    embeddings_available: bool = False
    capabilities: list[str] = Field(default_factory=list)


class AIOverviewResponse(BaseModel):
    resource_id: str
    generated_at: datetime
    model: str
    summary: str
    key_concepts: list[str] = Field(default_factory=list)
    important_points: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    who_should_read: str | None = None
    key_takeaways: list[str] = Field(default_factory=list)
    research: dict | None = None
    sources: list[dict] = Field(default_factory=list)


class ReadingActionRequest(BaseModel):
    action: str = Field(
        ...,
        description="explain | simplify | example | summarize | notes | flashcards | questions | translate | terminology",
    )
    selection: str | None = Field(default=None, max_length=6000)
    language: str | None = Field(default=None, max_length=32)


class ReadingActionResponse(BaseModel):
    action: str
    result: str
    notes_saved: int = 0
    flashcards_saved: int = 0
    questions_saved: int = 0


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    message_id: str
    role: str
    content: str
    citations: list[dict] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)


class ReaderDocument(BaseModel):
    resource_id: str
    title: str
    readable: bool
    reason: str | None = None
    external_url: str | None = None
    total_chunks: int = 0
    sections: list[dict] = Field(default_factory=list)
