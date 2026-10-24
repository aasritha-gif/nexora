from __future__ import annotations

import pytest

from app.core.config import Settings
from tests.conftest import make_settings


class TestDefaults:
    def test_default_environment_is_development(self):
        assert Settings(_env_file=None).environment == "development"

    def test_production_requires_secret_key(self):
        settings = make_settings(environment="production", secret_key="")
        with pytest.raises(RuntimeError, match="NEXORA_SECRET_KEY"):
            settings.effective_secret_key()

    def test_development_generates_ephemeral_secret(self):
        settings = make_settings(secret_key="")
        assert settings.effective_secret_key()

    def test_explicit_secret_wins(self):
        settings = make_settings(environment="production", secret_key="s3cret")
        assert settings.effective_secret_key() == "s3cret"

    def test_is_production_and_is_test(self):
        assert make_settings(environment="production").is_production
        assert make_settings(environment="test").is_test
        raw = Settings(_env_file=None)
        assert not raw.is_production and not raw.is_test


class TestCorsOrigins:
    def test_string_origin_splits_into_list(self):
        settings = make_settings(cors_origins="http://a.example, http://b.example,,")
        assert settings.cors_origins == ["http://a.example", "http://b.example"]

    def test_list_origin_passes_through(self):
        settings = make_settings(cors_origins=["http://only.example"])
        assert settings.cors_origins == ["http://only.example"]

    def test_default_origin_is_local_frontend(self):
        assert make_settings().cors_origins == ["http://localhost:3000"]


class TestSafeSummary:
    def test_summary_leaks_no_secrets(self):
        summary = make_settings(
            stripe_secret_key="sk-live-leak-me",
            smtp_password="hunter2",
            ai_api_key="ai-key",
        ).safe_summary()
        blob = repr(summary).lower()
        for forbidden in ("sk-live", "hunter2", "ai-key", "secret", "password", "api_key"):
            assert forbidden not in blob

    def test_summary_reports_configuration_state(self):
        summary = make_settings(ai_provider="openai", payment_provider="stripe").safe_summary()
        assert summary["ai_provider"] == "openai"
        assert summary["payment_provider"] == "stripe"
        assert summary["youtube_configured"] is False
