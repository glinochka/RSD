"""MAX userbot auth via PyMax: QR, SMS code, session import."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from pymax import Client, ExtraConfig, WebClient
from pymax.auth.base import AuthFlow
from pymax.session.models import SessionInfo

from .max_userbot_session import (
    MaxUserbotSessionError,
    bundle_to_session_payload,
    load_bundle_from_upload,
    normalize_bundle,
    profile_display_name,
    validate_session_bundle,
)
from .telegram_userbot_auth import qr_url_to_data_url

logger = logging.getLogger(__name__)

QR_WAIT_TIMEOUT_SECONDS = 180
_AUTH_TTL_SECONDS = 600

_auth_lock = asyncio.Lock()
_auth_states: dict[str, "_MaxAuthState"] = {}


class MaxUserbotAuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class _MaxAuthState:
    app: Any
    work_dir: str
    device_id: str
    transport: Literal["web", "mobile"]
    phone: str = ""
    sms_token: str = ""
    track_id: str = ""
    qr_link: str = ""
    qr_expires_at: float = 0.0
    password_track_id: str = ""
    password_hint: str | None = None
    ping_task: asyncio.Task[None] | None = None
    updated_at: float = field(default_factory=time.time)


class _SkipAuthFlow(AuthFlow):
    async def authenticate(self, app) -> Any:
        raise RuntimeError("MAX auth flow is managed by API endpoints")


def _build_web_app(work_dir: str, device_id: str):
    extra = ExtraConfig(
        device_id=device_id,
        reconnect=False,
        log_level="WARNING",
        telemetry=False,
    )
    return WebClient(
        work_dir=work_dir,
        session_name="auth.db",
        extra_config=extra,
        auth_flow=_SkipAuthFlow(),
    )


def _build_mobile_app(work_dir: str, device_id: str, phone: str):
    extra = ExtraConfig(
        device_id=device_id,
        reconnect=False,
        log_level="WARNING",
        telemetry=False,
    )
    return Client(
        phone=phone,
        work_dir=work_dir,
        session_name="auth.db",
        extra_config=extra,
        auth_flow=_SkipAuthFlow(),
    )


async def _purge_stale_states() -> None:
    now = time.time()
    async with _auth_lock:
        stale = [key for key, value in _auth_states.items() if now - value.updated_at > _AUTH_TTL_SECONDS]
        for key in stale:
            state = _auth_states.pop(key, None)
            if state is not None:
                await _close_state(state)


async def _close_state(state: _MaxAuthState) -> None:
    if state.ping_task is not None:
        state.ping_task.cancel()
        try:
            await state.ping_task
        except asyncio.CancelledError:
            pass
    try:
        await state.app.close()
    except Exception:
        logger.debug("max_userbot auth close failed", exc_info=True)
    shutil.rmtree(state.work_dir, ignore_errors=True)


async def _open_state(
    *,
    transport: Literal["web", "mobile"],
    phone: str = "",
) -> tuple[str, _MaxAuthState]:
    await _purge_stale_states()
    work_dir = tempfile.mkdtemp(prefix="rsd_max_auth_")
    device_id = str(uuid4())
    if transport == "mobile":
        client = _build_mobile_app(work_dir, device_id, phone)
    else:
        client = _build_web_app(work_dir, device_id)
    app = client._app
    try:
        await app.connection.open()
        await app.handshake(device_id)
        ping_task = asyncio.create_task(app._ping_loop())
    except Exception as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MaxUserbotAuthError(f"Не удалось подключиться к MAX: {exc}") from exc
    auth_id = str(uuid.uuid4())
    state = _MaxAuthState(
        app=app,
        work_dir=work_dir,
        device_id=device_id,
        transport=transport,
        phone=phone,
        ping_task=ping_task,
    )
    async with _auth_lock:
        _auth_states[auth_id] = state
    return auth_id, state


async def _get_state(auth_id: str) -> _MaxAuthState:
    await _purge_stale_states()
    async with _auth_lock:
        state = _auth_states.get(auth_id)
    if state is None:
        raise MaxUserbotAuthError("Сессия авторизации MAX истекла. Начните вход заново.", status_code=401)
    state.updated_at = time.time()
    return state


async def _pop_state(auth_id: str) -> _MaxAuthState | None:
    async with _auth_lock:
        return _auth_states.pop(auth_id, None)


def _success_payload(
    *,
    bundle: dict[str, Any],
    profile: Any,
    phone: str = "",
) -> dict[str, Any]:
    account_id = str(profile.contact.id)
    normalized = normalize_bundle({**bundle, "max_account_id": account_id, "phone": phone or bundle.get("phone", "")})
    return {
        "session_payload": bundle_to_session_payload(normalized),
        "max_account_id": account_id,
        "display_name": profile_display_name(profile),
        "phone_number": normalized.get("phone") or None,
    }


async def _finalize_login(
    state: _MaxAuthState,
    *,
    token: str,
    phone: str = "",
) -> dict[str, Any]:
    session = SessionInfo(
        token=token,
        device_id=state.device_id,
        phone=phone or state.phone,
        mt_instance_id=state.app.config.device.mt_instance_id,
    )
    await state.app.store.save_session(session)
    state.app.session = session
    response = await state.app.api.auth.login(state.app.config.device.user_agent)
    if response.token and response.token != session.token:
        await state.app.store.update_token(session.token, response.token)
        session = session.model_copy(update={"token": response.token})
        state.app.session = session
    profile = response.profile
    if profile is None or profile.contact is None:
        raise MaxUserbotAuthError("MAX не вернул профиль после входа")
    bundle = {
        "token": session.token,
        "device_id": session.device_id,
        "phone": session.phone,
        "mt_instance_id": session.mt_instance_id,
        "sync": session.sync.model_dump(),
        "transport": state.transport,
    }
    return _success_payload(bundle=bundle, profile=profile, phone=session.phone)


async def start_qr_login() -> dict[str, Any]:
    auth_id, state = await _open_state(transport="web")
    try:
        qr_info = await state.app.api.auth.request_qr()
        state.track_id = qr_info.track_id
        state.qr_link = qr_info.qr_link
        state.qr_expires_at = qr_info.expires_at / 1000
        return {
            "auth_id": auth_id,
            "qr_url": qr_info.qr_link,
            "qr_data_url": qr_url_to_data_url(qr_info.qr_link),
            "expires_at": state.qr_expires_at,
        }
    except Exception as exc:
        await _pop_state(auth_id)
        await _close_state(state)
        raise MaxUserbotAuthError(f"Не удалось запросить QR MAX: {exc}") from exc


async def get_qr_status(*, auth_id: str) -> dict[str, Any]:
    state = await _get_state(auth_id)
    if not state.track_id:
        return {"status": "error", "error": "QR не был инициализирован"}

    if time.time() > state.qr_expires_at:
        await _pop_state(auth_id)
        await _close_state(state)
        return {"status": "expired", "error": "QR-код истёк"}

    try:
        response = await state.app.api.auth.check_qr(state.track_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    if not response.status.login_available:
        return {"status": "pending"}

    try:
        result = await state.app.api.auth.confirm_qr(state.track_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    if result.login_token:
        payload = await _finalize_login(state, token=result.login_token)
        await _pop_state(auth_id)
        await _close_state(state)
        return {"status": "success", **payload}

    if result.password_challenge:
        state.password_track_id = result.password_challenge.track_id
        state.password_hint = result.password_challenge.hint
        return {
            "status": "need_2fa",
            "password_hint": state.password_hint,
        }

    return {"status": "error", "error": "MAX не вернул token после QR-подтверждения"}


async def complete_qr_2fa(*, auth_id: str, password: str) -> dict[str, Any]:
    state = await _get_state(auth_id)
    if not state.password_track_id:
        raise MaxUserbotAuthError("2FA для MAX не требуется или QR ещё не подтверждён")
    pwd = (password or "").strip()
    if not pwd:
        raise MaxUserbotAuthError("Пароль 2FA обязателен")

    try:
        response = await state.app.api.auth.check_password(state.password_track_id, pwd)
    except Exception as exc:
        raise MaxUserbotAuthError(f"Не удалось проверить пароль 2FA MAX: {exc}") from exc

    if response.error:
        raise MaxUserbotAuthError(f"Неверный пароль 2FA MAX: {response.error}")
    if not response.login_token:
        raise MaxUserbotAuthError("MAX не вернул token после 2FA")

    payload = await _finalize_login(state, token=response.login_token)
    await _pop_state(auth_id)
    await _close_state(state)
    return payload


async def request_sms_code(*, phone_number: str) -> dict[str, Any]:
    phone = (phone_number or "").strip()
    if len([ch for ch in phone if ch.isdigit()]) < 10:
        raise MaxUserbotAuthError("Некорректный номер телефона MAX")

    auth_id, state = await _open_state(transport="mobile", phone=phone)
    try:
        start = await state.app.api.auth.request_code(phone)
        state.sms_token = start.token
        state.phone = phone
        return {
            "auth_id": auth_id,
            "phone_number": phone,
            "code_length": start.code_length,
        }
    except Exception as exc:
        await _pop_state(auth_id)
        await _close_state(state)
        raise MaxUserbotAuthError(f"Не удалось отправить SMS-код MAX: {exc}") from exc


async def verify_sms_code(
    *,
    auth_id: str,
    code: str,
    password: str | None = None,
) -> dict[str, Any]:
    state = await _get_state(auth_id)
    if not state.sms_token:
        raise MaxUserbotAuthError("Сначала запросите SMS-код")

    verify_code = (code or "").strip()
    if not verify_code:
        raise MaxUserbotAuthError("Код подтверждения обязателен")

    try:
        result = await state.app.api.auth.send_code(state.sms_token, verify_code)
    except Exception as exc:
        raise MaxUserbotAuthError(f"Не удалось проверить код MAX: {exc}") from exc

    if result.login_token:
        payload = await _finalize_login(state, token=result.login_token, phone=state.phone)
        await _pop_state(auth_id)
        await _close_state(state)
        return payload

    if result.password_challenge:
        if not password:
            return {
                "status": "need_2fa",
                "password_hint": result.password_challenge.hint,
                "auth_id": auth_id,
            }
        try:
            pwd_response = await state.app.api.auth.check_password(
                result.password_challenge.track_id,
                password.strip(),
            )
        except Exception as exc:
            raise MaxUserbotAuthError(f"Не удалось проверить пароль 2FA MAX: {exc}") from exc
        if pwd_response.error:
            raise MaxUserbotAuthError(f"Неверный пароль 2FA MAX: {pwd_response.error}")
        if not pwd_response.login_token:
            raise MaxUserbotAuthError("MAX не вернул token после 2FA")
        payload = await _finalize_login(state, token=pwd_response.login_token, phone=state.phone)
        await _pop_state(auth_id)
        await _close_state(state)
        return payload

    if result.register_token:
        raise MaxUserbotAuthError(
            "Аккаунт MAX не зарегистрирован. Сначала завершите регистрацию в приложении MAX."
        )

    raise MaxUserbotAuthError("MAX не вернул token после проверки кода")


async def import_session_file(*, filename: str, content: bytes) -> dict[str, Any]:
    bundle = await load_bundle_from_upload(filename, content)
    validated = await validate_session_bundle(bundle)
    return {
        "session_payload": validated["session_payload"],
        "max_account_id": validated["account_id"],
        "display_name": validated.get("display_name"),
        "phone_number": validated.get("phone_number"),
    }


async def import_session_json(*, session_payload: str) -> dict[str, Any]:
    raw = (session_payload or "").strip()
    if not raw:
        raise MaxUserbotAuthError("session_payload пустой")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MaxUserbotAuthError("session_payload должен быть JSON") from exc
    if not isinstance(data, dict):
        raise MaxUserbotAuthError("session_payload должен быть JSON-объектом")
    bundle = normalize_bundle(data)
    validated = await validate_session_bundle(bundle)
    return {
        "session_payload": validated["session_payload"],
        "max_account_id": validated["account_id"],
        "display_name": validated.get("display_name"),
        "phone_number": validated.get("phone_number"),
    }
