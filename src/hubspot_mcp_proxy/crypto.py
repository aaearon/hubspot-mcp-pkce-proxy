"""Cryptographic utilities: Fernet token encryption and scrypt secret hashing."""

import hashlib
import hmac
import os

from cryptography.fernet import Fernet


class TokenEncryptor:
    """Encrypt/decrypt tokens at rest using Fernet symmetric encryption."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()


def hash_client_secret(secret: str) -> str:
    """Hash a client secret using scrypt. Returns 'salt_hex$hash_hex'."""
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        secret.encode(), salt=salt, n=16384, r=8, p=1, dklen=32
    )
    return f"{salt.hex()}${derived.hex()}"


def verify_client_secret(secret: str, stored: str) -> bool:
    """Verify a secret against a stored hash.

    Supports scrypt (salt$hash) and legacy SHA-256 hex digest.
    """
    if "$" in stored:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        derived = hashlib.scrypt(
            secret.encode(), salt=salt, n=16384, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(derived.hex(), hash_hex)
    else:
        # Legacy SHA-256 fallback
        expected = hashlib.sha256(secret.encode()).hexdigest()
        return hmac.compare_digest(expected, stored)
