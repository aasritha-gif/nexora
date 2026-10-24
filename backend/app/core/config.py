from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, loaded from environment variables prefixed NEXORA_."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        env_prefix="NEXORA_",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Core ─────────────────────────────────────────────
    app_name: str = "NEXORA"
    app_version: str = "1.0.0"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = True

    secret_key: str = ""
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    cors_origins: list[str] | str = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"

    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    # Stricter, dedicated throttle for anonymous credential endpoints
    # (login, register, password reset) so brute force cannot ride the
    # global per-user/IP budget.
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 300

    # Set true only when a reverse proxy you control terminates client
    # connections; otherwise X-Forwarded-For is client-forgeable.
    trust_proxy_headers: bool = False

    # Bootstrap admin (created on first boot if missing)
    admin_email: str = ""
    admin_password: str = ""

    # ── Databases ────────────────────────────────────────
    mongo_url: str = "mongodb://nexora:nexora_dev_password@localhost:27017/?authSource=admin"
    mongo_db: str = "nexora"

    redis_url: str = "redis://:nexora_dev_password@localhost:6379/0"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "nexora_dev_password"

    monetdb_host: str = "localhost"
    monetdb_port: int = 50000
    monetdb_database: str = "nexora"
    monetdb_user: str = "monetdb"
    monetdb_password: str = "nexora_dev_password"

    # ── AI provider abstraction ──────────────────────────
    ai_provider: Literal["none", "openai", "anthropic"] = "none"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_embedding_model: str = "text-embedding-3-small"

    # ── External services ────────────────────────────────
    youtube_api_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "NEXORA <no-reply@example.edu>"

    payment_provider: Literal["none", "stripe"] = "none"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    premium_default_price_usd: float = 9.0

    # ── Ingestion / synchronization ──────────────────────
    sync_enabled: bool = True
    sync_interval_minutes: int = 360
    crossref_mailto: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    def effective_secret_key(self) -> str:
        """Real key in production; ephemeral key (with a warning) in development."""
        if self.secret_key:
            return self.secret_key
        if self.is_production:
            raise RuntimeError(
                "NEXORA_SECRET_KEY must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return secrets.token_urlsafe(48)

    def safe_summary(self) -> dict:
        """Configuration subset safe for logs/diagnostics — never secrets."""
        return {
            "environment": self.environment,
            "ai_provider": self.ai_provider,
            "payment_provider": self.payment_provider,
            "youtube_configured": bool(self.youtube_api_key),
            "sync_enabled": self.sync_enabled,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
