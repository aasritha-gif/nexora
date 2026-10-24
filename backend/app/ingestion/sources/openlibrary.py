from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.models.resource import ResourceIdentifiers, ResourceType

logger = get_logger(__name__)

_API_URL = "https://openlibrary.org/search.json"


class OpenLibraryAdapter(SourceAdapter):
    """Open Library Search API — keyless. Book metadata + external link;
    NEXORA never hosts or downloads the copyrighted work itself."""

    name = "openlibrary"
    requires_api_key = False

    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        items: list[DiscoveredItem] = []
        per_query = max(2, limit // max(1, len(queries)))
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
            for query in queries:
                try:
                    response = await client.get(_API_URL, params={
                        "q": query,
                        "limit": per_query,
                        "fields": "key,title,author_name,first_publish_year,isbn,"
                                  "subject,edition_count,ratings_average,publisher",
                    })
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("openlibrary_query_failed", query=query,
                                   reason=exc.__class__.__name__)
                    continue
                for doc in data.get("docs", []):
                    item = self._parse_doc(doc)
                    if item:
                        items.append(item)
                        if len(items) >= limit:
                            return items
        return items

    def _parse_doc(self, doc: dict) -> DiscoveredItem | None:
        title = (doc.get("title") or "").strip()
        if not title:
            return None
        key = doc.get("key") or ""
        authors = [a for a in (doc.get("author_name") or []) if a][:10]
        isbns = doc.get("isbn") or []
        subjects = [s for s in (doc.get("subject") or [])
                    if isinstance(s, str) and len(s) < 60][:10]
        publishers = doc.get("publisher") or []
        year = doc.get("first_publish_year")
        url = f"https://openlibrary.org{key}" if key else None
        return DiscoveredItem(
            title=title[:400],
            type=ResourceType.BOOK,
            authors=authors,
            year=int(year) if year and 1900 < year < 2100 else None,
            description=(
                "Book record from Open Library. "
                f"{doc.get('edition_count', 0)} editions catalogued."
                + (f" Subjects: {', '.join(subjects[:6])}." if subjects else "")
            ),
            keywords=subjects,
            identifiers=ResourceIdentifiers(
                isbn=str(isbns[0]) if isbns else None,
                url=url,
                source_id=key.lstrip("/works/") if key else None,
            ),
            source_name=self.name,
            source_url=url,
            publisher=publishers[0] if publishers else None,
        )
