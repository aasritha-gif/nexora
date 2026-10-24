from __future__ import annotations

import re

import httpx

from app.core.logging import get_logger
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.models.resource import ResourceIdentifiers, ResourceType

logger = get_logger(__name__)

_API_URL = "https://api.crossref.org/works"

_TYPE_MAP = {
    "journal-article": ResourceType.JOURNAL_ARTICLE,
    "proceedings-article": ResourceType.RESEARCH_PAPER,
    "book": ResourceType.BOOK,
    "monograph": ResourceType.BOOK,
    "report": ResourceType.ACADEMIC_REPORT,
    "dissertation": ResourceType.THESIS,
    "posted-content": ResourceType.RESEARCH_PAPER,
}


def _strip_jats(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


class CrossrefAdapter(SourceAdapter):
    """Crossref REST API — keyless (polite pool via contact email). Returns
    metadata only; users follow the DOI to the legitimate source."""

    name = "crossref"
    requires_api_key = False

    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        items: list[DiscoveredItem] = []
        per_query = max(2, limit // max(1, len(queries)))
        params_extra = {}
        if self.settings.crossref_mailto:
            params_extra["mailto"] = self.settings.crossref_mailto
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
            for query in queries:
                try:
                    response = await client.get(_API_URL, params={
                        "query": query,
                        "rows": per_query,
                        "select": "DOI,title,author,issued,container-title,"
                                  "is-referenced-by-count,abstract,URL,type,publisher,subject",
                        **params_extra,
                    })
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("crossref_query_failed", query=query,
                                   reason=exc.__class__.__name__)
                    continue
                for work in (data.get("message", {}) or {}).get("items", []):
                    item = self._parse_work(work)
                    if item:
                        items.append(item)
                        if len(items) >= limit:
                            return items
        return items

    def _parse_work(self, work: dict) -> DiscoveredItem | None:
        titles = work.get("title") or []
        title = (titles[0] or "").strip() if titles else ""
        if not title:
            return None
        authors = []
        for author in (work.get("author") or [])[:12]:
            given = author.get("given", "")
            family = author.get("family", "")
            name = (f"{given} {family}".strip() or author.get("name", "")).strip()
            if name:
                authors.append(name)
        issued = (work.get("issued", {}) or {}).get("date-parts") or [[None]]
        year = issued[0][0] if issued and issued[0] else None
        containers = work.get("container-title") or []
        journal = containers[0] if containers else None
        abstract = _strip_jats(work.get("abstract", ""))
        subjects = [s for s in (work.get("subject") or []) if s][:8]
        resource_type = _TYPE_MAP.get(work.get("type", ""), ResourceType.RESEARCH_PAPER)
        return DiscoveredItem(
            title=title[:400],
            type=resource_type,
            authors=authors,
            year=int(year) if year and 1900 < year < 2100 else None,
            description=abstract[:4000] or None,
            keywords=subjects,
            identifiers=ResourceIdentifiers(
                doi=work.get("DOI"),
                url=work.get("URL"),
                source_id=work.get("DOI"),
            ),
            source_name=self.name,
            source_url=work.get("URL"),
            publisher=work.get("publisher"),
            citation_count=work.get("is-referenced-by-count"),
        )
