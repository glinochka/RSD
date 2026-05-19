from __future__ import annotations

import hashlib
import hmac


def sign_webhook(secret: str, timestamp: str, connection_id: int, raw_body: bytes) -> str:
    prefix = f"v1\n{timestamp}\n{connection_id}\n".encode()
    return hmac.new(secret.encode(), prefix + raw_body, hashlib.sha256).hexdigest()


def test_signature_deterministic():
    body = b'{"event":"call.inbound","connection_id":5}'
    sig1 = sign_webhook("secret", "100", 5, body)
    sig2 = sign_webhook("secret", "100", 5, body)
    assert sig1 == sig2


def test_signature_changes_with_connection_id():
    body = b"{}"
    assert sign_webhook("secret", "100", 1, body) != sign_webhook("secret", "100", 2, body)
