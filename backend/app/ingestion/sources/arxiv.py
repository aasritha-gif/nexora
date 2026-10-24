from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET

import httpx

from app.core.logging import get_logger
from app.ingestion.sources.base import DiscoveredItem, SourceAdapter
from app.models.resource import ResourceIdentifiers, ResourceType

logger = get_logger(__name__)

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_API_URL = "http://export.arxiv.org/api/query"
_PDF_TEXT_CAP_BYTES = 8 * 1024 * 1024
_TEXT_EXTRACT_CAP = 200_000
_QUERY_DELAY_S = 3.0  # arXiv asks for at most one request every 3 seconds


def _strip_markup(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:40]
        text = "\n\n".join((page.extract_text() or "") for page in pages)
        return text[:_TEXT_EXTRACT_CAP]
    except Exception as exc:  # noqa: BLE001 - best-effort extraction
        logger.info("arxiv_pdf_extraction_skipped", reason=str(exc)[:160])
        return ""


class ArxivAdapter(SourceAdapter):
    """arXiv Atom API — keyless, open metadata. PDFs on arXiv are open access,
    so full text is extracted best-effort for the RAG layer."""

    name = "arxiv"
    requires_api_key = False

    async def discover(self, queries: list[str], limit: int) -> list[DiscoveredItem]:
        items: list[DiscoveredItem] = []
        per_query = max(2, limit // max(1, len(queries)))
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0), follow_redirects=True) as client:
            for index, query in enumerate(queries):
                if index:
                    await asyncio.sleep(_QUERY_DELAY_S)
                try:
                    response = await client.get(_API_URL, params={
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": per_query,
                        "sortBy": "relevance",
                    })
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("arxiv_query_failed", query=query,
                                   reason=exc.__class__.__name__)
                    continue
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError:
                    logger.warning("arxiv_bad_xml", query=query)
                    continue
                for entry in root.findall(f"{_ATOM}entry"):
                    item = self._parse_entry(entry)
                    if item:
                        items.append(item)
                        if len(items) >= limit:
                            return items
        return items

    def _parse_entry(self, entry: ET.Element) -> DiscoveredItem | None:
        title_el = entry.find(f"{_ATOM}title")
        title = _strip_markup(title_el.text or "") if title_el is not None else ""
        if not title:
            return None
        authors = []
        for author in entry.findall(f"{_ATOM}author"):
            name_el = author.find(f"{_ATOM}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        published_el = entry.find(f"{_ATOM}published")
        year = int((published_el.text or "")[:4]) if published_el is not None else None
        summary_el = entry.find(f"{_ATOM}summary")
        abstract = _strip_markup(summary_el.text or "") if summary_el is not None else ""
        id_el = entry.find(f"{_ATOM}id")
        entry_url = (id_el.text or "").strip() if id_el is not None else ""
        arxiv_id = entry_url.rsplit("/abs/", 1)[-1] if "/abs/" in entry_url else None
        if arxiv_id and "v" in arxiv_id.rsplit(".", 1)[-1]:
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        doi_el = entry.find(f"{_ARXIV}doi")
        doi = (doi_el.text or "").strip() if doi_el is not None else None
        categories = [
            (el.get("term") or "") for el in entry.findall(f"{_ARXIV}primary_category")
        ] + [el.get("term") or "" for el in entry.findall(f"{_ATOM}category")]
        pdf_url = entry_url.replace("/abs/", "/pdf/") if entry_url else None
        return DiscoveredItem(
            title=title[:400],
            type=ResourceType.RESEARCH_PAPER,
            authors=authors[:12],
            year=year if 1900 < (year or 0) < 2100 else None,
            description=abstract[:4000] or None,
            keywords=[c for c in categories if c][:8],
            identifiers=ResourceIdentifiers(
                doi=doi, arxiv_id=arxiv_id, url=entry_url or None,
                source_id=arxiv_id,
            ),
            source_name=self.name,
            source_url=entry_url or None,
            license="arXiv non-exclusive license",
            text=abstract or None,
            text_source="description",
            youtube=None,
        )

    async def fetch_full_text(self, pdf_url: str) -> str:
        """Open-access PDF text extraction (bounded). Called by the ingestion
        pipeline after an arXiv item is persisted."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
                response = await client.get(pdf_url)
            if response.status_code != 200 or len(response.content) > _PDF_TEXT_CAP_BYTES:
                return ""
            if not response.content[:5].startswith(b"%PDF-"):
                return ""
            return _extract_pdf_text(response.content)
        except httpx.HTTPError:
            return ""
