"""MCP HTTP reverse proxy to HubSpot."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from hubspot_mcp_proxy.hub_client import HubSpotClient


def create_mcp_router(hub_client: HubSpotClient) -> APIRouter:
    router = APIRouter()

    @router.post("/mcp")
    async def mcp_proxy(request: Request) -> Response:
        body = await request.body()
        headers = {k: v for k, v in request.headers.items()}

        upstream = await hub_client.proxy_mcp(body, headers)

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
