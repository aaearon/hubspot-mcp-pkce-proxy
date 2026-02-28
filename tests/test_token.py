"""Tests for token endpoint."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient
from hubspot_mcp_proxy.routes.token import create_token_router


class TestToken:
    @pytest.fixture
    def hub_client(self, settings):
        return HubSpotClient(settings)

    @pytest.fixture
    async def setup_client_and_code(self, db):
        """Register a client and store a proxy auth code."""
        client_id = "test-client-id"
        client_secret = "test-client-secret"
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        await db.insert_client(
            client_id=client_id,
            client_secret_hash=secret_hash,
            redirect_uris=json.dumps(["https://copilot.example.com/callback"]),
        )

        expires = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        await db.insert_auth_code(
            code="proxy-code-123",
            access_token="hs-access-token",
            refresh_token="hs-refresh-token",
            token_type="bearer",
            expires_in=3600,
            client_id=client_id,
            expires_at=expires,
        )
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": "proxy-code-123",
        }

    @pytest.fixture
    def client(self, settings, db, hub_client):
        app = FastAPI()
        app.include_router(create_token_router(settings, db, hub_client))
        return TestClient(app)

    def test_authorization_code_grant(self, client, setup_client_and_code):
        info = setup_client_and_code
        resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": info["code"],
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
                "redirect_uri": "https://copilot.example.com/callback",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "hs-access-token"
        assert data["refresh_token"] == "hs-refresh-token"
        assert data["token_type"] == "bearer"

    def test_authorization_code_consumed(self, client, setup_client_and_code):
        """Code can only be used once."""
        info = setup_client_and_code
        data = {
            "grant_type": "authorization_code",
            "code": info["code"],
            "client_id": info["client_id"],
            "client_secret": info["client_secret"],
            "redirect_uri": "https://copilot.example.com/callback",
        }
        client.post("/token", data=data)
        resp2 = client.post("/token", data=data)
        assert resp2.status_code == 400

    def test_bad_client_secret(self, client, setup_client_and_code):
        info = setup_client_and_code
        resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": info["code"],
                "client_id": info["client_id"],
                "client_secret": "wrong-secret",
                "redirect_uri": "https://copilot.example.com/callback",
            },
        )
        assert resp.status_code == 401

    @respx.mock
    def test_refresh_token_grant(self, client, settings, setup_client_and_code):
        info = setup_client_and_code
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        )
        resp = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "hs-refresh-token",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "new-access-token"

    def test_unsupported_grant_type(self, client, setup_client_and_code):
        info = setup_client_and_code
        resp = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code == 400
