from __future__ import annotations

from app.core.config import Settings
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.models.resource import ResourceIdentifiers, ResourceType
from app.services.youtube_service import YouTubeService


class YouTubeSourceAdapter(SourceAdapter):
    """YouTube Data API v3 — requires NEXORA_YOUTUBE_API_KEY. Discovery runs
    through the shared YouTubeService so live browsing and ingestion share
    caching and error handling."""

    name = "youtube"
    requires_api_key = True
    api_key_setting = "youtube_api_key"

    def __init__(self, settings: Settings, youtube: YouTubeService) -> None:
        super().__init__(settings)
        self._youtube = youtube

    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        items: list[DiscoveredItem] = []
        per_query = max(2, limit // max(1, len(queries)))
        for query in queries:
            result = await self._youtube.discover(query, max_results=per_query)
            if not result.available:
                continue
            for video in result.videos:
                items.append(self._video_item(video))
                if len(items) >= limit:
                    return items
            for playlist in result.playlists:
                items.append(self._playlist_item(playlist))
                if len(items) >= limit:
                    return items
        return items

    def _video_item(self, video: dict) -> DiscoveredItem:
        return DiscoveredItem(
            title=video["title"][:400],
            type=ResourceType.VIDEO,
            authors=[video.get("channel") or "Unknown channel"],
            year=self._year_of(video.get("published_at")),
            description=video.get("description"),
            keywords=["video", "youtube"],
            identifiers=ResourceIdentifiers(
                url=video.get("url"),
                source_id=video.get("youtube_id"),
            ),
            source_name=self.name,
            source_url=video.get("url"),
            publisher=video.get("channel"),
            youtube={
                "video_id": video.get("youtube_id"),
                "channel_title": video.get("channel"),
                "channel_id": video.get("channel_id"),
                "duration_seconds": video.get("duration_seconds"),
                "view_count": video.get("views"),
                "like_count": video.get("likes"),
                "published_at": video.get("published_at"),
            },
        )

    def _playlist_item(self, playlist: dict) -> DiscoveredItem:
        return DiscoveredItem(
            title=playlist["title"][:400],
            type=ResourceType.PLAYLIST,
            authors=[playlist.get("channel") or "Unknown channel"],
            year=self._year_of(playlist.get("published_at")),
            description=playlist.get("description"),
            keywords=["playlist", "youtube"],
            identifiers=ResourceIdentifiers(
                url=playlist.get("url"),
                source_id=playlist.get("youtube_id"),
            ),
            source_name=self.name,
            source_url=playlist.get("url"),
            publisher=playlist.get("channel"),
            youtube={
                "video_id": playlist.get("youtube_id"),
                "channel_title": playlist.get("channel"),
                "channel_id": playlist.get("channel_id"),
                "playlist_id": playlist.get("youtube_id"),
                "item_count": playlist.get("video_count"),
                "published_at": playlist.get("published_at"),
            },
        )

    @staticmethod
    def _year_of(published_at: str | None) -> int | None:
        try:
            return int((published_at or "")[:4])
        except ValueError:
            return None
