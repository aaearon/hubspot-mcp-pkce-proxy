"""PKCE (Proof Key for Code Exchange) utilities per RFC 7636."""

import base64
import hashlib
import secrets


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier (43-128 chars)."""
    return secrets.token_urlsafe(32)


def generate_code_challenge(verifier: str) -> str:
    """Compute S256 code challenge: BASE64URL(SHA256(verifier)), no padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
