from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.models.resource import ResourceIdentifiers, ResourceType

logger = get_logger(__name__)

_API_URL = "https://doaj.org/api/v2/search/articles"


class DOAJAdapter(SourceAdapter):
    """DOAJ (Directory of Open Access Journals) API — keyless. Articles are
    open access; abstracts are legitimate text for the RAG layer."""

    name = "doaj"
    requires_api_key = False

    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        items: list[DiscoveredItem] = []
        per_query = max(2, limit // max(1, len(queries)))
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
            for query in queries:
                try:
                    response = await client.get(
                        _API_URL, params={"query": query, "pageSize": per_query}
                    )
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("doaj_query_failed", query=query,
                                   reason=exc.__class__.__name__)
                    continue
                for record in data.get("results", []):
                    item = self._parse_record(record)
                    if item:
                        items.append(item)
                        if len(items) >= limit:
                            return items
        return items

    def _parse_record(self, record: dict) -> DiscoveredItem | None:
        bib = record.get("bibjson", {}) or {}
        title = (bib.get("title") or "").strip()
        if not title:
            return None
        authors = [a.get("name", "") for a in (bib.get("author") or []) if a.get("name")][:12]
        year = bib.get("year")
        abstract = (bib.get("abstract") or "").strip()
        keywords = [k for k in (bib.get("keywords") or []) if isinstance(k, str)][:10]
        doi = None
        for identifier in bib.get("identifier", []):
            if identifier.get("type") == "doi":
                doi = identifier.get("id")
                break
        fulltext_url = None
        for link in bib.get("link", []):
            if link.get("type") in ("fulltext", "fulltext-pdf"):
                fulltext_url = link.get("url")
                break
        journal = (bib.get("journal") or {}).get("title")
        license_name = None
        for link in bib.get("link", []):
            if link.get("type") == "license":
                license_name = link.get("url") or "open access"
                break
        source_id = record.get("id") or doi
        return DiscoveredItem(
            title=title[:400],
            type=ResourceType.JOURNAL_ARTICLE,
            authors=authors,
            year=int(year) if year and 1900 < year < 2100 else None,
            description=abstract[:4000] or None,
            keywords=keywords,
            identifiers=ResourceIdentifiers(
                doi=doi, url=fulltext_url or doi and f"https://doi.org/{doi}",
                source_id=str(source_id) if source_id else None,
            ),
            source_name=self.name,
            source_url=fulltext_url,
            publisher=journal,
            license=license_name,
            text=abstract or None,
            text_source="description",
        )
