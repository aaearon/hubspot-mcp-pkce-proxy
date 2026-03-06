"""Tests for the callback endpoint."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.callback import create_callback_router


class TestCallback:
    @pytest.fixture
    async def stored_state(self, db, encryptor):
        """Insert a pending auth state with encrypted verifier."""
        expires = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
        encrypted_verifier = encryptor.encrypt("test-verifier-123")
        await db.insert_auth_state(
            state_key="proxy-state-abc",
            code_verifier=encrypted_verifier,
            client_id="test-client-id",
            redirect_uri="https://copilot.example.com/callback",
            copilot_state="copilot-state-xyz",
            scope="crm.objects.contacts.read",
            expires_at=expires,
        )
        return "proxy-state-abc"

    @pytest.fixture
    def client(self, settings, db, hub_client, encryptor):
        app = FastAPI()
        app.include_router(
            create_callback_router(settings, db, hub_client, encryptor)
        )
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
        assert resp.status_code == 302
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
    async def test_callback_hubspot_error_returns_502(
        self, client, db, settings, stored_state
    ):
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(401, json={"error": "invalid"})
        )
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "proxy-state-abc"},
        )
        assert resp.status_code == 502
        assert "detail" not in resp.json()
        # State should be preserved so the user can retry
        remaining = await db.get_auth_state("proxy-state-abc")
        assert remaining is not None

    def test_callback_oauth_error_redirects_to_client(
        self, client, stored_state
    ):
        """OAuth error from HubSpot is forwarded to the client redirect_uri."""
        resp = client.get(
            "/callback",
            params={
                "error": "access_denied",
                "state": "proxy-state-abc",
            },
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        assert parsed.netloc == "copilot.example.com"
        assert params["error"] == ["access_denied"]
        assert params["state"] == ["copilot-state-xyz"]

    def test_callback_oauth_error_with_description(self, client, stored_state):
        """Error description is forwarded alongside error."""
        resp = client.get(
            "/callback",
            params={
                "error": "access_denied",
                "error_description": "User denied access",
                "state": "proxy-state-abc",
            },
        )
        assert resp.status_code == 302
        params = parse_qs(urlparse(resp.headers["location"]).query)
        assert params["error_description"] == ["User denied access"]

    def test_callback_oauth_error_unknown_state(self, client):
        """OAuth error with unknown state returns 400."""
        resp = client.get(
            "/callback",
            params={
                "error": "access_denied",
                "state": "unknown-state",
            },
        )
        assert resp.status_code == 400

    def test_callback_no_code_no_error(self, client, stored_state):
        """Neither code nor error present returns 400."""
        resp = client.get(
            "/callback",
            params={"state": "proxy-state-abc"},
        )
        assert resp.status_code == 400

    @respx.mock
    async def test_callback_corrupt_verifier_returns_400(
        self, client, db, settings
    ):
        """Corrupt encrypted verifier returns 400, not 500."""
        expires = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
        await db.insert_auth_state(
            state_key="corrupt-state",
            code_verifier="not-valid-fernet-ciphertext",
            client_id="test-client-id",
            redirect_uri="https://copilot.example.com/callback",
            copilot_state="copilot-state-xyz",
            scope="crm.objects.contacts.read",
            expires_at=expires,
        )
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "corrupt-state"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"
        # Corrupt state should be cleaned up
        remaining = await db.get_auth_state("corrupt-state")
        assert remaining is None

    @respx.mock
    async def test_callback_stores_encrypted_tokens(
        self, client, db, settings, stored_state, encryptor
    ):
        """Tokens stored after exchange should be encrypted."""
        respx.post(settings.hubspot_token_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "hs-plaintext-token",
                    "refresh_token": "hs-plaintext-refresh",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        )
        resp = client.get(
            "/callback",
            params={"code": "hubspot-auth-code", "state": "proxy-state-abc"},
        )
        assert resp.status_code == 302
        from urllib.parse import parse_qs, urlparse

        proxy_code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]
        row = await db.get_auth_code(proxy_code)
        # Stored values should NOT be plaintext
        assert row["access_token"] != "hs-plaintext-token"
        assert row["refresh_token"] != "hs-plaintext-refresh"
        # But should decrypt correctly
        assert encryptor.decrypt(row["access_token"]) == "hs-plaintext-token"
        assert encryptor.decrypt(row["refresh_token"]) == "hs-plaintext-refresh"
