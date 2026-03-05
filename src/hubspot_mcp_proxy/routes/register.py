"""RFC 7591 Dynamic Client Registration endpoint."""

import json
import logging
import secrets
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter
from starlette.responses import JSONResponse

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import hash_client_secret
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.models import DCRRequest, DCRResponse

logger = logging.getLogger(__name__)


def _validate_redirect_uris(
    uris: list[str], allowed_domains: list[str],
) -> str | None:
    """Return an error message if any URI is invalid, else None."""
    for uri in uris:
        parsed = urlparse(uri)
        if parsed.scheme != "https":
            return f"redirect_uri must use https scheme: {uri}"
        if parsed.username is not None or parsed.password is not None:
            return f"redirect_uri must not contain userinfo: {uri}"
        hostname = parsed.hostname
        if not hostname:
            return f"redirect_uri has no hostname: {uri}"
        if not any(
            hostname == domain or hostname.endswith("." + domain)
            for domain in allowed_domains
        ):
            return f"redirect_uri domain not in allowlist: {hostname}"
    return None


def create_register_router(db: Database, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201)
    async def register(request: DCRRequest) -> JSONResponse:
        logger.info(
            "DCR request: client_name=%s uris=%s",
            request.client_name, request.redirect_uris,
        )

        error = _validate_redirect_uris(
            request.redirect_uris, settings.allowed_redirect_domains,
        )
        if error:
            logger.warning("DCR rejected: %s", error)
            return JSONResponse(
                content={"error": "invalid_redirect_uri", "error_description": error},
                status_code=400,
            )

        client_id = str(uuid.uuid4())
        client_secret = secrets.token_urlsafe(32)
        secret_hash = hash_client_secret(client_secret)

        await db.insert_client(
            client_id=client_id,
            client_secret_hash=secret_hash,
            redirect_uris=json.dumps(request.redirect_uris),
            client_name=request.client_name,
        )

        response = DCRResponse(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=request.redirect_uris,
            client_name=request.client_name,
        )
        logger.info(
            "DCR registered: client_id=%s name=%s",
            client_id, request.client_name,
        )
        return JSONResponse(content=response.model_dump(), status_code=201)

    return router
