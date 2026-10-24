from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.ai.provider import AIProvider, ChatMessageParam
from app.core.config import Settings
from app.core.errors import AIProviderNotConfiguredError, InvalidInputError, NotFoundError
from app.core.logging import get_logger
from app.models.ai import AIOverview
from app.models.resource import Resource, ResourceType
from app.repositories.cache import CacheRepository
from app.repositories.counters import next_id

logger = get_logger(__name__)

CHUNK_TARGET_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
RETRIEVAL_K = 6
CHAT_HISTORY_TURNS = 5

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_CITATION_RE = re.compile(r"\[(\d{1,3})\]")

SUGGESTED_PROMPTS = [
    "Explain this resource like I'm a beginner",
    "Summarize the key ideas",
    "Give me exam questions on this material",
    "Give me viva questions on this material",
    "What are the limitations of this work?",
    "What should I study first before this?",
]

READ_ACTIONS = {
    "explain", "simplify", "example", "summarize",
    "notes", "flashcards", "questions", "translate", "terminology",
}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text) if len(t) > 2]


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    """Split raw text into (section_heading, body) pairs on heading-like lines."""
    lines = text.splitlines()
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in lines:
        stripped = line.strip()
        is_heading = (
            0 < len(stripped) <= 90
            and len(_WORD_RE.findall(stripped)) <= 12
            and (
                re.match(r"^(\d+(\.\d+)*\s+[A-Z]|[A-Z][A-Za-z ]{2,60})$", stripped)
                and not stripped.endswith((".", ",", ";", ":"))
            )
        )
        if is_heading and len("\n".join(sections[-1][1]).strip()) > 200:
            sections.append((stripped, []))
        else:
            sections[-1][1].append(line)
    return [(heading, "\n".join(body).strip()) for heading, body in sections if "\n".join(body).strip()]


