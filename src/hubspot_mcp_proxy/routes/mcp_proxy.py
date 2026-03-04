"""MCP HTTP reverse proxy to HubSpot."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from hubspot_mcp_proxy.hub_client import HubSpotClient

logger = logging.getLogger(__name__)


def create_mcp_router(hub_client: HubSpotClient) -> APIRouter:
    router = APIRouter()

    @router.post("/mcp")
    @router.post("/")
    async def mcp_proxy(request: Request) -> Response:
        body = await request.body()
        headers = {k: v for k, v in request.headers.items()}

        session_id = headers.get("mcp-session-id", "none")
        has_auth = "authorization" in headers
        logger.info(
            "MCP proxy request: session=%s auth=%s len=%d",
            session_id, has_auth, len(body),
        )
        logger.debug("MCP request body: %s", body[:500])

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

    return router
