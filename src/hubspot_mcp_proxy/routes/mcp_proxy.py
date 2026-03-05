"""MCP Streamable HTTP proxy to HubSpot."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.hub_client import HubSpotClient

logger = logging.getLogger(__name__)


def _www_authenticate(proxy_base_url: str) -> str:
    """Build WWW-Authenticate header value per RFC 9728."""
    prm_url = f"{proxy_base_url.rstrip('/')}/.well-known/oauth-protected-resource"
    return f'Bearer resource_metadata="{prm_url}"'


def create_mcp_router(hub_client: HubSpotClient, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/mcp")
    @router.post("/")
    async def mcp_proxy(request: Request) -> Response:
        body = await request.body()
        headers = {k: v for k, v in request.headers.items()}

        # Reject requests without Authorization header
        if "authorization" not in headers:
            logger.warning("MCP proxy rejected: missing authorization header")
            return JSONResponse(
                {"error": "missing authorization header"},
                status_code=401,
                headers={
                    "WWW-Authenticate": _www_authenticate(settings.proxy_base_url),
                },
            )

        session_id = headers.get("mcp-session-id", "none")
        logger.info(
            "MCP proxy request: session=%s len=%d",
            session_id, len(body),
        )

        upstream = await hub_client.proxy_mcp(body, headers)

        logger.info(
            "MCP proxy response: status=%d session=%s",
            upstream.status_code, session_id,
        )
        if upstream.status_code >= 400:
            logger.warning(
                "MCP upstream error: status=%d body=%s",
                upstream.status_code, upstream.text[:500],
            )

        # Preserve key response headers
        response_headers = {}
        for key in ("content-type", "mcp-session-id"):
            if key in upstream.headers:
                response_headers[key] = upstream.headers[key]

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    @router.get("/mcp")
    @router.get("/")
    async def mcp_get(request: Request) -> Response:
        """Return 401 to trigger OAuth discovery in MCP clients.

        HubSpot MCP uses Streamable HTTP (POST only). GET requests are
        only useful as the initial unauthenticated probe that kicks off
        RFC 9728 protected-resource-metadata discovery.
        """
        www_auth = _www_authenticate(settings.proxy_base_url)

        if "authorization" not in request.headers:
            logger.info("GET %s: no auth, returning 401 for OAuth discovery",
                        request.url.path)
            return JSONResponse(
                {"error": "missing authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": www_auth},
            )

        logger.warning("GET %s: auth present but GET not supported",
                        request.url.path)
        return JSONResponse(
            {"error": "GET not supported, use POST for MCP requests"},
            status_code=401,
            headers={"WWW-Authenticate": www_auth},
        )

    return router
