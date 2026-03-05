"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hubspot_client_id: str
    hubspot_client_secret: str
    proxy_base_url: str

    hubspot_auth_url: str = "https://app.hubspot.com/oauth/authorize"
    hubspot_token_url: str = "https://api.hubapi.com/oauth/v1/token"
    hubspot_mcp_url: str = "https://mcp.hubspot.com"
    database_path: str = ":memory:"
    auth_state_ttl_seconds: int = 600
    auth_code_ttl_seconds: int = 300
    log_level: str = "INFO"
    registration_token: str
    token_encryption_key: str
