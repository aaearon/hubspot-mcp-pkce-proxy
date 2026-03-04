"""Tests for DCR (Dynamic Client Registration) endpoint."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.register import create_register_router
from tests.conftest import TEST_REGISTRATION_TOKEN


class TestRegister:
    @pytest.fixture
    def client(self, db, settings):
        app = FastAPI()
        app.include_router(create_register_router(db, settings))
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": f"Bearer {TEST_REGISTRATION_TOKEN}"}

    def test_register_returns_client_credentials(self, client, auth_headers):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "client_id" in data
        assert "client_secret" in data
        assert data["redirect_uris"] == ["https://example.com/callback"]

    def test_register_with_client_name(self, client, auth_headers):
        resp = client.post(
            "/register",
            json={
                "redirect_uris": ["https://example.com/callback"],
                "client_name": "My App",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["client_name"] == "My App"

    async def test_register_stores_in_database(self, client, db, auth_headers):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers=auth_headers,
        )
        client_id = resp.json()["client_id"]
        row = await db.get_client(client_id)
        assert row is not None
        assert json.loads(row["redirect_uris"]) == ["https://example.com/callback"]

    def test_register_requires_redirect_uris(self, client, auth_headers):
        resp = client.post("/register", json={}, headers=auth_headers)
        assert resp.status_code == 422

    async def test_register_secret_is_hashed_in_db(self, client, db, auth_headers):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers=auth_headers,
        )
        data = resp.json()
        row = await db.get_client(data["client_id"])
        # Stored hash should not equal the plaintext secret
        assert row["client_secret_hash"] != data["client_secret"]

    async def test_register_stores_scrypt_hash(self, client, db, auth_headers):
        """Stored hash should be in scrypt format (salt$hash)."""
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers=auth_headers,
        )
        row = await db.get_client(resp.json()["client_id"])
        assert "$" in row["client_secret_hash"]

    def test_register_rejects_missing_auth(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        assert resp.status_code == 401

    def test_register_rejects_invalid_token(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_register_rejects_non_bearer_scheme(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
            headers={"Authorization": f"Basic {TEST_REGISTRATION_TOKEN}"},
        )
        assert resp.status_code == 401
