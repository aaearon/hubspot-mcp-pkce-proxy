"""RFC 7591 Dynamic Client Registration endpoint."""

import hashlib
import json
import logging
import secrets
import uuid

from fastapi import APIRouter
from starlette.responses import JSONResponse

from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.models import DCRRequest, DCRResponse

logger = logging.getLogger(__name__)


def create_register_router(db: Database) -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201)
    async def register(request: DCRRequest) -> JSONResponse:
        logger.info("DCR request: client_name=%s redirect_uris=%s", request.client_name, request.redirect_uris)
        client_id = str(uuid.uuid4())
        client_secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

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
        logger.info("DCR registered: client_id=%s client_name=%s", client_id, request.client_name)
        return JSONResponse(content=response.model_dump(), status_code=201)

    return router
