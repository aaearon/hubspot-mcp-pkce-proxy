"""Tests for OAuth metadata endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.metadata import create_metadata_router


class TestMetadata:
    @pytest.fixture
    def client(self, settings):
        app = FastAPI()
        app.include_router(create_metadata_router(settings))
        return TestClient(app)

    def test_metadata_returns_valid_json(self, client, settings):
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issuer"] == settings.proxy_base_url
        assert data["authorization_endpoint"] == f"{settings.proxy_base_url}/authorize"
        assert data["token_endpoint"] == f"{settings.proxy_base_url}/token"
        assert data["registration_endpoint"] == f"{settings.proxy_base_url}/register"

    def test_metadata_does_not_advertise_pkce(self, client):
        resp = client.get("/.well-known/oauth-authorization-server")
        data = resp.json()
        assert "code_challenge_methods_supported" not in data

    def test_metadata_supported_values(self, client):
        resp = client.get("/.well-known/oauth-authorization-server")
        data = resp.json()
        assert data["response_types_supported"] == ["code"]
        assert "authorization_code" in data["grant_types_supported"]
        assert "refresh_token" in data["grant_types_supported"]
        assert data["token_endpoint_auth_methods_supported"] == ["client_secret_post"]

    def test_openid_configuration_alias(self, client, settings):
        """/.well-known/openid-configuration returns same metadata."""
        resp = client.get("/.well-known/openid-configuration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issuer"] == settings.proxy_base_url
        assert data["authorization_endpoint"] == f"{settings.proxy_base_url}/authorize"
