"""RFC 7591 Dynamic Client Registration endpoint."""

import hmac
import json
import logging
import secrets
import uuid

from fastapi import APIRouter, Header
from starlette.responses import JSONResponse

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import hash_client_secret
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.models import DCRRequest, DCRResponse

logger = logging.getLogger(__name__)


def create_register_router(db: Database, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201)
    async def register(
        request: DCRRequest,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        # Validate bearer token
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning("DCR rejected: missing or invalid authorization")
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        token = authorization[7:]  # strip "Bearer "
        if not hmac.compare_digest(token, settings.registration_token):
            logger.warning("DCR rejected: invalid registration token")
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        logger.info(
            "DCR request: client_name=%s uris=%s",
            request.client_name, request.redirect_uris,
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
