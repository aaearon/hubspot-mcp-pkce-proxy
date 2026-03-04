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
    def client(self, settings, db, encryptor):
        app = FastAPI()
        app.include_router(create_authorize_router(settings, db, encryptor))
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
        assert resp.status_code == 302
        location = resp.headers["location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        assert parsed.scheme == "https"
        assert parsed.hostname == "app.hubspot.com"
        assert params["client_id"] == [settings.hubspot_client_id]
        assert params["response_type"] == ["code"]
        assert "code_challenge" in params
        assert params["code_challenge_method"] == ["S256"]

    async def test_authorize_stores_state(self, client, db, registered_client):
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
        row = await db.get_auth_state(proxy_state)
        assert row is not None
        assert row["copilot_state"] == "copilot-state-123"
        assert row["code_verifier"] != ""

    async def test_authorize_encrypts_code_verifier(
        self, client, db, encryptor, registered_client
    ):
        """Stored code_verifier should be encrypted, not plaintext."""
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "copilot-state-456",
            },
        )
        parsed = urlparse(resp.headers["location"])
        proxy_state = parse_qs(parsed.query)["state"][0]
        row = await db.get_auth_state(proxy_state)
        stored_verifier = row["code_verifier"]
        # Should be encrypted (starts with gAAAAA for Fernet)
        assert stored_verifier.startswith("gAAAAA")
        # Should decrypt to a valid verifier
        decrypted = encryptor.decrypt(stored_verifier)
        assert len(decrypted) >= 43  # PKCE verifiers are 43+ chars

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

    def test_authorize_rejects_state_too_long(self, client, registered_client):
        """State longer than 512 chars is rejected."""
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "a" * 513,
            },
        )
        assert resp.status_code == 400

    def test_authorize_rejects_state_bad_chars(self, client, registered_client):
        """State with HTML/script chars is rejected."""
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "<script>alert(1)</script>",
            },
        )
        assert resp.status_code == 400

    def test_authorize_accepts_valid_base64url_state(
        self, client, registered_client
    ):
        """State with base64url chars, dots, tildes is accepted."""
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "code",
                "state": "abc-DEF_123.~",
            },
        )
        assert resp.status_code == 302

    def test_authorize_rejects_token_response_type(
        self, client, registered_client
    ):
        """response_type=token (implicit grant) is rejected."""
        resp = client.get(
            "/authorize",
            params={
                "client_id": registered_client["client_id"],
                "redirect_uri": registered_client["redirect_uri"],
                "response_type": "token",
                "state": "valid-state",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "unsupported_response_type"
