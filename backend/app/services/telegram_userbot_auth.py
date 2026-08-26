"""Telegram userbot auth: QR + 2FA, phone code, session file (opentele/Telethon)."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import shutil
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

# Same application ids as opentele API.TelegramDesktop / API.TelegramAndroid (public client keys).
_TELEGRAM_DESKTOP_API_ID = 2040
_TELEGRAM_DESKTOP_API_HASH = "b18441a1ff607e10a989891a5462e627"
_TELEGRAM_ANDROID_API_ID = 6
_TELEGRAM_ANDROID_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

QR_WAIT_TIMEOUT_SECONDS = 180
_QR_TTL_SECONDS = 600

_qr_lock = asyncio.Lock()
_qr_states: dict[str, "_QrAuthState"] = {}


@dataclass
class _QrAuthState:
    status: str = "pending"
    session_string: str = ""
    api_id: int = 0
    api_hash: str = ""
    error: str = ""
    me: dict[str, Any] | None = None
    updated_at: float = field(default_factory=time.time)


class TelegramUserbotAuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def opentele_available() -> bool:
    try:
        import opentele  # noqa: F401

        return True
    except BaseException:
        return False


def _official_desktop_api():
    from opentele.api import API

    return API.TelegramDesktop.Generate(unique_id="rsd_userbot")


def _official_android_api():
    from opentele.api import API

    return API.TelegramAndroid.Generate(unique_id="rsd_userbot_phone")


def _builtin_api_credentials(*, prefer_desktop: bool) -> tuple[int, str]:
    if prefer_desktop:
        return _TELEGRAM_DESKTOP_API_ID, _TELEGRAM_DESKTOP_API_HASH
    return _TELEGRAM_ANDROID_API_ID, _TELEGRAM_ANDROID_API_HASH


def resolve_api_credentials(
    api_id: int | None = None,
    api_hash: str | None = None,
    *,
    prefer_desktop: bool = True,
) -> tuple[int, str]:
    """Resolve MTProto app credentials (custom > env > opentele > Telethon builtin)."""
    custom_id = int(api_id) if api_id is not None and int(api_id) > 0 else 0
    custom_hash = str(api_hash or "").strip()
    if custom_id > 0 and custom_hash:
        return custom_id, custom_hash

    env_id = int(getattr(settings, "TELEGRAM_USERBOT_API_ID", 0) or 0)
    env_hash = str(getattr(settings, "TELEGRAM_USERBOT_API_HASH", "") or "").strip()
    if env_id > 0 and env_hash:
        return env_id, env_hash

    if opentele_available():
        try:
            api = _official_desktop_api() if prefer_desktop else _official_android_api()
            return int(api.api_id), str(api.api_hash)
        except Exception as exc:
            logger.warning("opentele API resolve failed, using Telethon builtin: %s", exc)

    creds = _builtin_api_credentials(prefer_desktop=prefer_desktop)
    logger.debug(
        "telegram userbot: using builtin %s API (opentele not installed)",
        "desktop" if prefer_desktop else "android",
    )
    return creds


def _build_api_data(api_id: int, api_hash: str):
    from opentele.api import APIData

    return APIData(
        api_id=int(api_id),
        api_hash=str(api_hash).strip(),
        device_model="RSD Platform",
        system_version="Windows 10",
        app_version="4.16.30 x64",
        lang_code="ru",
        system_lang_code="ru-RU",
    )


def create_telegram_client(
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    session_string: str = "",
    session_path: str | None = None,
    prefer_desktop: bool = True,
):
    """TelegramClient with opentele when installed, otherwise Telethon."""
    resolved_id, resolved_hash = resolve_api_credentials(
        api_id, api_hash, prefer_desktop=prefer_desktop
    )
    if session_path:
        session = session_path
    else:
        from telethon.sessions import StringSession

        session = StringSession((session_string or "").strip())
    if opentele_available():
        from opentele.tl import TelegramClient

        api = _build_api_data(resolved_id, resolved_hash)
        return TelegramClient(session, api=api), resolved_id, resolved_hash
    from telethon import TelegramClient

    return (
        TelegramClient(session, resolved_id, resolved_hash),
        resolved_id,
        resolved_hash,
    )


def qr_url_to_data_url(qr_url: str) -> str:
    import qrcode

    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _profile_from_me(me: Any) -> dict[str, Any]:
    return {
        "telegram_id": getattr(me, "id", None),
        "username": getattr(me, "username", None),
        "first_name": getattr(me, "first_name", None),
        "last_name": getattr(me, "last_name", None),
        "phone_number": getattr(me, "phone", None),
    }


def _success_payload(*, session_string: str, api_id: int, api_hash: str, me: Any) -> dict[str, Any]:
    profile = _profile_from_me(me)
    return {
        "session_string": session_string,
        "api_id": api_id,
        "api_hash": api_hash,
        **profile,
    }


async def _purge_stale_qr_states() -> None:
    now = time.time()
    async with _qr_lock:
        stale = [k for k, v in _qr_states.items() if now - v.updated_at > _QR_TTL_SECONDS]
        for key in stale:
            _qr_states.pop(key, None)


async def _set_qr_state(auth_id: str, **kwargs: Any) -> None:
    async with _qr_lock:
        state = _qr_states.get(auth_id)
        if state is None:
            state = _QrAuthState()
            _qr_states[auth_id] = state
        for key, value in kwargs.items():
            setattr(state, key, value)
        state.updated_at = time.time()


async def _run_qr_wait(
    auth_id: str,
    client: Any,
    qr_login: Any,
    *,
    api_id: int,
    api_hash: str,
) -> None:
    from telethon.errors import SessionPasswordNeededError

    try:
        await qr_login.wait(timeout=QR_WAIT_TIMEOUT_SECONDS)
        if await client.is_user_authorized():
            me = await client.get_me()
            session_string = client.session.save()
            await _set_qr_state(
                auth_id,
                status="success",
                session_string=session_string,
                api_id=api_id,
                api_hash=api_hash,
                me=_profile_from_me(me) if me else None,
                error="",
            )
        else:
            await _set_qr_state(auth_id, status="error", error="Сессия не авторизована после сканирования QR")
    except SessionPasswordNeededError:
        await _set_qr_state(
            auth_id,
            status="need_2fa",
            session_string=client.session.save(),
            api_id=api_id,
            api_hash=api_hash,
            error="",
        )
    except asyncio.TimeoutError:
        await _set_qr_state(auth_id, status="expired", error="Время ожидания сканирования QR истекло")
    except Exception as exc:
        logger.warning("telegram userbot QR wait failed auth_id=%s: %s", auth_id, exc, exc_info=True)
        await _set_qr_state(auth_id, status="error", error=str(exc))
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def start_qr_login(
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
) -> dict[str, Any]:
    await _purge_stale_qr_states()
    auth_id = uuid.uuid4().hex
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        prefer_desktop=True,
    )
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            session_string = client.session.save()
            await _set_qr_state(
                auth_id,
                status="success",
                session_string=session_string,
                api_id=resolved_id,
                api_hash=resolved_hash,
                me=_profile_from_me(me) if me else None,
            )
            await client.disconnect()
            return {
                "auth_id": auth_id,
                "qr_url": "",
                "qr_data_url": "",
                "pending_session_string": session_string,
                "already_authorized": True,
                "api_id": resolved_id,
                "api_hash": resolved_hash,
            }
        qr_login = await client.qr_login()
        qr_url = str(getattr(qr_login, "url", "") or "").strip()
        if not qr_url:
            raise TelegramUserbotAuthError("Telegram не вернул URL для QR-входа")
        pending_session_string = client.session.save()
        await _set_qr_state(
            auth_id,
            status="pending",
            session_string=pending_session_string,
            api_id=resolved_id,
            api_hash=resolved_hash,
        )
        asyncio.create_task(
            _run_qr_wait(
                auth_id,
                client,
                qr_login,
                api_id=resolved_id,
                api_hash=resolved_hash,
            )
        )
        return {
            "auth_id": auth_id,
            "qr_url": qr_url,
            "qr_data_url": qr_url_to_data_url(qr_url),
            "pending_session_string": pending_session_string,
            "already_authorized": False,
            "api_id": resolved_id,
            "api_hash": resolved_hash,
        }
    except TelegramUserbotAuthError:
        await client.disconnect()
        raise
    except Exception as exc:
        await client.disconnect()
        raise TelegramUserbotAuthError(f"Не удалось начать QR-вход: {exc}") from exc


async def get_qr_status(*, auth_id: str) -> dict[str, Any]:
    await _purge_stale_qr_states()
    async with _qr_lock:
        state = _qr_states.get(auth_id)
    if state is None:
        return {"status": "expired", "error": "Сессия QR-входа не найдена или истекла"}
    payload: dict[str, Any] = {
        "status": state.status,
        "error": state.error or None,
        "api_id": state.api_id or None,
        "api_hash": state.api_hash or None,
    }
    if state.status == "success":
        payload.update(
            {
                "session_string": state.session_string,
                "me": state.me,
            }
        )
    elif state.status == "need_2fa" and state.session_string:
        payload["pending_session_string"] = state.session_string
    return payload


async def complete_qr_2fa(
    *,
    api_id: int,
    api_hash: str,
    session_string: str,
    password: str,
) -> dict[str, Any]:
    from telethon.errors import PasswordHashInvalidError

    pwd = (password or "").strip()
    if not pwd:
        raise TelegramUserbotAuthError("Укажите пароль 2FA", status_code=422)

    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
    )
    try:
        await client.connect()
        try:
            await client.sign_in(password=pwd)
        except PasswordHashInvalidError:
            raise TelegramUserbotAuthError("Неверный пароль 2FA", status_code=422) from None
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("Не удалось авторизовать сессию с паролем 2FA")
        me = await client.get_me()
        final_session = client.session.save()
        return _success_payload(
            session_string=final_session,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    finally:
        await client.disconnect()


def _find_tdata_dir(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    markers = ("key_datas", "map", "settings", "usertag")
    if any((root / name).exists() for name in markers):
        return root
    nested = root / "tdata"
    if nested.is_dir() and any((nested / name).exists() for name in markers):
        return nested
    for child in sorted(root.iterdir()):
        if child.is_dir():
            found = _find_tdata_dir(child)
            if found is not None:
                return found
    return None


async def _import_from_tdata_dir(tdata_dir: Path) -> dict[str, Any]:
    if not opentele_available():
        raise TelegramUserbotAuthError(
            "Импорт архива tdata (Telegram Desktop) требует пакет opentele на сервере. "
            "Пересоберите Docker-образ backend или используйте вход по QR / .session / .txt",
            status_code=503,
        )
    from opentele.api import UseCurrentSession
    from opentele.td import TDesktop

    tdesk = TDesktop(str(tdata_dir))
    if not tdesk.isLoaded():
        raise TelegramUserbotAuthError("Не удалось загрузить папку tdata Telegram Desktop")

    api = _official_desktop_api()
    api_id, api_hash = int(api.api_id), str(api.api_hash)
    tmp_session = tempfile.NamedTemporaryFile(prefix="rsd_tg_", suffix=".session", delete=False)
    tmp_session.close()
    session_path = tmp_session.name
    client = None
    try:
        client = await tdesk.ToTelethon(session_path, UseCurrentSession, api)
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("tdata не содержит авторизованной сессии Telegram Desktop")
        me = await client.get_me()
        from telethon.sessions import StringSession

        session_string = StringSession.save(client.session)
        return _success_payload(
            session_string=session_string,
            api_id=api_id,
            api_hash=api_hash,
            me=me,
        )
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        try:
            Path(session_path).unlink(missing_ok=True)
        except Exception:
            pass


async def _import_from_telethon_session_file(
    session_path: Path,
    *,
    api_id: int | None,
    api_hash: str | None,
) -> dict[str, Any]:
    resolved_id, resolved_hash = resolve_api_credentials(api_id, api_hash, prefer_desktop=True)
    if opentele_available():
        from opentele.tl import TelegramClient

        api = _build_api_data(resolved_id, resolved_hash)
        client = TelegramClient(str(session_path), api=api)
    else:
        from telethon import TelegramClient

        client = TelegramClient(str(session_path), resolved_id, resolved_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("Файл .session не авторизован в Telegram")
        me = await client.get_me()
        from telethon.sessions import StringSession

        session_string = StringSession.save(client.session)
        return _success_payload(
            session_string=session_string,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    finally:
        await client.disconnect()


async def _import_from_string_text(
    text: str,
    *,
    api_id: int | None,
    api_hash: str | None,
) -> dict[str, Any]:
    session_string = text.strip()
    if len(session_string) < 10:
        raise TelegramUserbotAuthError("Слишком короткая строка сессии")
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=session_string,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise TelegramUserbotAuthError("StringSession не авторизована")
        me = await client.get_me()
        final = client.session.save()
        return _success_payload(
            session_string=final,
            api_id=resolved_id,
            api_hash=resolved_hash,
            me=me,
        )
    finally:
        await client.disconnect()


async def import_session_file(
    *,
    api_id: int | None,
    api_hash: str | None,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    name = (filename or "").strip().lower()
    if not content:
        raise TelegramUserbotAuthError("Файл сессии пуст")

    tmp_root = Path(tempfile.mkdtemp(prefix="rsd_tg_import_"))
    try:
        if name.endswith(".zip"):
            zip_path = tmp_root / "upload.zip"
            zip_path.write_bytes(content)
            extract_dir = tmp_root / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            tdata_dir = _find_tdata_dir(extract_dir)
            if tdata_dir is None:
                raise TelegramUserbotAuthError(
                    "В архиве не найдена папка tdata Telegram Desktop"
                )
            return await _import_from_tdata_dir(tdata_dir)

        if name.endswith(".session"):
            session_path = tmp_root / "upload.session"
            session_path.write_bytes(content)
            return await _import_from_telethon_session_file(
                session_path, api_id=api_id, api_hash=api_hash
            )

        text = content.decode("utf-8", errors="ignore").strip()
        if text:
            return await _import_from_string_text(text, api_id=api_id, api_hash=api_hash)

        raise TelegramUserbotAuthError(
            "Поддерживаются: .zip (tdata), .session (Telethon), .txt (StringSession)"
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
