import base64
import hashlib
import hmac
import json


def _b64url_decode(value: str) -> bytes:
    text = (value or "").strip()
    if not text:
        raise ValueError("Empty base64url value")
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("utf-8"))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def decode_whatsapp_session_bundle(session_string: str, session_secret: str) -> dict:
    """
    Decode and verify signed WhatsApp userbot bundle received from wa_bridge.
    Returns payload dict with at least provider/phone_number/auth_files keys.
    """
    raw = (session_string or "").strip()
    if not raw:
        raise ValueError("session_string is empty")
    secret = (session_secret or "").strip()
    if len(secret) < 32:
        raise ValueError("WA_USERBOT_SESSION_SECRET is not configured")

    try:
        wrapper = json.loads(_b64url_decode(raw).decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid wrapper format: {exc}") from exc

    version = int(wrapper.get("v") or 0)
    payload_b64 = str(wrapper.get("payload") or "")
    signature_b64 = str(wrapper.get("signature") or "")
    if version != 1 or not payload_b64 or not signature_b64:
        raise ValueError("Invalid bundle envelope")

    payload_bytes = _b64url_decode(payload_b64)
    expected_sig_b64 = _b64url_encode(hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest())
    if not hmac.compare_digest(expected_sig_b64, signature_b64):
        raise ValueError("Invalid bundle signature")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid bundle payload: {exc}") from exc

    if str(payload.get("provider") or "") != "whatsapp_userbot":
        raise ValueError("Invalid provider in bundle")
    if not isinstance(payload.get("auth_files"), dict) or not payload["auth_files"]:
        raise ValueError("auth_files are missing in bundle")
    return payload
