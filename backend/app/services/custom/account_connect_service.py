"""Single Telegram account connect for /custom: QR (+ 2FA) and SMS (+ 2FA)."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AccountClass, PoolAccount, SocialAccount
from ...utils.crypto import decrypt_token, encrypt_token
from ...utils.scoped_auth_token import custom_account_qr_auth_token, custom_account_sms_auth_token
from ..account_pool_service import add_account_from_session_string
from ..telegram_userbot_auth import (
    TelegramUserbotAuthError,
    complete_qr_2fa,
    create_telegram_client,
    get_qr_status,
    start_qr_login,
)

_ALLOWED_CLASSES = {item.value for item in AccountClass}
_persist_lock = asyncio.Lock()
_persisted_by_auth_id: dict[str, tuple[int, int]] = {}


def normalize_assign_class(value: str | None) -> str:
    raw = (value or "").strip() or AccountClass.ONE_DAY.value
    if raw not in _ALLOWED_CLASSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неизвестный класс аккаунта")
    return raw


def _display_name(me: dict[str, Any] | None) -> str | None:
    if not me:
        return None
    parts = [str(me.get("first_name") or "").strip(), str(me.get("last_name") or "").strip()]
    name = " ".join(part for part in parts if part).strip()
    return name or None


def _profile_phone(me: dict[str, Any] | None) -> str | None:
    if not me:
        return None
    phone = str(me.get("phone_number") or me.get("phone") or "").strip()
    return phone or None


def _profile_username(me: dict[str, Any] | None) -> str | None:
    if not me:
        return None
    username = str(me.get("username") or "").strip().lstrip("@")
    return username or None


def _telegram_id(me: dict[str, Any] | None) -> int | None:
    if not me:
        return None
    raw = me.get("telegram_id") or me.get("id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value or None


def _create_qr_token(
    *,
    automation_id: int,
    api_id: int,
    api_hash: str,
    auth_id: str,
    pending_session: str,
    assign_class: str,
    proxy_id: int | None = None,
) -> str:
    return custom_account_qr_auth_token.create(
        automation_id=int(automation_id),
        api_id=int(api_id),
        encrypted_api_hash=encrypt_token(api_hash),
        auth_id=str(auth_id),
        encrypted_pending_session=encrypt_token(pending_session or ""),
        assign_class=assign_class,
        proxy_id=int(proxy_id) if proxy_id else 0,
    )


def decode_qr_token(auth_token: str, automation_id: int) -> dict:
    data = custom_account_qr_auth_token.decode(auth_token, required_keys=["auth_id"])
    token_automation_id = int(data.get("automation_id") or 0)
    if token_automation_id != int(automation_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен QR-входа от другой автоматизации")
    return data


def _create_sms_token(
    *,
    automation_id: int,
    api_id: int,
    api_hash: str,
    phone_number: str,
    phone_code_hash: str,
    pending_session: str,
    assign_class: str,
    proxy_id: int | None = None,
) -> str:
    return custom_account_sms_auth_token.create(
        automation_id=int(automation_id),
        api_id=int(api_id),
        encrypted_api_hash=encrypt_token(api_hash),
        phone_number=phone_number,
        phone_code_hash=phone_code_hash,
        encrypted_pending_session=encrypt_token(pending_session or ""),
        assign_class=assign_class,
        proxy_id=int(proxy_id) if proxy_id else 0,
    )


def decode_sms_token(auth_token: str, automation_id: int) -> dict:
    data = custom_account_sms_auth_token.decode(auth_token, required_keys=["phone_number", "phone_code_hash"])
    token_automation_id = int(data.get("automation_id") or 0)
    if token_automation_id != int(automation_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен SMS-входа от другой автоматизации")
    return data


async def _load_persisted(
    session: AsyncSession,
    auth_id: str,
    automation_id: int,
) -> tuple[PoolAccount, SocialAccount] | None:
    ids = _persisted_by_auth_id.get(auth_id)
    if not ids:
        return None
    pool_account = await session.get(PoolAccount, ids[0])
    social_account = await session.get(SocialAccount, ids[1])
    if not pool_account or not social_account:
        return None
    if int(pool_account.custom_automation_id) != int(automation_id):
        return None
    return pool_account, social_account


async def persist_authorized_session(
    session: AsyncSession,
    automation_id: int,
    *,
    auth_id: str,
    session_string: str,
    assign_class: str,
    me: dict[str, Any] | None = None,
    preferred_proxy_id: int | None = None,
) -> tuple[PoolAccount, SocialAccount, bool]:
    async with _persist_lock:
        existing = await _load_persisted(session, auth_id, automation_id)
        if existing:
            return existing[0], existing[1], False
        try:
            pair = await add_account_from_session_string(
                session,
                automation_id,
                session_string=session_string,
                assign_class=assign_class,
                phone_number=_profile_phone(me),
                username=_profile_username(me),
                display_name=_display_name(me),
                telegram_id=_telegram_id(me),
                preferred_proxy_id=preferred_proxy_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        _persisted_by_auth_id[auth_id] = (pair[0].id, pair[1].id)
        return pair[0], pair[1], True


def _token_proxy_id(token_data: dict[str, Any]) -> int | None:
    raw = token_data.get("proxy_id")
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return None
    return value or None


async def start_account_qr(
    session: AsyncSession,
    automation_id: int,
    *,
    assign_class: str | None = None,
) -> dict[str, Any]:
    from .proxy_service import resolve_connect_proxy

    chosen_class = normalize_assign_class(assign_class)
    proxy_id, proxy = await resolve_connect_proxy(session, automation_id)
    try:
        result = await start_qr_login(proxy=proxy)
    except TelegramUserbotAuthError:
        raise
    except Exception as exc:
        raise TelegramUserbotAuthError(f"Не удалось начать QR-вход: {exc}") from exc

    api_id = int(result.get("api_id") or 0)
    api_hash = str(result.get("api_hash") or "")
    auth_id = str(result["auth_id"])
    pending = str(result.get("pending_session_string") or "")
    auth_token = _create_qr_token(
        automation_id=automation_id,
        api_id=api_id,
        api_hash=api_hash,
        auth_id=auth_id,
        pending_session=pending,
        assign_class=chosen_class,
        proxy_id=proxy_id,
    )
    payload: dict[str, Any] = {
        "auth_token": auth_token,
        "qr_url": result.get("qr_url") or "",
        "qr_data_url": result.get("qr_data_url") or "",
        "already_authorized": bool(result.get("already_authorized")),
        "pool_account": None,
        "social_account": None,
        "created": False,
    }
    if payload["already_authorized"] and pending:
        qr_state = await get_qr_status(auth_id=auth_id)
        me = qr_state.get("me") if isinstance(qr_state.get("me"), dict) else None
        pool_account, social_account, created = await persist_authorized_session(
            session,
            automation_id,
            auth_id=auth_id,
            session_string=pending,
            assign_class=chosen_class,
            me=me,
            preferred_proxy_id=proxy_id,
        )
        payload["pool_account"] = pool_account
        payload["social_account"] = social_account
        payload["created"] = created
    return payload


async def poll_account_qr(
    session: AsyncSession,
    automation_id: int,
    *,
    auth_token: str,
) -> dict[str, Any]:
    token_data = decode_qr_token(auth_token.strip(), automation_id)
    auth_id = str(token_data["auth_id"])
    assign_class = normalize_assign_class(str(token_data.get("assign_class") or ""))
    qr_state = await get_qr_status(auth_id=auth_id)
    status_value = str(qr_state.get("status") or "pending")
    payload: dict[str, Any] = {
        "status": status_value,
        "error": qr_state.get("error"),
        "pool_account": None,
        "social_account": None,
        "created": False,
    }
    if status_value == "success":
        session_string = str(qr_state.get("session_string") or "").strip()
        if not session_string:
            pending_enc = token_data.get("encrypted_pending_session")
            if pending_enc:
                session_string = decrypt_token(pending_enc)
        me = qr_state.get("me") if isinstance(qr_state.get("me"), dict) else {}
        if not session_string:
            payload["status"] = "error"
            payload["error"] = "Telegram не вернул сессию после QR-входа"
            return payload
        pool_account, social_account, created = await persist_authorized_session(
            session,
            automation_id,
            auth_id=auth_id,
            session_string=session_string,
            assign_class=assign_class,
            me=me,
            preferred_proxy_id=_token_proxy_id(token_data),
        )
        payload["pool_account"] = pool_account
        payload["social_account"] = social_account
        payload["created"] = created
    return payload


async def verify_account_qr_2fa(
    session: AsyncSession,
    automation_id: int,
    *,
    auth_token: str,
    password: str,
) -> tuple[PoolAccount, SocialAccount]:
    token_data = decode_qr_token(auth_token.strip(), automation_id)
    auth_id = str(token_data["auth_id"])
    assign_class = normalize_assign_class(str(token_data.get("assign_class") or ""))
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    pending_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_enc) if pending_enc else ""
    qr_state = await get_qr_status(auth_id=auth_id)
    if qr_state.get("session_string"):
        pending_session = str(qr_state["session_string"])
    from .proxy_service import load_telethon_proxy

    proxy_id, proxy = await load_telethon_proxy(
        session,
        _token_proxy_id(token_data),
        automation_id=automation_id,
    )
    result = await complete_qr_2fa(
        api_id=api_id,
        api_hash=api_hash,
        session_string=pending_session,
        password=password,
        proxy=proxy,
    )
    session_string = str(result.get("session_string") or "").strip()
    if not session_string:
        raise TelegramUserbotAuthError("Не удалось получить сессию после 2FA")
    me = {key: result.get(key) for key in ("telegram_id", "username", "first_name", "last_name", "phone_number")}
    pool_account, social_account, _created = await persist_authorized_session(
        session,
        automation_id,
        auth_id=auth_id,
        session_string=session_string,
        assign_class=assign_class,
        me=me,
        preferred_proxy_id=proxy_id,
    )
    return pool_account, social_account


async def request_account_sms(
    session: AsyncSession,
    automation_id: int,
    *,
    phone_number: str,
    assign_class: str | None = None,
) -> dict[str, Any]:
    from .proxy_service import resolve_connect_proxy

    chosen_class = normalize_assign_class(assign_class)
    phone = (phone_number or "").strip()
    if len(phone) < 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Укажите номер телефона")

    try:
        from telethon.errors import FloodWaitError
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        ) from exc

    proxy_id, proxy = await resolve_connect_proxy(session, automation_id)
    client, api_id, api_hash = create_telegram_client(prefer_desktop=True, proxy=proxy)
    phone_code_hash = None
    pending_session_string = ""
    try:
        await client.connect()
        sent = await client.send_code_request(phone=phone)
        phone_code_hash = getattr(sent, "phone_code_hash", None)
        if not phone_code_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telegram не вернул phone_code_hash",
            )
        pending_session_string = client.session.save()
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много попыток. Подождите {exc.seconds} сек",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        detail = f"Не удалось отправить код подтверждения Telegram: {exc}"
        if "api_id/api_hash combination is invalid" in str(exc).lower():
            detail = "Telegram отклонил API-ключи. Попробуйте вход по QR."
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    finally:
        await client.disconnect()

    auth_token = _create_sms_token(
        automation_id=automation_id,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone,
        phone_code_hash=str(phone_code_hash),
        pending_session=pending_session_string,
        assign_class=chosen_class,
        proxy_id=proxy_id,
    )
    return {"auth_token": auth_token}


async def verify_account_sms(
    session: AsyncSession,
    automation_id: int,
    *,
    auth_token: str,
    code: str,
    password: str | None = None,
) -> tuple[PoolAccount, SocialAccount]:
    token_data = decode_sms_token(auth_token.strip(), automation_id)
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    phone_number = str(token_data["phone_number"])
    phone_code_hash = str(token_data["phone_code_hash"])
    assign_class = normalize_assign_class(str(token_data.get("assign_class") or ""))
    pending_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_enc) if pending_enc else ""
    digits = "".join(ch for ch in (code or "") if ch.isdigit())
    if not digits:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Введите код подтверждения (цифры из Telegram)",
        )

    try:
        from telethon.errors import (
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            SessionPasswordNeededError,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        ) from exc

    from .proxy_service import load_telethon_proxy

    proxy_id, proxy = await load_telethon_proxy(
        session,
        _token_proxy_id(token_data),
        automation_id=automation_id,
    )
    client, api_id, api_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=pending_session or "",
        prefer_desktop=True,
        proxy=proxy,
    )
    try:
        await client.connect()
        try:
            await client.sign_in(phone=phone_number, code=digits, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            pwd = (password or "").strip()
            if not pwd:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Для этого аккаунта включен пароль 2FA. Передайте поле password.",
                )
            await client.sign_in(password=pwd)
        except PhoneCodeInvalidError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неверный код подтверждения Telegram",
            ) from None
        except PhoneCodeExpiredError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Код подтверждения Telegram истек. Запросите новый код.",
            ) from None
        me = await client.get_me()
        if not me:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось получить профиль после входа",
            )
        session_string = client.session.save()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось подтвердить код Telegram: {exc}",
        ) from exc
    finally:
        await client.disconnect()

    profile = {
        "telegram_id": getattr(me, "id", None),
        "username": getattr(me, "username", None),
        "first_name": getattr(me, "first_name", None),
        "last_name": getattr(me, "last_name", None),
        "phone_number": getattr(me, "phone", None),
    }
    auth_id = f"sms:{phone_number}:{phone_code_hash}"
    pool_account, social_account, _created = await persist_authorized_session(
        session,
        automation_id,
        auth_id=auth_id,
        session_string=session_string,
        assign_class=assign_class,
        me=profile,
        preferred_proxy_id=proxy_id,
    )
    return pool_account, social_account
