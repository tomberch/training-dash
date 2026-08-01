"""Unit tests for encryption/decryption helpers."""

import base64
import os
from unittest import mock

import pytest

from fitter.crypto import encrypt, decrypt, generate_encryption_key, EncryptionError


@pytest.fixture
def valid_encryption_key():
    """Generate a valid 32-byte base64-encoded key."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture
def mock_settings_with_key(valid_encryption_key):
    """Mock settings with a valid encryption key."""
    with mock.patch("fitter.crypto.settings") as mock_settings:
        mock_settings.encryption_key = valid_encryption_key
        yield mock_settings


class TestEncryption:
    def test_encrypt_decrypt_round_trip(self, mock_settings_with_key):
        """Encrypted data should decrypt back to the original plaintext."""
        plaintext = "my-secret-password-123!"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_decrypt_unicode(self, mock_settings_with_key):
        """Should handle unicode characters correctly."""
        plaintext = "password-with-emoji-🔐-and-中文"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_output_each_time(self, mock_settings_with_key):
        """Due to random nonce, encrypting same plaintext produces different ciphertext."""
        plaintext = "test-password"
        encrypted1 = encrypt(plaintext)
        encrypted2 = encrypt(plaintext)
        assert encrypted1 != encrypted2
        # But both should decrypt to the same value
        assert decrypt(encrypted1) == plaintext
        assert decrypt(encrypted2) == plaintext

    def test_encrypted_data_format(self, mock_settings_with_key):
        """Encrypted data should be nonce (12 bytes) + ciphertext + tag."""
        plaintext = "test"
        encrypted = encrypt(plaintext)
        # Should be at least 12 (nonce) + 4 (plaintext) + 16 (tag) = 32 bytes
        assert len(encrypted) >= 32
        # First 12 bytes are the nonce
        assert len(encrypted[:12]) == 12

    def test_decrypt_with_wrong_key_raises(self, valid_encryption_key):
        """Decrypting with a different key should raise EncryptionError."""
        # Encrypt with one key
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = valid_encryption_key
            encrypted = encrypt("secret-data")

        # Try to decrypt with a different key
        different_key = base64.b64encode(os.urandom(32)).decode("ascii")
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = different_key
            with pytest.raises(EncryptionError, match="Decryption failed"):
                decrypt(encrypted)

    def test_decrypt_corrupted_data_raises(self, mock_settings_with_key):
        """Decrypting corrupted data should raise EncryptionError."""
        encrypted = encrypt("test-data")
        # Corrupt the ciphertext (not the nonce)
        corrupted = encrypted[:12] + bytes([encrypted[12] ^ 0xFF]) + encrypted[13:]
        with pytest.raises(EncryptionError, match="Decryption failed"):
            decrypt(corrupted)

    def test_decrypt_too_short_data_raises(self, mock_settings_with_key):
        """Decrypting data shorter than nonce + tag should raise."""
        with pytest.raises(EncryptionError, match="too short"):
            decrypt(b"short")

    def test_encrypt_without_key_raises(self):
        """Encrypting without FITTER_ENCRYPTION_KEY configured should raise."""
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = None
            with pytest.raises(EncryptionError, match="not configured"):
                encrypt("test")

    def test_decrypt_without_key_raises(self, valid_encryption_key):
        """Decrypting without FITTER_ENCRYPTION_KEY configured should raise."""
        # First encrypt with a valid key
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = valid_encryption_key
            encrypted = encrypt("test")

        # Then try to decrypt without a key
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = None
            with pytest.raises(EncryptionError, match="not configured"):
                decrypt(encrypted)

    def test_invalid_key_format_raises(self):
        """Invalid base64 key should raise EncryptionError."""
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = "not-valid-base64!!!"
            with pytest.raises(EncryptionError, match="Invalid"):
                encrypt("test")

    def test_wrong_key_length_raises(self):
        """Key that's not 32 bytes should raise EncryptionError."""
        short_key = base64.b64encode(os.urandom(16)).decode("ascii")  # 16 bytes, not 32
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = short_key
            with pytest.raises(EncryptionError, match="32 bytes"):
                encrypt("test")


class TestGenerateKey:
    def test_generate_encryption_key_length(self):
        """Generated key should decode to 32 bytes."""
        key = generate_encryption_key()
        decoded = base64.b64decode(key)
        assert len(decoded) == 32

    def test_generate_encryption_key_unique(self):
        """Each generated key should be unique."""
        keys = [generate_encryption_key() for _ in range(10)]
        assert len(set(keys)) == 10

    def test_generated_key_works_for_encryption(self):
        """Generated key should work for encrypt/decrypt."""
        key = generate_encryption_key()
        with mock.patch("fitter.crypto.settings") as mock_settings:
            mock_settings.encryption_key = key
            plaintext = "test-secret"
            encrypted = encrypt(plaintext)
            decrypted = decrypt(encrypted)
            assert decrypted == plaintext
