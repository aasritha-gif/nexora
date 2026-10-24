from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.core.logging import get_logger
from app.databases.redis import RedisAdapter
from app.repositories.cache import CacheRepository

logger = get_logger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"

_LABEL_LIMIT = 4


def _parse_iso8601_duration(value: str) -> int:
    # PT1H2M3S -> seconds
    days = hours = minutes = seconds = 0
    token = ""
    for ch in value:
        if ch.isdigit():
            token += ch
        elif ch == "D" and token:
            days = int(token); token = ""
        elif ch == "H" and token:
            hours = int(token); token = ""
        elif ch == "M" and token:
            minutes = int(token); token = ""
        elif ch == "S" and token:
            seconds = int(token); token = ""
        elif ch == "P" or ch == "T":
            token = ""
        else:
            token = ""
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _published_months_ago(published_at: str) -> float:
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 999.0
    return max(0.0, (datetime.now(timezone.utc) - published).days / 30.0)


def _engagement_score(views: int, likes: int, comments: int) -> float:
    if views <= 0:
        return 0.0
    return ((likes * 2.0) + comments) / views * 100.0


def _apply_labels(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return items
    ranked = sorted(items, key=lambda i: i["nexora_score"], reverse=True)
    ranked[0]["nexora_label"] = "Best Overall"
    most_popular = sorted(items, key=lambda i: i["views"], reverse=True)[0]
    if most_popular.get("nexora_label") is None:
        most_popular["nexora_label"] = "Most Popular"
    best_rated = sorted(items, key=lambda i: _engagement_score(i["views"], i["likes"], i["comments"]), reverse=True)[0]
    if best_rated.get("nexora_label") is None:
        best_rated["nexora_label"] = "Best Rated"
    freshest = sorted(items, key=lambda i: i["published_months_ago"])[0]
    if freshest.get("nexora_label") is None:
        freshest["nexora_label"] = "Recently Updated"
    return ranked[:_LABEL_LIMIT]


@dataclass
class YouTubeResult:
    available: bool
    reason: str | None
    query: str
    videos: list[dict[str, Any]]
    playlists: list[dict[str, Any]]


class YouTubeService:
    def __init__(self, settings: Any, cache: CacheRepository) -> None:
        self._settings = settings
        self._cache = cache
        self._api_key = settings.youtube_api_key
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(12.0))

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def close(self) -> None:
        await self._client.aclose()

    async def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured,
            "hint": "Set NEXORA_YOUTUBE_API_KEY to enable video discovery.",
        }

    async def discover(self, query: str, max_results: int = 12) -> YouTubeResult:
        if not self.is_configured:
            return YouTubeResult(
                available=False,
                reason="YouTube Data API is not configured.",
                query=query,
                videos=[],
                playlists=[],
            )
        cache_key = f"yt:disc:{max_results}:{query.lower()}"
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            return YouTubeResult(
                available=True, reason=None, query=query,
                videos=cached.get("videos", []),
                playlists=cached.get("playlists", []),
            )

        try:
            videos, playlists = await self._search_both(query, max_results)
        except YouTubeAPIError as exc:
            logger.warning("youtube_discovery_failed", reason=str(exc), query=query)
            return YouTubeResult(available=False, reason=str(exc), query=query, videos=[], playlists=[])

        payload = {"videos": videos, "playlists": playlists}
        await self._cache.set_json(cache_key, payload, ttl_seconds=6 * 3600)
        return YouTubeResult(available=True, reason=None, query=query, videos=videos, playlists=playlists)

    async def _search_both(self, query: str, max_results: int) -> tuple[list[dict], list[dict]]:
        half = max(4, max_results // 2)
        video_ids = await self._search_ids(query, "video", half)
        playlist_ids = await self._search_ids(query, "playlist", half)
        videos = await self._hydrate_videos(video_ids) if video_ids else []
        playlists = await self._hydrate_playlists(playlist_ids) if playlist_ids else []
        return (
            _apply_labels([v for v in videos if v.get("views", 0) > 0]),
            _apply_labels([p for p in playlists if p.get("views", 0) > 0]),
        )

    async def _search_ids(self, query: str, kind: str, max_results: int) -> list[str]:
        params = {
            "part": "snippet",
            "q": query,
            "type": kind,
            "maxResults": str(min(25, max_results)),
            "key": self._api_key,
            "order": "relevance",
            "safeSearch": "strict",
            "videoEmbeddable": "true",
        } if kind == "video" else {
            "part": "snippet",
            "q": query,
            "type": kind,
            "maxResults": str(min(25, max_results)),
            "key": self._api_key,
            "order": "relevance",
        }
        data = await self._get(_SEARCH_URL, params)
        return [item["id"][f"{kind}Id"] for item in data.get("items", []) if f"{kind}Id" in item.get("id", {})]

    async def _hydrate_videos(self, ids: list[str]) -> list[dict]:
        data = await self._get(_VIDEOS_URL, {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(ids),
            "key": self._api_key,
        })
        out: list[dict] = []
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            views = int(stats.get("viewCount", 0) or 0)
            likes = int(stats.get("likeCount", 0) or 0)
            comments = int(stats.get("commentCount", 0) or 0)
            engagement = _engagement_score(views, likes, comments)
            months = _published_months_ago(snippet.get("publishedAt", ""))
            score = (
                math.log10(max(views, 10)) * 2.0
                + min(engagement * 8.0, 20.0)
                + max(0.0, 12.0 - months * 0.5)
            )
            out.append({
                "kind": "video",
                "youtube_id": item["id"],
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "description": (snippet.get("description", "") or "")[:400],
                "thumbnail": (
                    snippet.get("thumbnails", {}).get("high", {})
                    or snippet.get("thumbnails", {}).get("medium", {})
                ).get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
                "published_months_ago": round(months, 1),
                "duration_seconds": _parse_iso8601_duration(item.get("contentDetails", {}).get("duration", "")),
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_percent": round(engagement, 3),
                "nexora_score": round(score, 2),
                "nexora_label": None,
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            })
        return out

    async def _hydrate_playlists(self, ids: list[str]) -> list[dict]:
        data = await self._get(_PLAYLISTS_URL, {
            "part": "snippet,contentDetails",
            "id": ",".join(ids),
            "key": self._api_key,
        })
        out: list[dict] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            details = item.get("contentDetails", {})
            count = int(details.get("itemCount", 0) or 0)
            months = _published_months_ago(snippet.get("publishedAt", ""))
            completeness = min(count / 20.0, 1.0) * 15.0
            freshness = max(0.0, 12.0 - months * 0.4)
            out.append({
                "kind": "playlist",
                "youtube_id": item["id"],
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "description": (snippet.get("description", "") or "")[:400],
                "thumbnail": (
                    snippet.get("thumbnails", {}).get("high", {})
                    or snippet.get("thumbnails", {}).get("medium", {})
                ).get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
                "published_months_ago": round(months, 1),
                "video_count": count,
                "nexora_score": round(completeness + freshness, 2),
                "nexora_label": None,
                "url": f"https://www.youtube.com/playlist?list={item['id']}",
            })
        return out

    async def _get(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise YouTubeAPIError(f"YouTube Data API request failed: {exc.__class__.__name__}") from exc
        if response.status_code in (401, 403):
            raise YouTubeAPIError("YouTube API credentials were rejected.")
        if response.status_code == 404:
            raise YouTubeAPIError("YouTube API endpoint unavailable.")
        if response.status_code == 429:
            raise YouTubeAPIError("YouTube API quota exceeded; try again later.")
        if response.status_code >= 400:
            raise YouTubeAPIError("YouTube Data API returned an error.")
        try:
            return response.json()
        except ValueError as exc:
            raise YouTubeAPIError("YouTube Data API returned invalid data.") from exc


class YouTubeAPIError(Exception):
    pass


async def build_search_query(topic: str, subject: str | None = None) -> str:
    parts = [topic]
    if subject and subject.lower() not in topic.lower():
        parts.append(subject)
    return quote_plus(" ".join(parts))
