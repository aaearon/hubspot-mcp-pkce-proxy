"""End-to-end integration test through the full OAuth + MCP flow."""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from hubspot_mcp_proxy.app import create_app
from hubspot_mcp_proxy.config import Settings


class TestIntegration:
    @pytest.fixture
    def settings(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HUBSPOT_CLIENT_ID", "hs-client-id")
        monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "hs-client-secret")
        monkeypatch.setenv("PROXY_BASE_URL", "https://proxy.example.com")
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "integration.db"))
        return Settings()

    @pytest.fixture
    def client(self, settings):
        app = create_app(settings)
        with TestClient(app, follow_redirects=False) as c:
            yield c

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_full_oauth_flow(self, client, settings):
        """Complete flow: discover -> register -> authorize ->
        callback -> token -> mcp."""

        # 1. Discover metadata
        meta = client.get("/.well-known/oauth-authorization-server").json()
        assert meta["issuer"] == settings.proxy_base_url

        # 2. Register client via DCR
        reg = client.post(
            "/register",
            json={
                "redirect_uris": ["https://copilot.example.com/callback"],
                "client_name": "Integration Test",
            },
        ).json()
        dcr_client_id = reg["client_id"]
        dcr_client_secret = reg["client_secret"]

        # 3. Authorize (capture redirect to HubSpot)
        auth_resp = client.get(
            "/authorize",
            params={
                "client_id": dcr_client_id,
                "redirect_uri": "https://copilot.example.com/callback",
                "response_type": "code",
                "state": "copilot-state-abc",
                "scope": "crm.objects.contacts.read",
            },
        )
        assert auth_resp.status_code == 302
        hubspot_url = urlparse(auth_resp.headers["location"])
        hubspot_params = parse_qs(hubspot_url.query)
        assert hubspot_params["code_challenge_method"] == ["S256"]
        proxy_state = hubspot_params["state"][0]

        # 4. Simulate HubSpot callback (mock token exchange)
        with respx.mock:
            respx.post(settings.hubspot_token_url).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "hs-access-token-xyz",
                        "refresh_token": "hs-refresh-token-xyz",
                        "token_type": "bearer",
                        "expires_in": 3600,
                    },
                )
            )

            callback_resp = client.get(
                "/callback",
                params={"code": "hubspot-auth-code-123", "state": proxy_state},
            )
        assert callback_resp.status_code == 302
        copilot_redirect = urlparse(callback_resp.headers["location"])
        copilot_params = parse_qs(copilot_redirect.query)
        assert copilot_params["state"] == ["copilot-state-abc"]
        proxy_code = copilot_params["code"][0]

        # 5. Exchange proxy code for tokens
        token_resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": proxy_code,
                "client_id": dcr_client_id,
                "client_secret": dcr_client_secret,
                "redirect_uri": "https://copilot.example.com/callback",
            },
        )
        assert token_resp.status_code == 200
        tokens = token_resp.json()
        assert tokens["access_token"] == "hs-access-token-xyz"
        assert tokens["refresh_token"] == "hs-refresh-token-xyz"

        # 6. MCP proxy request
        mcp_response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        with respx.mock:
            respx.post(settings.hubspot_mcp_url).mock(
                return_value=httpx.Response(200, json=mcp_response)
            )

            mcp_resp = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            assert mcp_resp.status_code == 200
            assert mcp_resp.json() == mcp_response

            # Verify the MCP request forwarded the auth header
            mcp_request = respx.calls.last.request
            expected = f"Bearer {tokens['access_token']}"
            assert mcp_request.headers["authorization"] == expected
