"""HTTP client for HubSpot API calls."""

import logging
from typing import Any

import httpx

from hubspot_mcp_proxy.config import Settings

logger = logging.getLogger(__name__)


class HubSpotClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(timeout=30.0)

    async def exchange_code(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange authorization code + PKCE verifier for tokens."""
        logger.debug("HubSpot exchange_code: redirect_uri=%s", redirect_uri)
        resp = await self._http.post(
            self._settings.hubspot_token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": self._settings.hubspot_client_id,
                "client_secret": self._settings.hubspot_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": code_verifier,
            },
        )
        logger.debug("HubSpot exchange_code response: status=%d", resp.status_code)
        return {"status_code": resp.status_code, "data": resp.json()}

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an access token using HubSpot's client credentials."""
        logger.debug("HubSpot refresh_token request")
        resp = await self._http.post(
            self._settings.hubspot_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": self._settings.hubspot_client_id,
                "client_secret": self._settings.hubspot_client_secret,
                "refresh_token": refresh_token,
            },
        )
        logger.debug("HubSpot refresh_token response: status=%d", resp.status_code)
        return {"status_code": resp.status_code, "data": resp.json()}

    async def proxy_mcp(
        self, body: bytes, headers: dict[str, str]
    ) -> httpx.Response:
        """Forward an MCP request to HubSpot, streaming the response."""
        forward_headers = {}
        for key in ("authorization", "content-type", "mcp-session-id"):
            if key in headers:
                forward_headers[key] = headers[key]

        logger.debug("HubSpot MCP proxy: url=%s", self._settings.hubspot_mcp_url)
        return await self._http.post(
            self._settings.hubspot_mcp_url,
            content=body,
            headers=forward_headers,
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._http.aclose()
