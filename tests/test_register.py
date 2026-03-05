"""Tests for DCR (Dynamic Client Registration) endpoint."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.register import create_register_router


class TestRegister:
    @pytest.fixture
    def client(self, db, settings):
        app = FastAPI()
        app.include_router(create_register_router(db))
        return TestClient(app)

    def test_register_returns_client_credentials(self, client):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "client_id" in data
        assert "client_secret" in data
        assert data["redirect_uris"] == ["https://example.com/callback"]

    def test_register_with_client_name(self, client):
        resp = client.post(
            "/register",
            json={
                "redirect_uris": ["https://example.com/callback"],
                "client_name": "My App",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["client_name"] == "My App"

    async def test_register_stores_in_database(self, client, db):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        client_id = resp.json()["client_id"]
        row = await db.get_client(client_id)
        assert row is not None
        assert json.loads(row["redirect_uris"]) == ["https://example.com/callback"]

    def test_register_requires_redirect_uris(self, client):
        resp = client.post("/register", json={})
        assert resp.status_code == 422

    async def test_register_secret_is_hashed_in_db(self, client, db):
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        data = resp.json()
        row = await db.get_client(data["client_id"])
        # Stored hash should not equal the plaintext secret
        assert row["client_secret_hash"] != data["client_secret"]

    async def test_register_stores_scrypt_hash(self, client, db):
        """Stored hash should be in scrypt format (salt$hash)."""
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        row = await db.get_client(resp.json()["client_id"])
        assert "$" in row["client_secret_hash"]

    def test_register_without_auth_succeeds(self, client):
        """Open registration — no auth required (IP-restricted at infra level)."""
        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        assert resp.status_code == 201
