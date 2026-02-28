"""Tests for PKCE utilities."""

import base64
import hashlib

from hubspot_mcp_proxy.pkce import generate_code_challenge, generate_code_verifier


class TestPkce:
    def test_verifier_length(self):
        """Code verifier must be 43-128 characters (RFC 7636)."""
        verifier = generate_code_verifier()
        assert 43 <= len(verifier) <= 128

    def test_verifier_uniqueness(self):
        """Each call produces a different verifier."""
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2

    def test_verifier_charset(self):
        """Verifier uses only unreserved URI characters."""
        import re

        verifier = generate_code_verifier()
        assert re.fullmatch(r"[A-Za-z0-9\-._~]+", verifier)

    def test_challenge_is_s256(self):
        """Challenge is SHA-256 of verifier, base64url-encoded, no padding."""
        verifier = "test-verifier-value"
        challenge = generate_code_challenge(verifier)
        expected = (
            base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        assert challenge == expected

    def test_challenge_no_padding(self):
        """Challenge must not contain base64 padding characters."""
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        assert "=" not in challenge
