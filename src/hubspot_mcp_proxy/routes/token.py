"""Token endpoint - authorization_code and refresh_token grants."""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient

logger = logging.getLogger(__name__)


def create_token_router(
    settings: Settings, db: Database, hub_client: HubSpotClient
) -> APIRouter:
    router = APIRouter()

    async def _validate_client(client_id: str, client_secret: str) -> dict | None:
        """Validate client credentials, return client row or None."""
        client = await db.get_client(client_id)
        if client is None:
            return None
        expected = hashlib.sha256(client_secret.encode()).hexdigest()
        if not hmac.compare_digest(client["client_secret_hash"], expected):
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
        logger.info(
            "Token request: grant_type=%s client_id=%s",
            grant_type, client_id,
        )

        if not client_id or not client_secret:
            logger.warning("Token rejected: missing client credentials")
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        client = await _validate_client(client_id, client_secret)
        if client is None:
            logger.warning(
                "Token rejected: invalid creds for client_id=%s",
                client_id,
            )
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        if grant_type == "authorization_code":
            if not code:
                return JSONResponse(
                    {"error": "invalid_request", "error_description": "code required"},
                    status_code=400,
                )
            auth_code = await db.get_and_delete_auth_code(code)
            if auth_code is None:
                logger.warning(
                    "Token rejected: invalid/expired code"
                    " for client_id=%s", client_id,
                )
                return JSONResponse(
                    {"error": "invalid_grant"}, status_code=400
                )
            if auth_code["client_id"] != client_id:
                logger.warning(
                    "Token rejected: code client_id mismatch:"
                    " expected=%s got=%s",
                    auth_code["client_id"], client_id,
                )
                return JSONResponse(
                    {"error": "invalid_grant"}, status_code=400
                )
            logger.info(
                "Token issued via auth_code for client_id=%s",
                client_id,
            )
            return JSONResponse(
                {
                    "access_token": auth_code["access_token"],
                    "token_type": auth_code["token_type"],
                    "expires_in": auth_code["expires_in"],
                    "refresh_token": auth_code["refresh_token"],
                },
                headers={"Cache-Control": "no-store"},
            )

        elif grant_type == "refresh_token":
            if not refresh_token:
                return JSONResponse(
                    {
                        "error": "invalid_request",
                        "error_description": "refresh_token required",
                    },
                    status_code=400,
                )
            logger.info("Refreshing token via HubSpot for client_id=%s", client_id)
            result = await hub_client.refresh_token(refresh_token)
            if result["status_code"] != 200:
                logger.error(
                    "HubSpot refresh failed: status=%d response=%s",
                    result["status_code"], result["data"],
                )
                return JSONResponse(
                    {"error": "invalid_grant"},
                    status_code=502,
                )
            data = result["data"]
            logger.info("Token refreshed successfully for client_id=%s", client_id)
            return JSONResponse(
                {
                    "access_token": data["access_token"],
                    "token_type": data.get("token_type", "bearer"),
                    "expires_in": data.get("expires_in"),
                    "refresh_token": data.get("refresh_token"),
                },
                headers={"Cache-Control": "no-store"},
            )

        else:
            logger.warning(
                "Unsupported grant_type=%s from client_id=%s",
                grant_type, client_id,
            )
            return JSONResponse(
                {"error": "unsupported_grant_type"}, status_code=400
            )

    return router
