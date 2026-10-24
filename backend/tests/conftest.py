from __future__ import annotations

import pytest

from app.core.config import Settings
from app.ingestion.sources.base import DiscoveredItem
from app.models.resource import Resource, ResourceType


def make_settings(**overrides) -> Settings:
    """Isolated settings: never reads .env files, always test environment."""
    params: dict = {
        "_env_file": None,
        "environment": "test",
        "secret_key": "unit-test-secret-key-not-for-production-use",
    }
    params.update(overrides)
    return Settings(**params)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


def make_item(**overrides) -> DiscoveredItem:
    params: dict = {
        "title": "A Study of Sorting Algorithms",
        "type": ResourceType.RESEARCH_PAPER,
        "authors": ["Ada Lovelace"],
        "year": 2024,
        "description": "Comparative analysis of sorting algorithms.",
        "keywords": ["sorting", "algorithms"],
        "source_name": "test-source",
    }
    params.update(overrides)
    return DiscoveredItem(**params)


def make_resource(**overrides) -> Resource:
    params: dict = {
        "resource_id": "RES-000001",
        "type": ResourceType.RESEARCH_PAPER,
        "title": "A Study of Sorting Algorithms",
        "authors": ["Ada Lovelace"],
        "year": 2024,
    }
    params.update(overrides)
    return Resource(**params)


class FakeRedis:
    """Minimal redis.asyncio stand-in for the rate limiter."""

    def __init__(self, *, fail: bool = False):
        self.values: dict[str, int] = {}
        self.expired: list[str] = []
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("redis is down")
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, _seconds: int) -> bool:
        if self.fail:
            raise ConnectionError("redis is down")
        self.expired.append(key)
        return True
