"""Tests for DCR (Dynamic Client Registration) endpoint."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.routes.register import create_register_router


class TestRegister:
    @pytest.fixture
    def client(self, db):
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

    def test_register_stores_in_database(self, client, db):
        import asyncio

        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        client_id = resp.json()["client_id"]
        row = asyncio.get_event_loop().run_until_complete(db.get_client(client_id))
        assert row is not None
        assert json.loads(row["redirect_uris"]) == ["https://example.com/callback"]

    def test_register_requires_redirect_uris(self, client):
        resp = client.post("/register", json={})
        assert resp.status_code == 422

    def test_register_secret_is_hashed_in_db(self, client, db):
        import asyncio

        resp = client.post(
            "/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        data = resp.json()
        row = asyncio.get_event_loop().run_until_complete(
            db.get_client(data["client_id"])
        )
        # Stored hash should not equal the plaintext secret
        assert row["client_secret_hash"] != data["client_secret"]
