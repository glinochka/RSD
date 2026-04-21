import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


APP_TITLE = "WhatsApp Userbot Bridge"
AUTH_TTL_SECONDS = int(os.getenv("WA_USERBOT_AUTH_TTL_SECONDS", "600"))
AUTH_MAX_ATTEMPTS = int(os.getenv("WA_USERBOT_AUTH_MAX_ATTEMPTS", "5"))
BRIDGE_API_KEY = os.getenv("WA_USERBOT_BRIDGE_API_KEY", "").strip()
SESSION_SECRET = os.getenv("WA_USERBOT_SESSION_SECRET", "wa-bridge-dev-secret")
DEV_EXPOSE_CODE_IN_HINT = os.getenv("WA_USERBOT_DEV_EXPOSE_CODE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title=APP_TITLE)
_auth_store_lock = Lock()
_auth_store: dict[str, dict] = {}


class RequestCodePayload(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=32)


class VerifyCodePayload(BaseModel):
    auth_id: str = Field(..., min_length=8, max_length=128)
    phone_number: str = Field(..., min_length=5, max_length=32)
    code: str = Field(..., min_length=3, max_length=64)


def _normalize_phone(phone_number: str) -> str:
    raw = (phone_number or "").strip()
    cleaned_digits = "".join(ch for ch in raw if ch.isdigit())
    if len(cleaned_digits) < 5:
        raise HTTPException(status_code=422, detail="Некорректный номер WhatsApp")
    if raw.startswith("+"):
        return f"+{cleaned_digits}"
    return f"+{cleaned_digits}"


def _normalize_code(code: str) -> str:
    value = (code or "").strip()
    compact = "".join(ch for ch in value if ch.isdigit())
    return compact or value


def _sign_payload(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), data, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(data + b"." + signature).decode("utf-8")


def _authorize_bridge(x_api_key: str | None) -> None:
    if BRIDGE_API_KEY and (x_api_key or "").strip() != BRIDGE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid bridge API key")


def _cleanup_expired() -> None:
    now = _utc_now()
    expired = [auth_id for auth_id, item in _auth_store.items() if item["expires_at"] <= now]
    for auth_id in expired:
        _auth_store.pop(auth_id, None)


@app.get("/health")
async def health():
    return {"status": "ok", "service": APP_TITLE}


@app.post("/auth/request_code")
async def request_code(payload: RequestCodePayload, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _authorize_bridge(x_api_key)
    normalized_phone = _normalize_phone(payload.phone_number)
    verification_code = "".join(secrets.choice("0123456789") for _ in range(6))
    auth_id = f"wauth_{secrets.token_urlsafe(18)}"
    now = _utc_now()

    with _auth_store_lock:
        _cleanup_expired()
        _auth_store[auth_id] = {
            "phone_number": normalized_phone,
            "code": verification_code,
            "attempts_left": AUTH_MAX_ATTEMPTS,
            "created_at": now,
            "expires_at": now + timedelta(seconds=AUTH_TTL_SECONDS),
        }

    hint = "Код отправлен. Введите код для подтверждения."
    if DEV_EXPOSE_CODE_IN_HINT:
        hint = f"{hint} DEV code: {verification_code}"

    return {
        "auth_id": auth_id,
        "delivery": "pairing_code",
        "hint": hint,
        "expires_in_seconds": AUTH_TTL_SECONDS,
    }


@app.post("/auth/verify_code")
async def verify_code(payload: VerifyCodePayload, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _authorize_bridge(x_api_key)
    normalized_phone = _normalize_phone(payload.phone_number)
    normalized_code = _normalize_code(payload.code)
    auth_id = payload.auth_id.strip()

    with _auth_store_lock:
        _cleanup_expired()
        pending = _auth_store.get(auth_id)
        if not pending:
            raise HTTPException(status_code=404, detail="Сессия подтверждения не найдена или истекла")
        if pending["phone_number"] != normalized_phone:
            raise HTTPException(status_code=422, detail="Номер телефона не совпадает с сессией подтверждения")
        if pending["attempts_left"] <= 0:
            _auth_store.pop(auth_id, None)
            raise HTTPException(status_code=429, detail="Превышено число попыток подтверждения")
        if normalized_code != pending["code"]:
            pending["attempts_left"] -= 1
            raise HTTPException(status_code=422, detail="Неверный код подтверждения WhatsApp")
        _auth_store.pop(auth_id, None)

    session_payload = {
        "provider": "whatsapp_userbot",
        "auth_id": auth_id,
        "phone_number": normalized_phone,
        "issued_at": _utc_now().isoformat(),
    }
    session_string = _sign_payload(session_payload)
    return {
        "session_string": session_string,
        "phone_number": normalized_phone,
        "external_user_id": normalized_phone.lstrip("+"),
        "display_name": f"WA {normalized_phone}",
    }
