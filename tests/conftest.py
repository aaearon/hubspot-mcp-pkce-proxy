"""Shared test fixtures."""

import pytest

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient


@pytest.fixture
def settings(monkeypatch):
    """Provide test settings with required env vars."""
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "hs-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "hs-client-secret")
    monkeypatch.setenv("PROXY_BASE_URL", "https://proxy.example.com")
    return Settings()


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
