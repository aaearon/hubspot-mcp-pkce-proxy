"""Tests for diagnostic request logging middleware."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from hubspot_mcp_proxy.app import create_app
from hubspot_mcp_proxy.config import Settings
from tests.conftest import TEST_ENCRYPTION_KEY


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "hs-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "hs-client-secret")
    monkeypatch.setenv("PROXY_BASE_URL", "https://proxy.example.com")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    return create_app(Settings())


@pytest.mark.anyio
async def test_request_logging_includes_method_and_path(app, caplog):
    """Middleware logs method and path for every request."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="hubspot_mcp_proxy.app"):
            await client.get("/health")

    assert any(
        "GET /health" in record.message
        for record in caplog.records
    ), f"Expected 'GET /health' in logs, got: {[r.message for r in caplog.records]}"


@pytest.mark.anyio
async def test_request_logging_includes_user_agent(app, caplog):
    """Middleware logs the User-Agent header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="hubspot_mcp_proxy.app"):
            await client.get("/health", headers={"User-Agent": "CopilotStudio/1.0"})

    assert any(
        "CopilotStudio/1.0" in record.message
        for record in caplog.records
    ), f"Expected User-Agent in logs, got: {[r.message for r in caplog.records]}"


@pytest.mark.anyio
async def test_request_logging_shows_auth_presence(app, caplog):
    """Middleware logs whether Authorization header is present."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="hubspot_mcp_proxy.app"):
            await client.get("/health", headers={"Authorization": "Bearer tok123"})

    assert any(
        "auth=yes" in record.message.lower() or "auth: yes" in record.message.lower()
        for record in caplog.records
    ), f"Expected auth presence in logs, got: {[r.message for r in caplog.records]}"


@pytest.mark.anyio
async def test_request_logging_shows_no_auth(app, caplog):
    """Middleware logs when Authorization header is absent."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="hubspot_mcp_proxy.app"):
            await client.get("/health")

    assert any(
        "auth=no" in record.message.lower() or "auth: no" in record.message.lower()
        for record in caplog.records
    ), f"Expected auth=no in logs, got: {[r.message for r in caplog.records]}"


@pytest.mark.anyio
async def test_request_logging_includes_status_code(app, caplog):
    """Middleware logs the response status code."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="hubspot_mcp_proxy.app"):
            await client.get("/health")

    assert any(
        "200" in record.message
        for record in caplog.records
    ), f"Expected status 200 in logs, got: {[r.message for r in caplog.records]}"
