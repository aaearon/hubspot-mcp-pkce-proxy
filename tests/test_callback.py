"""Tests for the callback endpoint."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient
from hubspot_mcp_proxy.routes.callback import create_callback_router


class TestCallback:
    @pytest.fixture
    def hub_client(self, settings):
        transport = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: None))
        return HubSpotClient(settings)

    @pytest.fixture
    async def stored_state(self, db):
        """Insert a pending auth state."""
        expires = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
        await db.insert_auth_state(
            state_key="proxy-state-abc",
            code_verifier="test-verifier-123",
            client_id="test-client-id",
            redirect_uri="https://copilot.example.com/callback",
            copilot_state="copilot-state-xyz",
            scope="crm.objects.contacts.read",
            expires_at=expires,
        )
        return "proxy-state-abc"

    @pytest.fixture
    def client(self, settings, db, hub_client):
        app = FastAPI()
        app.include_router(create_callback_router(settings, db, hub_client))
        return TestClient(app, follow_redirects=False)

    @respx.mock
    def test_callback_exchanges_code_and_redirects(
        self, client, settings, stored_state
    ):
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "hs-access-token",
                    "refresh_token": "hs-refresh-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        )
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "proxy-state-abc"},
        )
        assert resp.status_code == 307
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        assert parsed.netloc == "copilot.example.com"
        assert "code" in params
        assert params["state"] == ["copilot-state-xyz"]

    @respx.mock
    def test_callback_unknown_state_returns_400(self, client, settings):
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "unknown-state"},
        )
        assert resp.status_code == 400

    @respx.mock
    def test_callback_hubspot_error_returns_502(self, client, settings, stored_state):
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(401, json={"error": "invalid"})
        )
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "proxy-state-abc"},
        )
        assert resp.status_code == 502
