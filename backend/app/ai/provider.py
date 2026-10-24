from __future__ import annotations

import abc
import logging
import time

import httpx

from app.core.config import Settings
from app.core.errors import AIProviderNotConfiguredError

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 90
EMBED_BATCH = 64


class ChatMessageParam:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class CompletionResult:
    def __init__(self, text: str, model: str, usage: dict | None):
        self.text = text
        self.model = model
        self.usage = usage


class AIProvider(abc.ABC):
    """Provider-agnostic LLM abstraction.

    `none` is a valid, honest state: every AI feature checks
    `provider.is_configured` and reports "not configured" rather than
    fabricating output."""

    name = "none"

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def embeddings_available(self) -> bool:
        return False

    async def complete(
        self, messages: list[ChatMessageParam], *, temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> CompletionResult:
        raise AIProviderNotConfiguredError()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise AIProviderNotConfiguredError()

    def status(self) -> dict:
        return {
            "provider": self.name,
            "configured": self.is_configured,
            "model": self.settings.ai_model if self.is_configured else None,
            "embeddings_available": self.embeddings_available,
        }

    async def close(self) -> None:
        return None


class NoneProvider(AIProvider):
    name = "none"


class OpenAICompatibleProvider(AIProvider):
    """OpenAI-compatible chat + embeddings. Works with OpenAI, Groq,
    OpenRouter, Ollama (/v1), LM Studio, vLLM… selected purely via config."""

    name = "openai"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._base_url = (settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.ai_api_key)

    @property
    def embeddings_available(self) -> bool:
        # Local runtimes (Ollama/LM Studio) often lack an embeddings endpoint;
        # we probe lazily and cache the result on first use.
        return self.is_configured and not getattr(self, "_embeddings_disabled", False)

    async def complete(
        self, messages: list[ChatMessageParam], *, temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> CompletionResult:
        if not self.is_configured:
            raise AIProviderNotConfiguredError()
        payload = {
            "model": self.settings.ai_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._post_json("/chat/completions", payload)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Malformed completion response from AI provider") from exc
        return CompletionResult(text=text, model=data.get("model", self.settings.ai_model),
                                usage=data.get("usage"))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.is_configured:
            raise AIProviderNotConfiguredError()
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            payload = {
                "model": self.settings.ai_embedding_model,
                "input": batch,
            }
            data = await self._post_json("/embeddings", payload)
            try:
                ordered = sorted(data["data"], key=lambda d: d["index"])
                all_embeddings.extend([item["embedding"] for item in ordered])
            except (KeyError, TypeError) as exc:
                raise RuntimeError("Malformed embeddings response from AI provider") from exc
        return all_embeddings

    async def _post_json(self, path: str, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                response = await client.post(
                    f"{self._base_url}{path}", json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"AI provider request failed: {exc}") from exc
        if response.status_code == 404:
            self._embeddings_disabled = True
            raise RuntimeError(
                f"AI provider returned 404 for {path} — endpoint not available "
                "on this backend"
            )
        if response.status_code in (401, 403):
            log.error("AI provider rejected credentials", extra={"event": "ai_auth_failed"})
            raise RuntimeError("AI provider rejected the configured credentials")
        response.raise_for_status()
        log.debug(
            "AI provider call %s took %.0f ms", path, (time.monotonic() - started) * 1000
        )
        return response.json()


class AnthropicProvider(AIProvider):
    """Anthropic Messages API. No embeddings endpoint exists, so RAG falls
    back to lexical retrieval (BM25-style scoring) for this provider."""

    name = "anthropic"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.ai_api_key)

    @property
    def embeddings_available(self) -> bool:
        return False

    async def complete(
        self, messages: list[ChatMessageParam], *, temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> CompletionResult:
        if not self.is_configured:
            raise AIProviderNotConfiguredError()
        system = "\n".join(m.content for m in messages if m.role == "system")
        convo = [m.to_dict() for m in messages if m.role != "system"]
        payload = {
            "model": self.settings.ai_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": convo,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.settings.ai_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages", json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"AI provider request failed: {exc}") from exc
        if response.status_code in (401, 403):
            log.error("AI provider rejected credentials", extra={"event": "ai_auth_failed"})
            raise RuntimeError("AI provider rejected the configured credentials")
        response.raise_for_status()
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return CompletionResult(text=text, model=data.get("model", self.settings.ai_model),
                                usage=data.get("usage"))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(
            "The Anthropic provider has no embeddings endpoint; "
            "lexical retrieval is used instead"
        )


def build_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "openai" and settings.ai_api_key:
        return OpenAICompatibleProvider(settings)
    if settings.ai_provider == "anthropic" and settings.ai_api_key:
        return AnthropicProvider(settings)
    return NoneProvider(settings)
