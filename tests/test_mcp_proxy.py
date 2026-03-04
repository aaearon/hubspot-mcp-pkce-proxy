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
        app.include_router(create_mcp_router(hub_client))
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
        """POST without Authorization header returns 401."""
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "missing authorization header"

    def test_proxy_root_path_rejects_no_auth(self, client):
        """POST / without Authorization header also returns 401."""
        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )
        assert resp.status_code == 401
