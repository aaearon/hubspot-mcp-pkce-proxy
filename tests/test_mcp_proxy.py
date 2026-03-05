"""Tests for MCP proxy endpoint."""

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.routes.mcp_proxy import create_mcp_router


class TestMcpProxy:
    @pytest.fixture
    def client(self, settings, hub_client):
        app = FastAPI()
        app.include_router(create_mcp_router(hub_client, settings))
        return TestClient(app)

    @respx.mock
    def test_proxy_forwards_request(self, client, settings):
        mcp_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        respx.post(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                json=mcp_response,
                headers={"content-type": "application/json"},
            )
        )
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == mcp_response

    @respx.mock
    def test_proxy_forwards_auth_header(self, client, settings):
        respx.post(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(200, json={})
        )
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer my-token"},
        )
        request = respx.calls.last.request
        assert request.headers["authorization"] == "Bearer my-token"

    @respx.mock
    def test_proxy_forwards_session_id(self, client, settings):
        respx.post(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                json={},
                headers={"mcp-session-id": "sess-123"},
            )
        )
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={
                "Authorization": "Bearer test-token",
                "Mcp-Session-Id": "sess-123",
            },
        )
        # Verify session ID was forwarded upstream
        request = respx.calls.last.request
        assert request.headers["mcp-session-id"] == "sess-123"

    @respx.mock
    def test_proxy_root_path(self, client, settings):
        mcp_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        respx.post(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(200, json=mcp_response)
        )
        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == mcp_response

    @respx.mock
    def test_proxy_returns_hubspot_error(self, client, settings):
        respx.post(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401

    def test_proxy_rejects_no_auth_header(self, client):
        """POST without Authorization header returns 401 with WWW-Authenticate."""
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "missing authorization header"
        www_auth = resp.headers["www-authenticate"]
        assert "Bearer" in www_auth
        assert "resource_metadata" in www_auth
        assert "/.well-known/oauth-protected-resource" in www_auth

    def test_proxy_root_path_rejects_no_auth(self, client):
        """POST / without Authorization header also returns 401."""
        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 401
        assert "www-authenticate" in resp.headers


class TestMcpGetDiscovery:
    """Tests for GET handler that returns 401 for OAuth discovery."""

    @pytest.fixture
    def client(self, settings, hub_client):
        app = FastAPI()
        app.include_router(create_mcp_router(hub_client, settings))
        return TestClient(app)

    def test_get_mcp_returns_401(self, client):
        """GET /mcp without Authorization returns 401 with WWW-Authenticate."""
        resp = client.get("/mcp")
        assert resp.status_code == 401
        assert resp.json()["error"] == "missing authorization header"
        www_auth = resp.headers["www-authenticate"]
        assert "Bearer" in www_auth
        assert "resource_metadata" in www_auth
        assert "/.well-known/oauth-protected-resource" in www_auth

    def test_get_root_returns_401(self, client):
        """GET / without Authorization returns 401 with WWW-Authenticate."""
        resp = client.get("/")
        assert resp.status_code == 401
        assert resp.json()["error"] == "missing authorization header"
        assert "www-authenticate" in resp.headers

    def test_get_mcp_with_auth_returns_401(self, client):
        """GET /mcp with Authorization also returns 401 (SSE not supported)."""
        resp = client.get("/mcp", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "GET not supported, use POST for MCP requests"

    def test_get_root_with_auth_returns_401(self, client):
        """GET / with Authorization also returns 401 (SSE not supported)."""
        resp = client.get("/", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "GET not supported, use POST for MCP requests"
