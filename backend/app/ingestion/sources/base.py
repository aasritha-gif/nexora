from __future__ import annotations

import abc
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.resource import ResourceIdentifiers, ResourceType


class DiscoveredItem(BaseModel):
    """A normalized candidate produced by a source adapter — everything the
    pipeline needs before validation/classification/persistence."""

    title: str
    type: ResourceType
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    identifiers: ResourceIdentifiers = Field(default_factory=ResourceIdentifiers)
    source_name: str = "unknown"
    source_url: str | None = None
    license: str | None = None
    publisher: str | None = None
    language: str = "en"
    citation_count: int | None = None
    # Full text when legitimately available (open access / permissive license).
    text: str | None = None
    text_source: str | None = None
    youtube: dict[str, Any] | None = None


class SourceAdapter(abc.ABC):
    """Interface for automatic resource discovery sources. Adding a source
    means implementing this class and registering it in ADAPTERS."""

    name: str = "abstract"
    requires_api_key: bool = False
    api_key_setting: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        if not self.requires_api_key:
            return True
        return bool(getattr(self.settings, self.api_key_setting or "", None))

    def unavailable_reason(self) -> str | None:
        if self.is_available():
            return None
        env_var = f"NEXORA_{(self.api_key_setting or '').upper()}"
        return f"{self.name} is not configured — set {env_var} to enable it."

    @abc.abstractmethod
    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        """Fetch real metadata from the source. Never fabricates entries."""
