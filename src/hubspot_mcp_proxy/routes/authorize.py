"""OAuth authorize endpoint - injects PKCE and redirects to HubSpot."""

import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import TokenEncryptor
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.pkce import generate_code_challenge, generate_code_verifier

logger = logging.getLogger(__name__)

_STATE_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.~]{1,512}$")


def create_authorize_router(
    settings: Settings, db: Database, encryptor: TokenEncryptor
) -> APIRouter:
    router = APIRouter()

    @router.get("/authorize", response_model=None)
    async def authorize(
        client_id: str = Query(),
        redirect_uri: str = Query(),
        response_type: str = Query(),
        state: str = Query(),
        scope: str | None = Query(default=None),
    ) -> Response:
        logger.info("Authorize request: client_id=%s scope=%s", client_id, scope)

        # Validate response_type
        if response_type != "code":
            logger.warning(
                "Authorize rejected: unsupported response_type=%s", response_type
            )
            return JSONResponse(
                {"error": "unsupported_response_type"}, status_code=400
            )

        # Validate state format
        if not _STATE_PATTERN.match(state):
            logger.warning("Authorize rejected: invalid state format")
            return JSONResponse({"error": "invalid state"}, status_code=400)

        # Validate client registration
        client = await db.get_client(client_id)
        if client is None:
            logger.warning("Authorize rejected: unknown client_id=%s", client_id)
            return JSONResponse({"error": "unknown client_id"}, status_code=400)

        registered_uris = json.loads(client["redirect_uris"])
        if redirect_uri not in registered_uris:
            logger.warning(
                "Authorize rejected: redirect_uri=%s"
                " not in registered URIs for client_id=%s",
                redirect_uri, client_id,
            )
            return JSONResponse({"error": "invalid redirect_uri"}, status_code=400)

        # Generate PKCE pair
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        # Generate proxy state key
        proxy_state = secrets.token_urlsafe(32)
        ttl = settings.auth_state_ttl_seconds
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl)
        ).isoformat()

        await db.insert_auth_state(
            state_key=proxy_state,
            code_verifier=encryptor.encrypt(code_verifier),
            client_id=client_id,
            redirect_uri=redirect_uri,
            copilot_state=state,
            scope=scope,
            expires_at=expires_at,
        )

        # Build HubSpot authorize URL
        params = {
            "client_id": settings.hubspot_client_id,
            "redirect_uri": f"{settings.proxy_base_url}/callback",
            "response_type": "code",
            "state": proxy_state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if scope:
            params["scope"] = scope

        hubspot_url = f"{settings.hubspot_auth_url}?{urlencode(params)}"
        logger.info(
            "Authorize redirecting to HubSpot: client_id=%s proxy_state=%s",
            client_id, proxy_state,
        )
        logger.debug("HubSpot authorize URL: %s", hubspot_url)
        return RedirectResponse(url=hubspot_url, status_code=302)

    return router
