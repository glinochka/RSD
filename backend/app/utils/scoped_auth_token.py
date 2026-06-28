"""Short-lived JWT tokens scoped to a single auth flow (userbot, etc.)."""

from __future__ import annotations

from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError

from ..config import settings

USERBOT_AUTH_TOKEN_TTL_MINUTES = 10


class ScopedAuthToken:
    def __init__(
        self,
        scope: str,
        ttl_minutes: int = USERBOT_AUTH_TOKEN_TTL_MINUTES,
        *,
        invalid_detail: str,
        scope_mismatch_detail: str,
        missing_key_detail: str | None = None,
    ) -> None:
        self.scope = scope
        self.ttl_minutes = ttl_minutes
        self._invalid_detail = invalid_detail
        self._scope_mismatch_detail = scope_mismatch_detail
        self._missing_key_detail = missing_key_detail or "Токен не содержит обязательных данных"

    def create(self, **claims) -> str:
        now = datetime.utcnow()
        payload = {
            "scope": self.scope,
            **claims,
            "exp": now + timedelta(minutes=self.ttl_minutes),
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def decode(self, token: str, *, required_keys: list[str] | None = None) -> dict:
        try:
            data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=self._invalid_detail,
            ) from None
        if data.get("scope") != self.scope:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=self._scope_mismatch_detail,
            )
        if required_keys:
            for key in required_keys:
                value = data.get(key)
                if value is None or (isinstance(value, str) and not str(value).strip()):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=self._missing_key_detail,
                    )
        return data


userbot_auth_token = ScopedAuthToken(
    "userbot_auth",
    invalid_detail="Невалидный или просроченный токен подтверждения userbot",
    scope_mismatch_detail="Некорректный scope токена подтверждения userbot",
)

userbot_qr_auth_token = ScopedAuthToken(
    "userbot_qr_auth",
    invalid_detail="Невалидный или просроченный токен QR-входа userbot",
    scope_mismatch_detail="Некорректный scope токена QR-входа userbot",
    missing_key_detail="Токен QR-входа userbot не содержит auth_id",
)

max_userbot_auth_token = ScopedAuthToken(
    "max_userbot_auth",
    invalid_detail="Невалидный или просроченный токен подтверждения MAX userbot",
    scope_mismatch_detail="Некорректный scope токена подтверждения MAX userbot",
    missing_key_detail="Токен MAX userbot не содержит auth_id",
)

whatsapp_userbot_auth_token = ScopedAuthToken(
    "whatsapp_userbot_auth",
    invalid_detail="Невалидный или просроченный токен подтверждения WhatsApp userbot",
    scope_mismatch_detail="Некорректный scope токена подтверждения WhatsApp userbot",
    missing_key_detail="Токен подтверждения WhatsApp userbot не привязан к пользователю",
)
