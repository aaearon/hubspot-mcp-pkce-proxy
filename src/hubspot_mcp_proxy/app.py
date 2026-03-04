"""FastAPI application factory with async lifespan."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.crypto import TokenEncryptor
from hubspot_mcp_proxy.db import Database
from hubspot_mcp_proxy.hub_client import HubSpotClient
from hubspot_mcp_proxy.routes.authorize import create_authorize_router
from hubspot_mcp_proxy.routes.callback import create_callback_router
from hubspot_mcp_proxy.routes.mcp_proxy import create_mcp_router
from hubspot_mcp_proxy.routes.metadata import create_metadata_router
from hubspot_mcp_proxy.routes.register import create_register_router
from hubspot_mcp_proxy.routes.token import create_token_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    logger.info("Starting HubSpot MCP PKCE Proxy")
    logger.info("Proxy base URL: %s", settings.proxy_base_url)
    logger.info("HubSpot auth URL: %s", settings.hubspot_auth_url)
    logger.info("HubSpot token URL: %s", settings.hubspot_token_url)
    logger.info("HubSpot MCP URL: %s", settings.hubspot_mcp_url)
    logger.info("Database path: %s", settings.database_path)
    logger.info("Log level: %s", settings.log_level)

    db = Database(settings.database_path)
    http_client = httpx.AsyncClient(timeout=30.0)
    hub_client = HubSpotClient(settings, http_client)
    encryptor = TokenEncryptor(settings.token_encryption_key)

    async def _cleanup_loop(interval: int = 300) -> None:
        """Periodically purge expired auth states and codes."""
        while True:
            await asyncio.sleep(interval)
            try:
                await db.cleanup_expired()
                logger.debug("Expired records cleaned up")
            except Exception:
                logger.exception("Cleanup task failed")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Initializing database at %s", settings.database_path)
        await db.init()
        logger.info("Database initialized")
        cleanup_task = asyncio.create_task(_cleanup_loop())
        yield
        logger.info("Shutting down...")
        cleanup_task.cancel()
        await hub_client.close()
        await db.close()
        logger.info("Shutdown complete")

    app = FastAPI(title="HubSpot MCP PKCE Proxy", lifespan=lifespan)

    app.include_router(create_metadata_router(settings))
    app.include_router(create_register_router(db, settings))
    app.include_router(create_authorize_router(settings, db, encryptor))
    app.include_router(create_callback_router(settings, db, hub_client, encryptor))
    app.include_router(create_token_router(settings, db, hub_client, encryptor))
    app.include_router(create_mcp_router(hub_client))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
