"""Unit tests for app.services.encryption — Fernet encrypt/decrypt."""
import pytest
from app.services.encryption import encrypt_api_key, decrypt_api_key


def test_encrypt_returns_different_string():
    plaintext = "sk-test-this-is-a-real-api-key"
    encrypted = encrypt_api_key(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)


def test_decrypt_round_trip():
    plaintext = "sk-test-this-is-a-real-api-key"
    encrypted = encrypt_api_key(plaintext)
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == plaintext


def test_encrypt_same_input_different_output():
    """Fernet uses random IV — same plaintext produces different ciphertext."""
    key = "my-secret-oauth-token"
    c1 = encrypt_api_key(key)
    c2 = encrypt_api_key(key)
    assert c1 != c2


def test_decrypt_wrong_data_raises():
    """Decrypting garbage should raise an exception."""
    with pytest.raises(Exception):
        decrypt_api_key("not-valid-fernet-data")
