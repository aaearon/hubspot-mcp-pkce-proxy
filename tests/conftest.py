"""Shared test fixtures."""

import pytest

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import TokenEncryptor
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient

# Stable test key (Fernet requires url-safe base64, 32 bytes)
TEST_ENCRYPTION_KEY = "imk_7pWm4NQntQwKYk93wRJh362s6Fsmtph6u_JcTeU="
TEST_REGISTRATION_TOKEN = "test-reg-token"


@pytest.fixture
def settings(monkeypatch):
    """Provide test settings with required env vars."""
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "hs-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "hs-client-secret")
    monkeypatch.setenv("PROXY_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("REGISTRATION_TOKEN", TEST_REGISTRATION_TOKEN)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    return Settings()


@pytest.fixture
def encryptor():
    """Provide a TokenEncryptor for testing."""
    return TokenEncryptor(TEST_ENCRYPTION_KEY)


@pytest.fixture
async def db(tmp_path):
    """Provide an initialized temp database."""
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def hub_client(settings):
    """Provide a HubSpotClient for testing."""
    return HubSpotClient(settings)
