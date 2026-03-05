"""Tests for DCR (Dynamic Client Registration) endpoint."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.register import create_register_router

VALID_URI = "https://api.powerva.microsoft.com/callback"


class TestRegister:
    @pytest.fixture
    def client(self, db, settings):
        app = FastAPI()
        app.include_router(create_register_router(db, settings))
        return TestClient(app)

    def test_register_returns_client_credentials(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "client_id" in data
        assert "client_secret" in data
        assert data["redirect_uris"] == [VALID_URI]

    def test_register_with_client_name(self, client):
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [VALID_URI],
                "client_name": "My App",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["client_name"] == "My App"

    async def test_register_stores_in_database(self, client, db):
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        client_id = resp.json()["client_id"]
        row = await db.get_client(client_id)
        assert row is not None
        assert json.loads(row["redirect_uris"]) == [VALID_URI]

    def test_register_requires_redirect_uris(self, client):
        resp = client.post("/register", json={})
        assert resp.status_code == 422

    async def test_register_secret_is_hashed_in_db(self, client, db):
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        data = resp.json()
        row = await db.get_client(data["client_id"])
        # Stored hash should not equal the plaintext secret
        assert row["client_secret_hash"] != data["client_secret"]

    async def test_register_stores_scrypt_hash(self, client, db):
        """Stored hash should be in scrypt format (salt$hash)."""
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        row = await db.get_client(resp.json()["client_id"])
        assert "$" in row["client_secret_hash"]

    def test_register_without_auth_succeeds(self, client):
        """Open registration -- no auth required (IP-restricted at infra level)."""
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        assert resp.status_code == 201


class TestRedirectUriValidation:
    @pytest.fixture
    def client(self, db, settings):
        app = FastAPI()
        app.include_router(create_register_router(db, settings))
        return TestClient(app)

    def test_valid_copilot_studio_uri_accepted(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        assert resp.status_code == 201

    def test_arbitrary_domain_rejected(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://evil.com/steal"]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_redirect_uri"

    def test_http_scheme_rejected(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["http://api.powerva.microsoft.com/callback"]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_redirect_uri"

    def test_subdomain_of_allowed_domain_accepted(self, client):
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [
                    "https://default.api.powerva.microsoft.com/callback"
                ]
            },
        )
        assert resp.status_code == 201

    def test_mixed_valid_and_invalid_rejected(self, client):
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [VALID_URI, "https://evil.com/steal"]
            },
        )
        assert resp.status_code == 400

    def test_custom_allowed_domains(self, db, settings, monkeypatch):
        monkeypatch.setattr(
            settings, "allowed_redirect_domains",
            ["custom.example.com"],
        )
        app = FastAPI()
        app.include_router(create_register_router(db, settings))
        custom_client = TestClient(app)

        resp = custom_client.post(
            "/register",
            json={"redirect_uris": ["https://custom.example.com/cb"]},
        )
        assert resp.status_code == 201

        # Default domain should now be rejected
        resp = custom_client.post(
            "/register",
            json={"redirect_uris": [VALID_URI]},
        )
        assert resp.status_code == 400

    def test_non_subdomain_suffix_rejected(self, client):
        """'notapi.powerva.microsoft.com' is not a subdomain of allowed domain."""
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [
                    "https://notapi.powerva.microsoft.com/callback"
                ]
            },
        )
        assert resp.status_code == 400

    def test_superdomain_rejected(self, client):
        """powerva.microsoft.com alone should not match api.powerva.microsoft.com."""
        resp = client.post(
            "/register",
            json={
                "redirect_uris": ["https://powerva.microsoft.com/callback"]
            },
        )
        assert resp.status_code == 400

    def test_userinfo_in_uri_rejected(self, client):
        """URI with userinfo (user@host) is rejected to prevent open redirect."""
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [
                    "https://evil.com@api.powerva.microsoft.com/callback"
                ]
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_redirect_uri"

    def test_password_userinfo_in_uri_rejected(self, client):
        """URI with user:password@host userinfo is rejected."""
        resp = client.post(
            "/register",
            json={
                "redirect_uris": [
                    "https://user:pass@api.powerva.microsoft.com/callback"
                ]
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_redirect_uri"