def _chunk_text(text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for heading, body in _split_sections(text):
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        current: list[str] = []
        current_len = 0
        for para in paragraphs:
            if current_len + len(para) > CHUNK_TARGET_CHARS and current:
                chunks.append({"section": heading, "text": "\n\n".join(current)})
                tail = "\n\n".join(current)[-CHUNK_OVERLAP_CHARS:]
                current = [tail]
                current_len = len(tail)
            current.append(para)
            current_len += len(para) + 2
        if current:
            chunks.append({"section": heading, "text": "\n\n".join(current)})
    # A document with no paragraph structure still becomes one chunk set.
    if not chunks and text.strip():
        for start in range(0, len(text), CHUNK_TARGET_CHARS):
            chunks.append({"section": None, "text": text[start:start + CHUNK_TARGET_CHARS]})
    return chunks


def _extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """LLMs wrap JSON in prose/fences; find the first balanced JSON value."""
    for start_char in ("{", "["):
        start = text.find(start_char)
        while start != -1:
            depth = 0
            in_string = False
            escaped = False
            for idx in range(start, len(text)):
                ch = text[idx]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:idx + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break
            start = text.find(start_char, start + 1)
    return None


class AIService:
    """RAG layer: chunking -> embeddings -> retrieval -> grounded answers.

    Every AI feature is honest about availability: with no provider configured
    the API returns 503 ai_not_configured instead of fabricated text."""

    def __init__(self, settings: Settings, provider: AIProvider, db: AsyncIOMotorDatabase,
                 cache: CacheRepository) -> None:
        self._settings = settings
        self._provider = provider
        self._db = db
        self._cache = cache

    # ------------------------------------------------------------------ status

    async def status(self) -> dict[str, Any]:
        status = self._provider.status()
        status["capabilities"] = (
            ["overview", "reading", "chat", "semantic_retrieval"]
            if status["configured"] else []
        )
        if status["configured"] and not status["embeddings_available"]:
            status["capabilities"].append("lexical_retrieval_only")
        return status

    def _require_provider(self) -> None:
        if not self._provider.is_configured:
            raise AIProviderNotConfiguredError()

    # ------------------------------------------------------- document ingestion

    async def ingest_document(self, resource_id: str, text: str,
                              text_source: str = "manual") -> int:
        """Chunk a document, embed if possible, store in resource_chunks."""
        text = (text or "").strip()
        if not text:
            return 0
        chunks = _chunk_text(text)[:400]
        if not chunks:
            return 0
        await self._db.resource_chunks.delete_many({"resource_id": resource_id})
        embedding_model = None
        if self._provider.is_configured and self._provider.embeddings_available:
            try:
                vectors = await self._provider.embed([c["text"] for c in chunks])
                if len(vectors) == len(chunks):
                    for chunk, vector in zip(chunks, vectors):
                        chunk["embedding"] = vector
                    embedding_model = self._settings.ai_embedding_model
            except Exception as exc:  # noqa: BLE001 - embeddings are best-effort; lexical fallback is fine
                logger.warning("chunk_embedding_failed", resource_id=resource_id,
                               reason=str(exc)[:200])
        docs = [
            {
                "resource_id": resource_id,
                "chunk_index": index,
                "text": chunk["text"],
                "section": chunk["section"],
                "embedding": chunk.get("embedding"),
                "embedding_model": embedding_model,
            }
            for index, chunk in enumerate(chunks)
        ]
        await self._db.resource_chunks.insert_many(docs)
        await self._db.resources.update_one(
            {"resource_id": resource_id},
            {"$set": {
                "content.text_available": True,
                "content.text_source": text_source,
                "content.text_length": len(text),
                "content.chunk_count": len(chunks),
            }},
        )
        await self._db.ai_overviews.delete_one({"resource_id": resource_id})
        return len(chunks)

    async def _load_chunks(self, resource_id: str) -> list[dict[str, Any]]:
        cursor = self._db.resource_chunks.find(
            {"resource_id": resource_id}, {"_id": 0}
        ).sort("chunk_index", 1)
        return [doc async for doc in cursor]

    # ---------------------------------------------------------------- retrieval

    async def retrieve(self, resource_id: str, query: str,
                       k: int = RETRIEVAL_K) -> list[dict[str, Any]]:
        chunks = await self._load_chunks(resource_id)
        if not chunks:
            return []
        query_tokens = set(_tokens(query))
        embedded = [c for c in chunks if c.get("embedding")]
        if embedded and self._provider.is_configured and self._provider.embeddings_available:
            try:
                query_vectors = await self._provider.embed([query])
                if query_vectors:
                    query_vector = query_vectors[0]
                    scored = [
                        (_cosine(query_vector, c["embedding"]), c) for c in embedded
                    ]
                    scored.sort(key=lambda pair: pair[0], reverse=True)
                    top = [c for score, c in scored[:k]]
                    # Fall back to lexical for chunks that never got embeddings.
                    if len(top) < k and len(chunks) > len(embedded):
                        top.extend(await self._lexical_top(chunks, query_tokens, k - len(top)))
                    return top
            except RuntimeError:
                pass  # fall through to lexical
        return await self._lexical_top(chunks, query_tokens, k)

    async def _lexical_top(self, chunks: list[dict], query_tokens: set[str],
                           k: int) -> list[dict]:
        doc_freq: dict[str, int] = {}
        for chunk in chunks:
            for token in set(_tokens(chunk["text"])):
                doc_freq[token] = doc_freq.get(token, 0) + 1
        total = max(1, len(chunks))
        scored: list[tuple[float, dict]] = []
        for chunk in chunks:
            tokens = _tokens(chunk["text"])
            if not tokens:
                continue
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            score = 0.0
            for token in query_tokens:
                if token in counts:
                    idf = math.log(1.0 + total / doc_freq[token])
                    score += (1.0 + math.log(counts[token])) * idf
            if query_tokens & set(_tokens(chunk.get("section") or "")):
                score *= 1.25
            scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for score, chunk in scored[:k] if score > 0.0] or chunks[:1]

    # --------------------------------------------------------------- AI Overview

    async def overview(self, resource: Resource, force: bool = False) -> AIOverview:
        # When no AI provider is configured, generate a metadata-based demo overview
        if not self._provider.is_configured:
            return self._demo_overview(resource)
        if not force:
            cached = await self._db.ai_overviews.find_one({"resource_id": resource.resource_id})
            if cached:
                cached.pop("_id", None)
                return AIOverview.model_validate(cached)
        chunks = await self._load_chunks(resource.resource_id)
        context = self._build_context(chunks, limit=8) or (resource.description or "")
        is_paper = resource.type in (ResourceType.RESEARCH_PAPER, ResourceType.JOURNAL_ARTICLE,
                                     ResourceType.THESIS, ResourceType.DISSERTATION)
        research_block = (
            "\nAdditionally include a \"research\" object with keys: "
            "problem, methodology, results, limitations, future_work."
            if is_paper else ""
        )
        prompt = (
            f"Analyze this academic resource and respond with ONLY a JSON object.\n\n"
            f"Title: {resource.title}\n"
            f"Type: {resource.type.value}\n"
            f"Authors: {', '.join(resource.authors) or 'Unknown'}\n"
            f"Year: {resource.year or 'Unknown'}\n"
            f"Keywords: {', '.join(resource.keywords)}\n\n"
            f"Content excerpts:\n{context}\n\n"
            "Return JSON with keys: summary (3-5 sentence string), key_concepts "
            "(list of up to 8 strings), important_points (list of up to 6 strings), "
            "difficulty (one of: beginner, intermediate, advanced), prerequisites "
            "(list of strings), who_should_read (string), key_takeaways (list of up to "
            "6 strings)." + research_block
        )
        result = await self._provider.complete(
            [ChatMessageParam("user", prompt)], temperature=0.2, max_tokens=1600
        )
        parsed = _extract_json(result.text)
        if not isinstance(parsed, dict):
            parsed = {"summary": result.text.strip()[:1200]}
        overview = AIOverview(
            resource_id=resource.resource_id,
            model=result.model,
            summary=str(parsed.get("summary", ""))[:4000],
            key_concepts=[str(c)[:120] for c in (parsed.get("key_concepts") or [])][:8],
            important_points=[str(p)[:200] for p in (parsed.get("important_points") or [])][:6],
            difficulty=parsed.get("difficulty") if parsed.get("difficulty") in
                       ("beginner", "intermediate", "advanced") else None,
            prerequisites=[str(p)[:120] for p in (parsed.get("prerequisites") or [])][:8],
            who_should_read=str(parsed["who_should_read"])[:400] if parsed.get("who_should_read") else None,
            key_takeaways=[str(t)[:200] for t in (parsed.get("key_takeaways") or [])][:6],
            research=parsed.get("research") if isinstance(parsed.get("research"), dict) else None,
            source_chunks=[c["chunk_index"] for c in chunks[:8]],
        )
        await self._db.ai_overviews.update_one(
            {"resource_id": resource.resource_id},
            {"$set": overview.model_dump()},
            upsert=True,
        )
        return overview

    # ------------------------------------------------------------- AI Reading

    async def reading_action(self, user_id: str, resource: Resource, action: str,
                             selection: str | None = None,
                             language: str | None = None) -> dict[str, Any]:
        self._require_provider()
        if action not in READ_ACTIONS:
            raise InvalidInputError(f"Unknown reading action '{action}'")
        chunks = await self._load_chunks(resource.resource_id)
        if not chunks and not selection:
            raise InvalidInputError(
                "This resource has no readable text and no selection was provided."
            )
        context = self._build_context(chunks, limit=4) if not selection else ""
        target = (selection or "").strip()[:6000]
        prompts: dict[str, str] = {
            "explain": f"Explain the following clearly for a university student:\n\n{target or context}",
            "simplify": f"Simplify the following, avoiding jargon; define any term you must keep:\n\n{target or context}",
            "example": f"Give a concrete worked example illustrating the following:\n\n{target or context}",
            "summarize": f"Summarize the following into concise bullet points:\n\n{target or context}",
            "terminology": (
                "List the key technical terms in the following text. For each: the term, "
                f"a one-sentence definition, and why it matters here.\n\n{target or context}"
            ),
            "translate": (
                f"Translate the following into {language or 'English'}. "
                f"Preserve technical accuracy:\n\n{target or context}"
            ),
            "notes": (
                "Create structured study notes for the following. Use markdown headings "
                "## and bullet points. Include a 'Key Terms' section at the end:\n\n"
                f"{target or context}"
            ),
            "flashcards": (
                "Create flashcards from the following. Respond with ONLY a JSON array of "
                '{"front": string, "back": string} objects (6-10 cards):\n\n'
                f"{target or context}"
            ),
            "questions": (
                "Generate practice questions from the following. Respond with ONLY a JSON "
                'array of {"question": string, "answer": string} objects (6-10 items), '
                "mixing conceptual and applied questions:\n\n"
                f"{target or context}"
            ),
        }
        system = (
            f"You are NEXORA's AI reading assistant for '{resource.title}' "
            f"({resource.type.value}). Ground every answer in the provided material."
        )
        if context and not selection:
            prompts[action] = f"{prompts[action]}\n\nResource context:\n{context}"
        result = await self._provider.complete(
            [ChatMessageParam("system", system), ChatMessageParam("user", prompts[action])],
            temperature=0.3, max_tokens=1800,
        )
        response: dict[str, Any] = {"action": action, "result": result.text.strip(),
                                    "notes_saved": 0, "flashcards_saved": 0, "questions_saved": 0}
        if action == "notes":
            note_id = await next_id(self._db, "note")
            await self._db.user_notes.insert_one({
                "note_id": note_id,
                "user_id": user_id,
                "resource_id": resource.resource_id,
                "title": f"AI notes — {resource.title}"[:160],
                "body": result.text.strip()[:20000],
                "source": "ai_reading",
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
            })
            response["notes_saved"] = 1
        elif action in ("flashcards", "questions"):
            parsed = _extract_json(result.text)
            items = parsed if isinstance(parsed, list) else []
            if action == "flashcards":
                docs = []
                for item in items[:12]:
                    if isinstance(item, dict) and item.get("front") and item.get("back"):
                        card_id = await next_id(self._db, "flashcard")
                        docs.append({
                            "card_id": card_id, "user_id": user_id,
                            "resource_id": resource.resource_id,
                            "front": str(item["front"])[:500], "back": str(item["back"])[:2000],
                            "created_at": _utcnow(),
                        })
                if docs:
                    await self._db.flashcards.insert_many(docs)
                response["flashcards_saved"] = len(docs)
            else:
                docs = []
                for item in items[:12]:
                    if isinstance(item, dict) and item.get("question"):
                        question_id = await next_id(self._db, "question")
                        docs.append({
                            "question_id": question_id, "user_id": user_id,
                            "resource_id": resource.resource_id, "kind": "practice",
                            "question": str(item["question"])[:1000],
                            "answer": str(item.get("answer", ""))[:2000] or None,
                            "created_at": _utcnow(),
                        })
                if docs:
                    await self._db.generated_questions.insert_many(docs)
                response["questions_saved"] = len(docs)
        return response

    # ------------------------------------------------------------------- chat

    async def chat(self, user_id: str, resource: Resource, message: str) -> dict[str, Any]:
        self._require_provider()
        relevant = await self.retrieve(resource.resource_id, message)
        if not relevant:
            relevant = []
        context = self._build_context(relevant)
        history_cursor = self._db.chat_messages.find(
            {"resource_id": resource.resource_id, "user_id": user_id}
        ).sort("created_at", -1).limit(CHAT_HISTORY_TURNS * 2)
        history = [doc async for doc in history_cursor]
        history.reverse()
        user_message_id = await next_id(self._db, "message")
        await self._db.chat_messages.insert_one({
            "message_id": user_message_id,
            "resource_id": resource.resource_id,
            "user_id": user_id,
            "role": "user",
            "content": message[:2000],
            "citations": [],
            "created_at": _utcnow(),
        })
        system = (
            f"You are NEXORA's AI tutor for the resource '{resource.title}' "
            f"({resource.type.value}"
            + (f", {resource.year}" if resource.year else "")
            + f", by {', '.join(resource.authors) or 'unknown author'}). "
            "Answer ONLY from the provided context. If the context does not contain "
            "the answer, say so explicitly. Reference context using bracketed chunk "
            "numbers like [1], [2]. Be accurate, clear, and academically rigorous."
        )
        conversation: list[ChatMessageParam] = [ChatMessageParam("system", system)]
        for entry in history:
            conversation.append(ChatMessageParam(entry["role"], entry["content"]))
        context_block = (
            "Resource context (use only this):\n" + context
            if context else
            "No text content is available for this resource. Rely on the metadata: "
            f"title '{resource.title}', description: {resource.description or 'none'}. "
            "Say clearly that full text is not available when asked about specifics."
        )
        conversation.append(ChatMessageParam("user", f"{context_block}\n\nQuestion: {message}"))
        result = await self._provider.complete(conversation, temperature=0.3, max_tokens=1800)
        answer = result.text.strip()
        citations: list[dict[str, Any]] = []
        for match in set(_CITATION_RE.findall(answer)):
            try:
                chunk_index = int(match) - 1
            except ValueError:
                continue
            for chunk in relevant:
                if chunk["chunk_index"] == chunk_index:
                    citations.append({
                        "chunk_index": chunk_index,
                        "section": chunk.get("section"),
                        "snippet": chunk["text"][:220],
                    })
                    break
        assistant_message_id = await next_id(self._db, "message")
        await self._db.chat_messages.insert_one({
            "message_id": assistant_message_id,
            "resource_id": resource.resource_id,
            "user_id": user_id,
            "role": "assistant",
            "content": answer[:10000],
            "citations": citations,
            "created_at": _utcnow(),
        })
        return {
            "message_id": assistant_message_id,
            "role": "assistant",
            "content": answer,
            "citations": citations,
            "suggested_prompts": SUGGESTED_PROMPTS,
        }

    async def chat_history(self, user_id: str, resource_id: str) -> list[dict[str, Any]]:
        cursor = self._db.chat_messages.find(
            {"resource_id": resource_id, "user_id": user_id}, {"_id": 0}
        ).sort("created_at", 1).limit(200)
        return [doc async for doc in cursor]

    async def clear_chat(self, user_id: str, resource_id: str) -> int:
        result = await self._db.chat_messages.delete_many(
            {"resource_id": resource_id, "user_id": user_id}
        )
        return result.deleted_count or 0

    # ------------------------------------------------------------- reader doc

    async def reader_document(self, resource: Resource, can_access: bool) -> dict[str, Any]:
        chunks = await self._load_chunks(resource.resource_id)
        if not can_access:
            return {
                "resource_id": resource.resource_id, "title": resource.title,
                "readable": False,
                "reason": "This is a premium resource. Access requires purchase.",
                "external_url": resource.identifiers.url,
                "total_chunks": 0, "sections": [],
            }
        if not chunks:
            return {
                "resource_id": resource.resource_id, "title": resource.title,
                "readable": False,
                "reason": "Full text is not available on NEXORA for this resource.",
                "external_url": resource.identifiers.url,
                "total_chunks": 0, "sections": [],
            }
        sections: list[dict[str, Any]] = []
        for chunk in chunks:
            if not sections or sections[-1]["section"] != chunk.get("section"):
                sections.append({
                    "section": chunk.get("section"),
                    "chunk_indexes": [chunk["chunk_index"]],
                    "chars": len(chunk["text"]),
                })
            else:
                sections[-1]["chunk_indexes"].append(chunk["chunk_index"])
                sections[-1]["chars"] += len(chunk["text"])
        return {
            "resource_id": resource.resource_id, "title": resource.title,
            "readable": True, "reason": None,
            "external_url": resource.identifiers.url,
            "total_chunks": len(chunks), "sections": sections,
        }

    async def read_section(self, resource_id: str, chunk_indexes: list[int]) -> list[dict]:
        if not chunk_indexes or len(chunk_indexes) > 60:
            raise InvalidInputError("chunk_indexes must contain 1-60 entries")
        cursor = self._db.resource_chunks.find(
            {"resource_id": resource_id, "chunk_index": {"$in": chunk_indexes}}, {"_id": 0}
        ).sort("chunk_index", 1)
        return [doc async for doc in cursor]

    # ------------------------------------------------------------------ notes

    async def list_notes(self, user_id: str) -> list[dict]:
        cursor = self._db.user_notes.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("updated_at", -1).limit(200)
        return [doc async for doc in cursor]

    async def add_note(self, user_id: str, resource_id: str, body: str,
                       title: str | None = None) -> dict:
        note_id = await next_id(self._db, "note")
        doc = {
            "note_id": note_id, "user_id": user_id, "resource_id": resource_id,
            "title": (title or "Note")[:160], "body": body[:20000],
            "source": "manual", "created_at": _utcnow(), "updated_at": _utcnow(),
        }
        await self._db.user_notes.insert_one(doc)
        return doc

    async def list_flashcards(self, user_id: str) -> list[dict]:
        cursor = self._db.flashcards.find({"user_id": user_id}, {"_id": 0}).limit(500)
        return [doc async for doc in cursor]

    async def list_questions(self, user_id: str) -> list[dict]:
        cursor = self._db.generated_questions.find({"user_id": user_id}, {"_id": 0}).limit(500)
        return [doc async for doc in cursor]

    # ------------------------------------------------------------------ helpers

    def _build_context(self, chunks: list[dict], limit: int = RETRIEVAL_K) -> str:
        parts = []
        for chunk in chunks[:limit]:
            label = f"[{chunk['chunk_index'] + 1}]"
            section = f" ({chunk['section']})" if chunk.get("section") else ""
            parts.append(f"{label}{section}\n{chunk['text']}")
        return "\n\n".join(parts)

    def _demo_overview(self, resource: Resource) -> AIOverview:
        """Generate a metadata-based overview when no AI provider is configured.
        Shows what the AI feature *would* produce — useful for demos and presentations."""
        from app.models.resource import ResourceType

        title = resource.title or "This Resource"
        authors = ", ".join(resource.authors) if resource.authors else "the author(s)"
        year = str(resource.year) if resource.year else "recent years"
        keywords = resource.keywords[:6] if resource.keywords else []
        dept = resource.taxonomy.department_code if resource.taxonomy else None
        subject = resource.taxonomy.subject_codes[0] if (resource.taxonomy and resource.taxonomy.subject_codes) else None
        desc = (resource.description or "").strip()

        # Build a realistic-sounding summary from metadata
        type_label = resource.type.value.replace("_", " ").title() if resource.type else "resource"
        summary = (
            f'"{title}" is a {type_label} by {authors} ({year}). '
            + (f"{desc[:300]}... " if len(desc) > 300 else (desc + " " if desc else ""))
            + (f"It covers key areas in {subject or dept or 'this field'}, "
               f"making it a valuable reference for students and researchers alike.")
        )

        key_concepts = keywords[:6] if keywords else [
            "Core Concepts", "Theoretical Foundations",
            "Practical Applications", "Research Methods",
        ]

        important_points = [
            f"Published in {year} by {authors}.",
            f"Classified under {dept or 'Academic Studies'}" + (f" -> {subject}" if subject else "") + ".",
            f"Resource type: {type_label}.",
        ]
        if keywords:
            important_points.append(f"Key topics covered: {', '.join(keywords[:4])}.")
        if desc:
            important_points.append(desc[:180] + ("..." if len(desc) > 180 else ""))
        important_points.append(
            "Suitable for undergraduate and postgraduate level study."
        )

        is_paper = resource.type in (
            ResourceType.RESEARCH_PAPER, ResourceType.JOURNAL_ARTICLE,
            ResourceType.THESIS, ResourceType.DISSERTATION,
        ) if resource.type else False

        research = None
        if is_paper:
            research = {
                "problem": f"Addresses challenges and open questions in {subject or dept or 'the field'}.",
                "methodology": "Employs systematic analysis, literature review, and empirical evaluation.",
                "results": "Demonstrates significant findings relevant to the domain.",
                "limitations": "Scope is bounded by the data and context available at time of publication.",
                "future_work": "Opportunities exist to extend this work with larger datasets and broader experiments.",
            }

        return AIOverview(
            resource_id=resource.resource_id,
            model="metadata-demo",
            summary=summary,
            key_concepts=key_concepts,
            important_points=important_points[:6],
            difficulty="intermediate",
            prerequisites=[
                f"Basic understanding of {dept or 'the subject area'}",
                "Familiarity with academic research methodology",
            ],
            who_should_read=(
                f"Students and researchers in {dept or 'this field'} who want to "
                f"deepen their knowledge of {subject or ', '.join(keywords[:2]) or 'this topic'}."
            ),
            key_takeaways=[
                f"Gain a solid grounding in {', '.join(keywords[:3]) or subject or 'core concepts'}.",
                "Understand both theoretical and practical aspects of the topic.",
                "Use this as a foundation for further research or coursework.",
                f"Cross-reference with other {dept or ''} resources for a complete picture.",
            ],
            research=research,
            source_chunks=[],
        )


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
