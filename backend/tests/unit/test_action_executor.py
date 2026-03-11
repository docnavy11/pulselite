import hashlib
import hmac
import json

from app.services.action_executor import compute_signature


def test_compute_signature_deterministic():
    secret = "mysecret"
    payload = {"event": "lead.submit", "email": "user@example.com"}
    sig1 = compute_signature(secret, payload)
    sig2 = compute_signature(secret, payload)
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex digest


def test_compute_signature_differs_with_different_secret():
    payload = {"event": "test"}
    assert compute_signature("secret1", payload) != compute_signature("secret2", payload)


def test_compute_signature_matches_stdlib():
    secret = "test-secret"
    payload = {"key": "value", "num": 42}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert compute_signature(secret, payload) == expected
