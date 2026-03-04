"""Tests for token endpoint."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.crypto import hash_client_secret
from hubspot_mcp_proxy.routes.token import create_token_router


class TestToken:
    @pytest.fixture
    async def setup_client_and_code(self, db, encryptor):
        """Register a client and store a proxy auth code with encrypted tokens."""
        client_id = "test-client-id"
        client_secret = "test-client-secret"
        secret_hash = hash_client_secret(client_secret)

        await db.insert_client(
            client_id=client_id,
            client_secret_hash=secret_hash,
            redirect_uris=json.dumps(["https://copilot.example.com/callback"]),
        )

        expires = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        await db.insert_auth_code(
            code="proxy-code-123",
            access_token=encryptor.encrypt("hs-access-token"),
            refresh_token=encryptor.encrypt("hs-refresh-token"),
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
    def client(self, settings, db, hub_client, encryptor):
        app = FastAPI()
        app.include_router(create_token_router(settings, db, hub_client, encryptor))
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

    @respx.mock
    def test_refresh_token_hubspot_error_no_detail(
        self, client, settings, setup_client_and_code
    ):
        """Upstream error responses must not leak HubSpot detail to clients."""
        info = setup_client_and_code
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(
                401, json={"message": "Invalid refresh token", "correlationId": "abc"}
            )
        )
        resp = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "bad-token",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code == 502
        assert "detail" not in resp.json()

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

    async def test_auth_code_client_id_mismatch(
        self, client, db, setup_client_and_code
    ):
        """Auth code issued for client A cannot be redeemed by client B."""
        info = setup_client_and_code
        # Register a second client
        other_secret = "other-client-secret"
        other_hash = hash_client_secret(other_secret)
        await db.insert_client(
            client_id="other-client-id",
            client_secret_hash=other_hash,
            redirect_uris=json.dumps(["https://other.example.com/callback"]),
        )
        # Try to redeem client A's code with client B's credentials
        resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": info["code"],
                "client_id": "other-client-id",
                "client_secret": other_secret,
                "redirect_uri": "https://other.example.com/callback",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"

    async def test_token_works_with_legacy_sha256_hash(
        self, client, db, encryptor
    ):
        """Clients with legacy SHA-256 hashes should still authenticate."""
        client_secret = "legacy-secret"
        legacy_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        await db.insert_client(
            client_id="legacy-client",
            client_secret_hash=legacy_hash,
            redirect_uris=json.dumps(["https://example.com/callback"]),
        )
        expires = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        await db.insert_auth_code(
            code="legacy-code",
            access_token=encryptor.encrypt("legacy-access"),
            refresh_token=encryptor.encrypt("legacy-refresh"),
            token_type="bearer",
            expires_in=3600,
            client_id="legacy-client",
            expires_at=expires,
        )
        resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": "legacy-code",
                "client_id": "legacy-client",
                "client_secret": client_secret,
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "legacy-access"

    def test_token_response_cache_control(self, client, setup_client_and_code):
        """Token responses must include Cache-Control: no-store (RFC 6749)."""
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
        assert resp.headers.get("cache-control") == "no-store"
