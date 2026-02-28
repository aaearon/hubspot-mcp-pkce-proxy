"""Token endpoint - authorization_code and refresh_token grants."""

import hashlib

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient


def create_token_router(
    settings: Settings, db: Database, hub_client: HubSpotClient
) -> APIRouter:
    router = APIRouter()

    async def _validate_client(client_id: str, client_secret: str) -> dict | None:
        """Validate client credentials, return client row or None."""
        client = await db.get_client(client_id)
        if client is None:
            return None
        expected_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        if client["client_secret_hash"] != expected_hash:
            return None
        return client

    @router.post("/token")
    async def token(
        grant_type: str = Form(),
        code: str | None = Form(default=None),
        redirect_uri: str | None = Form(default=None),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
        refresh_token: str | None = Form(default=None),
    ) -> JSONResponse:
        if not client_id or not client_secret:
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        client = await _validate_client(client_id, client_secret)
        if client is None:
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        if grant_type == "authorization_code":
            if not code:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "code required"},
                    status_code=400,
                )
            auth_code = await db.get_and_delete_auth_code(code)
            if auth_code is None:
                return JSONResponse(
                    {"error": "invalid_grant"}, status_code=400
                )
            return JSONResponse({
                "access_token": auth_code["access_token"],
                "token_type": auth_code["token_type"],
                "expires_in": auth_code["expires_in"],
                "refresh_token": auth_code["refresh_token"],
            })

        elif grant_type == "refresh_token":
            if not refresh_token:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "refresh_token required"},
                    status_code=400,
                )
            result = await hub_client.refresh_token(refresh_token)
            if result["status_code"] != 200:
                return JSONResponse(
                    {"error": "invalid_grant", "detail": result["data"]},
                    status_code=result["status_code"],
                )
            data = result["data"]
            return JSONResponse({
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in"),
                "refresh_token": data.get("refresh_token"),
            })

        else:
            return JSONResponse(
                {"error": "unsupported_grant_type"}, status_code=400
            )

    return router
