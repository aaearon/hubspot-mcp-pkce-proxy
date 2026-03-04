"""Tests for the crypto module (Fernet encryption + scrypt hashing)."""

import hashlib

import pytest

from hubspot_mcp_proxy.crypto import (
    TokenEncryptor,
    hash_client_secret,
    verify_client_secret,
)


class TestTokenEncryptor:
    @pytest.fixture
    def encryptor(self):
        from cryptography.fernet import Fernet

        return TokenEncryptor(Fernet.generate_key().decode())

    def test_encrypt_decrypt_roundtrip(self, encryptor):
        plaintext = "my-secret-token-value"
        ciphertext = encryptor.encrypt(plaintext)
        assert encryptor.decrypt(ciphertext) == plaintext

    def test_ciphertext_differs_from_plaintext(self, encryptor):
        plaintext = "my-secret-token-value"
        ciphertext = encryptor.encrypt(plaintext)
        assert ciphertext != plaintext

    def test_decrypt_invalid_ciphertext_raises(self, encryptor):
        with pytest.raises(Exception):
            encryptor.decrypt("not-valid-ciphertext")

    def test_different_keys_cannot_decrypt(self):
        from cryptography.fernet import Fernet

        enc1 = TokenEncryptor(Fernet.generate_key().decode())
        enc2 = TokenEncryptor(Fernet.generate_key().decode())
        ciphertext = enc1.encrypt("secret")
        with pytest.raises(Exception):
            enc2.decrypt(ciphertext)


class TestClientSecretHashing:
    def test_hash_and_verify_roundtrip(self):
        secret = "my-client-secret"
        stored = hash_client_secret(secret)
        assert verify_client_secret(secret, stored) is True

    def test_verify_wrong_secret_returns_false(self):
        stored = hash_client_secret("correct-secret")
        assert verify_client_secret("wrong-secret", stored) is False

    def test_hash_produces_salted_format(self):
        stored = hash_client_secret("test-secret")
        assert "$" in stored

    def test_different_hashes_for_same_secret(self):
        h1 = hash_client_secret("same-secret")
        h2 = hash_client_secret("same-secret")
        assert h1 != h2  # Random salt should produce different hashes

    def test_verify_legacy_sha256_format(self):
        """Backward compat: verify against plain SHA-256 hex digest."""
        secret = "legacy-secret"
        legacy_hash = hashlib.sha256(secret.encode()).hexdigest()
        assert verify_client_secret(secret, legacy_hash) is True
        assert verify_client_secret("wrong", legacy_hash) is False
