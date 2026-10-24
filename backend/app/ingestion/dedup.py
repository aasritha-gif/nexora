from __future__ import annotations

import hashlib
import re

from app.ingestion.sources.base import DiscoveredItem
from app.models.resource import Resource

_AUTHOR_STOP = {"unknown", "anonymous", "editor", "staff"}


def normalize_title(title: str) -> str:
    lowered = (title or "").lower()
    lowered = re.sub(r"\(.*?\)|\[.*?\]", " ", lowered)
    lowered = re.sub(r"[^a-z0-9 ]", " ", lowered)
    return " ".join(sorted(set(lowered.split())))


def first_author_key(authors: list[str]) -> str:
    for author in authors:
        cleaned = (author or "").strip().lower()
        if cleaned and cleaned not in _AUTHOR_STOP:
            return re.sub(r"[^a-z]", "", cleaned)[:24]
    return ""


def fingerprint(item: DiscoveredItem) -> str:
    basis = normalize_title(item.title) + "|" + first_author_key(item.authors)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def identifier_kinds(item: DiscoveredItem) -> list[tuple[str, str]]:
    """Strong identifiers in priority order — (kind, value)."""
    pairs = []
    if item.identifiers.doi:
        pairs.append(("doi", item.identifiers.doi))
    if item.identifiers.isbn:
        pairs.append(("isbn", item.identifiers.isbn))
    if item.identifiers.arxiv_id:
        pairs.append(("arxiv_id", item.identifiers.arxiv_id))
    if item.identifiers.source_id:
        pairs.append(("source_id", f"{item.source_name}:{item.identifiers.source_id}"))
    if item.identifiers.url:
        pairs.append(("url", item.identifiers.url.rstrip("/")))
    return pairs


def merge_metadata(existing: Resource, item: DiscoveredItem) -> dict:
    """Merge a re-discovered item into an existing resource. Existing values
    win unless the new source provides something the old one lacked; lists
    union. Returns the update dict (empty when nothing improves)."""
    updates: dict = {}
    if not existing.description and item.description:
        updates["description"] = item.description[:4000]
    if not existing.year and item.year:
        updates["year"] = item.year
    if not existing.publisher and item.publisher:
        updates["publisher"] = item.publisher[:200]
    if item.citation_count is not None and (existing.citation_count or 0) < item.citation_count:
        updates["citation_count"] = item.citation_count
    if not existing.identifiers.doi and item.identifiers.doi:
        updates["identifiers.doi"] = item.identifiers.doi
    if not existing.identifiers.isbn and item.identifiers.isbn:
        updates["identifiers.isbn"] = item.identifiers.isbn
    if not existing.identifiers.arxiv_id and item.identifiers.arxiv_id:
        updates["identifiers.arxiv_id"] = item.identifiers.arxiv_id
    if not existing.identifiers.url and item.identifiers.url:
        updates["identifiers.url"] = item.identifiers.url

    new_keywords = set(k.lower()[:60] for k in item.keywords if k)
    existing_keywords = set(existing.keywords or [])
    if new_keywords - existing_keywords:
        updates["keywords"] = sorted(existing_keywords | new_keywords)[:24]
    if not existing.fingerprint:
        updates["fingerprint"] = fingerprint(item)
    return updates
