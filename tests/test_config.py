"""Tests for configuration module."""

import pytest
from pydantic import ValidationError

from hubspot_mcp_proxy.config import Settings


class TestSettings:
    def test_required_fields(self, monkeypatch):
        """Settings raises without required env vars."""
        monkeypatch.delenv("HUBSPOT_CLIENT_ID", raising=False)
        monkeypatch.delenv("HUBSPOT_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("PROXY_BASE_URL", raising=False)
        with pytest.raises(ValidationError):
            Settings()

    def test_defaults(self, monkeypatch):
        """Settings uses correct defaults for optional fields."""
        monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-id")
        monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("PROXY_BASE_URL", "https://proxy.example.com")
        monkeypatch.setenv("REGISTRATION_TOKEN", "test-token")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-key")
        s = Settings()
        assert s.hubspot_client_id == "test-id"
        assert s.hubspot_client_secret == "test-secret"
        assert s.proxy_base_url == "https://proxy.example.com"
        assert s.hubspot_auth_url == "https://app.hubspot.com/oauth/authorize"
        assert s.hubspot_token_url == "https://api.hubapi.com/oauth/v1/token"
        assert s.hubspot_mcp_url == "https://mcp.hubspot.com"
        assert s.database_path == "/data/proxy.db"
        assert s.auth_state_ttl_seconds == 600
        assert s.auth_code_ttl_seconds == 300
        assert s.log_level == "INFO"

    def test_custom_values(self, monkeypatch):
        """Settings respects custom env var values."""
        monkeypatch.setenv("HUBSPOT_CLIENT_ID", "custom-id")
        monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "custom-secret")
        monkeypatch.setenv("PROXY_BASE_URL", "https://custom.example.com")
        monkeypatch.setenv("REGISTRATION_TOKEN", "custom-token")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "custom-key")
        monkeypatch.setenv("DATABASE_PATH", "/tmp/test.db")
        monkeypatch.setenv("AUTH_STATE_TTL_SECONDS", "120")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.database_path == "/tmp/test.db"
        assert s.auth_state_ttl_seconds == 120
        assert s.log_level == "DEBUG"
