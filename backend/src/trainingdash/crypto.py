"""AES encryption helpers for sensitive credential storage."""

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from trainingdash.config import settings


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


def _get_key() -> bytes:
    """Get the encryption key from settings, validating it's present and valid."""
    key_b64 = settings.encryption_key
    if not key_b64:
        raise EncryptionError("FITTER_ENCRYPTION_KEY not configured")
    try:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise EncryptionError("FITTER_ENCRYPTION_KEY must be 32 bytes (256-bit) base64-encoded")
        return key
    except Exception as e:
        if isinstance(e, EncryptionError):
            raise
        raise EncryptionError(f"Invalid FITTER_ENCRYPTION_KEY: {e}") from e


def generate_encryption_key() -> str:
    """Generate a new 256-bit encryption key, base64-encoded. For setup/key rotation."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def encrypt(plaintext: str) -> bytes:
    """
    Encrypt plaintext using AES-256-GCM.

    Returns: nonce (12 bytes) + ciphertext + tag (concatenated)
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    return nonce + ciphertext


def decrypt(encrypted: bytes) -> str:
    """
    Decrypt data encrypted with encrypt().

    Args:
        encrypted: nonce (12 bytes) + ciphertext + tag

    Returns: decrypted plaintext string

    Raises: EncryptionError if decryption fails (wrong key, corrupted data, etc.)
    """
    if len(encrypted) < 12 + 16:  # nonce + minimum tag
        raise EncryptionError("Invalid encrypted data: too short")

    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]

    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        # Don't leak details about why decryption failed
        raise EncryptionError("Decryption failed") from e
