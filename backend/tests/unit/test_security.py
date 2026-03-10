"""Unit tests for app.utils.security — pure functions, no DB needed."""
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_hash_password_returns_string():
    result = hash_password("mysecretpassword")
    assert isinstance(result, str)
    assert len(result) > 20


def test_hash_password_is_not_plaintext():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert hashed != password


def test_hash_password_different_hashes_for_same_input():
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2


def test_verify_password_correct():
    password = "correct-horse-battery-staple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("rightpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_empty_string():
    hashed = hash_password("somepassword")
    assert verify_password("", hashed) is False


def test_create_access_token_returns_string():
    token = create_access_token({"sub": "user-123", "type": "access"})
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_access_token_round_trip():
    payload = {"sub": "user-abc", "type": "access"}
    token = create_access_token(payload)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-abc"
    assert decoded["type"] == "access"


def test_create_refresh_token_returns_string():
    token = create_refresh_token({"sub": "user-123", "type": "refresh"})
    assert isinstance(token, str)


def test_decode_refresh_token_round_trip():
    payload = {"sub": "user-xyz", "type": "refresh"}
    token = create_refresh_token(payload)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-xyz"
    assert decoded["type"] == "refresh"


def test_decode_token_invalid_returns_none():
    result = decode_token("not.a.valid.jwt")
    assert result is None


def test_decode_token_tampered_returns_none():
    token = create_access_token({"sub": "user-123", "type": "access"})
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + ".invalidsignature"
    result = decode_token(tampered)
    assert result is None


def test_decode_token_empty_string_returns_none():
    result = decode_token("")
    assert result is None
