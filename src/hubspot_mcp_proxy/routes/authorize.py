"""OAuth authorize endpoint - injects PKCE and redirects to HubSpot."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.pkce import generate_code_challenge, generate_code_verifier


def create_authorize_router(settings: Settings, db: Database) -> APIRouter:
    router = APIRouter()

    @router.get("/authorize", response_model=None)
    async def authorize(
        client_id: str = Query(),
        redirect_uri: str = Query(),
        response_type: str = Query(),
        state: str = Query(),
        scope: str | None = Query(default=None),
    ) -> Response:
        # Validate client registration
        client = await db.get_client(client_id)
        if client is None:
            return JSONResponse({"error": "unknown client_id"}, status_code=400)

        registered_uris = json.loads(client["redirect_uris"])
        if redirect_uri not in registered_uris:
            return JSONResponse({"error": "invalid redirect_uri"}, status_code=400)

        # Generate PKCE pair
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

        # Generate proxy state key
        proxy_state = secrets.token_urlsafe(32)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=settings.auth_state_ttl_seconds)
        ).isoformat()

        await db.insert_auth_state(
            state_key=proxy_state,
            code_verifier=code_verifier,
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
        return RedirectResponse(url=hubspot_url, status_code=307)

    return router
