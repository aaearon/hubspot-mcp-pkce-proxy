"""RFC 8414 OAuth Authorization Server Metadata endpoint."""

from fastapi import APIRouter

from hubspot_mcp_proxy.config import Settings
from hubspot_mcp_proxy.models import OAuthMetadata


def create_metadata_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    base = settings.proxy_base_url
    _cached = OAuthMetadata(
        issuer=base,
        authorization_endpoint=f"{base}/authorize",
        token_endpoint=f"{base}/token",
        registration_endpoint=f"{base}/register",
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        token_endpoint_auth_methods_supported=["client_secret_post"],
    )

    @router.get("/.well-known/oauth-authorization-server")
    @router.get("/.well-known/openid-configuration")
    async def metadata() -> OAuthMetadata:
        return _cached

    return router
