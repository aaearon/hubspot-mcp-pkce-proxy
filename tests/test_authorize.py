"""Tests for the authorize endpoint."""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.authorize import create_authorize_router


class TestAuthorize:
    @pytest.fixture
    async def registered_client(self, db):
        """Insert a registered client and return its info."""
        import hashlib

        client_id = "test-client-id"
        redirect_uri = "https://copilot.example.com/callback"
        await db.insert_client(
            client_id=client_id,
            client_secret_hash=hashlib.sha256(b"secret").hexdigest(),
            redirect_uris=json.dumps([redirect_uri]),
        )
        return {"client_id": client_id, "redirect_uri": redirect_uri}

    @pytest.fixture
    def client(self, settings, db):
        app = FastAPI()
        app.include_router(create_authorize_router(settings, db))
        return TestClient(app, follow_redirects=False)

    def test_authorize_redirects_to_hubspot(
        self, client, settings, registered_client
    ):
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "copilot-state-123",
                "scope": "crm.objects.contacts.read",
            },
        )
        assert resp.status_code == 307
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        assert parsed.scheme == "https"
        assert parsed.hostname == "app.hubspot.com"
        assert params["client_id"] == [settings.hubspot_client_id]
        assert params["response_type"] == ["code"]
        assert "code_challenge" in params
        assert params["code_challenge_method"] == ["S256"]

    def test_authorize_stores_state(self, client, db, registered_client):
        import asyncio

        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "copilot-state-123",
            },
        )
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        proxy_state = params["state"][0]
        row = asyncio.get_event_loop().run_until_complete(
            db.get_auth_state(proxy_state)
        )
        assert row is not None
        assert row["copilot_state"] == "copilot-state-123"
        assert row["code_verifier"] != ""

    def test_authorize_rejects_unknown_client(self, client):
        resp = client.get(
            "/authorize",
            params={
                "client_id": "unknown",
                "redirect_uri": "https://example.com/cb",
                "response_type": "code",
                "state": "s",
            },
        )
        assert resp.status_code == 400

    def test_authorize_rejects_bad_redirect_uri(self, client, registered_client):
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": "https://evil.com/callback",
                "response_type": "code",
                "state": "s",
            },
        )
        assert resp.status_code == 400
