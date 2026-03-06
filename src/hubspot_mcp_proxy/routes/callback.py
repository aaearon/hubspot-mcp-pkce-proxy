"""OAuth callback endpoint - receives HubSpot auth code, exchanges for tokens."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import TokenEncryptor
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient

logger = logging.getLogger(__name__)


def create_callback_router(
    settings: Settings,
    db: Database,
    hub_client: HubSpotClient,
    encryptor: TokenEncryptor,
) -> APIRouter:
    router = APIRouter()

    @router.get("/callback", response_model=None)
    async def callback(
        state: str = Query(),
        code: str | None = Query(default=None),
        error: str | None = Query(default=None),
        error_description: str | None = Query(default=None),
    ) -> Response:
        logger.info("Callback received: state=%s", state)

        # Handle OAuth error response from HubSpot
        if error:
            auth_state = await db.get_auth_state(state)
            if auth_state is None:
                logger.warning(
                    "Callback error with unknown state=%s error=%s", state, error
                )
                return JSONResponse(
                    {"error": "unknown or expired state"}, status_code=400
                )
            await db.delete_auth_state(state)
            params = {
                "error": error,
                "state": auth_state["copilot_state"],
            }
            if error_description:
                params["error_description"] = error_description
            redirect_url = (
                f"{auth_state['redirect_uri']}?{urlencode(params)}"
            )
            logger.warning(
                "Callback forwarding OAuth error=%s to client_id=%s",
                error, auth_state["client_id"],
            )
            return RedirectResponse(url=redirect_url, status_code=302)

        # No code and no error — invalid request
        if not code:
            logger.warning("Callback missing both code and error params")
            return JSONResponse(
                {"error": "missing code or error parameter"}, status_code=400
            )

        # Look up the proxy auth state
        auth_state = await db.get_auth_state(state)
        if auth_state is None:
            logger.warning("Callback rejected: unknown or expired state=%s", state)
            return JSONResponse({"error": "unknown or expired state"}, status_code=400)

        logger.info(
            "Callback exchanging code with HubSpot: client_id=%s",
            auth_state["client_id"],
        )

        # Exchange with HubSpot using PKCE verifier (decrypt from storage)
        try:
            code_verifier = encryptor.decrypt(auth_state["code_verifier"])
        except InvalidToken:
            logger.error(
                "Corrupt encrypted verifier for state=%s, deleting", state
            )
            await db.delete_auth_state(state)
            return JSONResponse(
                {"error": "invalid_grant"}, status_code=400
            )

        result = await hub_client.exchange_code(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=f"{settings.proxy_base_url}/callback",
        )

        if result["status_code"] != 200:
            logger.error(
                "HubSpot token exchange failed: status=%d response=%s",
                result["status_code"], result["data"],
            )
            return JSONResponse(
                {"error": "hubspot token exchange failed"},
                status_code=502,
            )

        # Clean up used state only after successful exchange
        await db.delete_auth_state(state)

        token_data = result["data"]

        # Generate proxy auth code and store HubSpot tokens
        proxy_code = secrets.token_urlsafe(32)
        ttl = settings.auth_code_ttl_seconds
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl)
        ).isoformat()

        raw_refresh = token_data.get("refresh_token")
        await db.insert_auth_code(
            code=proxy_code,
            access_token=encryptor.encrypt(token_data["access_token"]),
            refresh_token=encryptor.encrypt(raw_refresh) if raw_refresh else None,
            token_type=token_data.get("token_type", "bearer"),
            expires_in=token_data.get("expires_in"),
            client_id=auth_state["client_id"],
            expires_at=expires_at,
        )

        # Redirect back to Copilot Studio with proxy code
        params = {"code": proxy_code, "state": auth_state["copilot_state"]}
        redirect_url = f"{auth_state['redirect_uri']}?{urlencode(params)}"
        logger.info(
            "Callback success: issuing proxy code for client_id=%s, redirecting to %s",
            auth_state["client_id"], auth_state["redirect_uri"],
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    return router
