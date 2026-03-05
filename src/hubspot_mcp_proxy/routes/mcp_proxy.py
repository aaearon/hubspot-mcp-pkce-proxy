"""MCP HTTP reverse proxy to HubSpot."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.hub_client import HubSpotClient

logger = logging.getLogger(__name__)


def _rewrite_endpoint_events(body: bytes, proxy_base_url: str) -> bytes:
    """Rewrite SSE endpoint event URLs from HubSpot to our proxy."""
    lines = body.split(b"\n")
    result = []
    prev_was_endpoint = False
    for line in lines:
        if line == b"event: endpoint":
            prev_was_endpoint = True
            result.append(line)
        elif prev_was_endpoint and line.startswith(b"data: "):
            # Rewrite HubSpot URL to our proxy URL
            rewritten = proxy_base_url.rstrip("/") + "/mcp"
            result.append(b"data: " + rewritten.encode())
            prev_was_endpoint = False
        else:
            prev_was_endpoint = False
            result.append(line)
    return b"\n".join(result)


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
                {"error": "missing authorization header"}, status_code=401
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
    async def mcp_sse_proxy(request: Request) -> Response:
        headers = {k: v for k, v in request.headers.items()}

        # Return 401 to trigger OAuth discovery flow in MCP clients
        if "authorization" not in headers:
            logger.warning("MCP SSE proxy rejected: missing authorization header")
            return JSONResponse(
                {"error": "missing authorization header"}, status_code=401
            )

        session_id = headers.get("mcp-session-id", "none")
        logger.info("MCP SSE proxy GET: session=%s", session_id)

        upstream = await hub_client.stream_mcp_sse(headers)

        logger.info(
            "MCP SSE proxy response: status=%d session=%s",
            upstream.status_code, session_id,
        )

        # Rewrite endpoint events if present
        content = _rewrite_endpoint_events(upstream.content, settings.proxy_base_url)

        # Preserve key response headers
        response_headers = {}
        for key in ("content-type", "mcp-session-id"):
            if key in upstream.headers:
                response_headers[key] = upstream.headers[key]

        return Response(
            content=content,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    return router
