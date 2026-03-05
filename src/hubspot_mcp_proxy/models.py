"""Pydantic request/response models."""

from pydantic import BaseModel


class DCRRequest(BaseModel):
    redirect_uris: list[str]
    client_name: str | None = None
    grant_types: list[str] | None = None


class DCRResponse(BaseModel):
    client_id: str
    client_secret: str
    redirect_uris: list[str]
    client_name: str | None = None


class TokenRequest(BaseModel):
    grant_type: str
    code: str | None = None
    redirect_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str | None = None


class OAuthMetadata(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    response_types_supported: list[str]
    grant_types_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    code_challenge_methods_supported: list[str] | None = None
