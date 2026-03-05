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


class TestMcpGetSseProxy:
    """Tests for GET SSE proxy (Streamable HTTP / legacy SSE transport)."""

    @pytest.fixture
    def client(self, settings, hub_client):
        app = FastAPI()
        app.include_router(create_mcp_router(hub_client, settings))
        return TestClient(app)

    @respx.mock
    def test_get_sse_stream(self, client, settings):
        """GET /mcp with Authorization returns 200 with SSE content-type."""
        sse_body = b"event: message\ndata: {\"jsonrpc\":\"2.0\"}\n\n"
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        resp = client.get(
            "/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert b"event: message" in resp.content

    @respx.mock
    def test_get_sse_forwards_auth_header(self, client, settings):
        """GET forwards Authorization header to HubSpot."""
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=b"event: message\ndata: {}\n\n",
                headers={"content-type": "text/event-stream"},
            )
        )
        client.get(
            "/mcp",
            headers={"Authorization": "Bearer my-token"},
        )
        request = respx.calls.last.request
        assert request.headers["authorization"] == "Bearer my-token"

    @respx.mock
    def test_get_sse_forwards_session_id(self, client, settings):
        """GET forwards Mcp-Session-Id header to HubSpot."""
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=b"event: message\ndata: {}\n\n",
                headers={
                    "content-type": "text/event-stream",
                    "mcp-session-id": "sess-456",
                },
            )
        )
        resp = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer test-token",
                "Mcp-Session-Id": "sess-456",
            },
        )
        # Verify forwarded upstream
        request = respx.calls.last.request
        assert request.headers["mcp-session-id"] == "sess-456"
        # Verify returned in response
        assert resp.headers["mcp-session-id"] == "sess-456"

    def test_get_sse_rejects_no_auth(self, client):
        """GET /mcp without Authorization returns 401 to trigger OAuth flow."""
        resp = client.get("/mcp")
        assert resp.status_code == 401
        assert resp.json()["error"] == "missing authorization header"

    @respx.mock
    def test_get_root_sse_stream(self, client, settings):
        """GET / also works as SSE proxy."""
        sse_body = b"event: message\ndata: {\"jsonrpc\":\"2.0\"}\n\n"
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        resp = client.get(
            "/",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert b"event: message" in resp.content

    @respx.mock
    def test_get_sse_rewrites_endpoint_event(self, client, settings):
        """SSE endpoint event URL is rewritten to proxy URL."""
        sse_body = (
            b"event: endpoint\n"
            b"data: https://mcp.hubspot.com/messages?session=abc123\n\n"
        )
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        resp = client.get(
            "/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        body = resp.content.decode()
        # Should be rewritten to proxy URL
        assert "https://proxy.example.com/mcp" in body
        # Original HubSpot URL should be replaced
        assert "https://mcp.hubspot.com/messages" not in body

    @respx.mock
    def test_get_sse_passes_non_endpoint_events(self, client, settings):
        """Non-endpoint SSE events pass through unchanged."""
        sse_body = (
            b"event: message\n"
            b"data: {\"jsonrpc\":\"2.0\",\"method\":\"tools/list\"}\n\n"
        )
        respx.get(settings.hubspot_mcp_url).mock(
            return_value=httpx.Response(
                200,
                content=sse_body,
                headers={"content-type": "text/event-stream"},
            )
        )
        resp = client.get(
            "/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
        body = resp.content.decode()
        assert 'event: message\n' in body
        assert '{"jsonrpc":"2.0","method":"tools/list"}' in body
