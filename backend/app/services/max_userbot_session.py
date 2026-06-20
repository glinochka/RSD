"""PyMax session helpers for MAX userbot channel."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from ..utils.crypto import decrypt_token

logger = logging.getLogger(__name__)

_PHONE_DIGITS_RE = re.compile(r"\D+")

Transport = Literal["web", "mobile"]


class MaxUserbotSessionError(Exception):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def bundle_from_credentials(encrypted_credentials: str) -> dict[str, Any]:
    try:
        raw = json.loads(decrypt_token(encrypted_credentials))
    except Exception as exc:
        raise MaxUserbotSessionError(f"Не удалось расшифровать credentials MAX: {exc}") from exc
    if not isinstance(raw, dict):
        raise MaxUserbotSessionError("Некорректный формат credentials MAX")
    if isinstance(raw.get("session_payload"), str):
        try:
            inner = json.loads(raw["session_payload"])
            if isinstance(inner, dict):
                return normalize_bundle(inner)
        except Exception as exc:
            raise MaxUserbotSessionError(f"Некорректный session_payload: {exc}") from exc
    if isinstance(raw.get("session_payload"), dict):
        return normalize_bundle(raw["session_payload"])
    return normalize_bundle(raw)


def normalize_bundle(data: dict[str, Any]) -> dict[str, Any]:
    token = str(data.get("token") or data.get("max_token") or "").strip()
    device_id = str(data.get("device_id") or data.get("deviceId") or "").strip()
    if not token:
        raise MaxUserbotSessionError("В сессии MAX отсутствует token")
    if not device_id:
        raise MaxUserbotSessionError("В сессии MAX отсутствует device_id")
    transport = str(data.get("transport") or "web").strip().lower()
    if transport not in {"web", "mobile"}:
        transport = "web"
    sync_raw = data.get("sync") if isinstance(data.get("sync"), dict) else {}
    return {
        "token": token,
        "device_id": device_id,
        "phone": str(data.get("phone") or "").strip(),
        "mt_instance_id": str(data.get("mt_instance_id") or "").strip(),
        "transport": transport,
        "max_account_id": str(data.get("max_account_id") or "").strip(),
        "sync": {
            "chats_sync": int(sync_raw.get("chats_sync", 0) or 0),
            "contacts_sync": int(sync_raw.get("contacts_sync", 0) or 0),
            "drafts_sync": int(sync_raw.get("drafts_sync", 0) or 0),
            "presence_sync": int(sync_raw.get("presence_sync", 0) or 0),
            "config_hash": str(sync_raw.get("config_hash") or ""),
        },
    }


def bundle_to_session_payload(bundle: dict[str, Any]) -> str:
    return json.dumps(normalize_bundle(bundle), ensure_ascii=False)


def profile_display_name(profile: Any) -> str:
    contact = getattr(profile, "contact", None)
    if contact is None:
        return ""
    names = getattr(contact, "names", None) or []
    if names:
        first = str(getattr(names[0], "first_name", "") or "").strip()
        last = str(getattr(names[0], "last_name", "") or "").strip()
        display = f"{first} {last}".strip()
        if display:
            return display
    return str(getattr(contact, "id", "") or "").strip()


async def write_session_store(work_dir: str, bundle: dict[str, Any]) -> None:
    from pymax.session import SessionStore
    from pymax.session.models import SessionInfo
    from pymax.types.domain.sync import SyncState, DEFAULT_CONFIG_HASH

    normalized = normalize_bundle(bundle)
    sync_raw = normalized.get("sync") or {}
    config_hash = str(sync_raw.get("config_hash") or "").strip() or DEFAULT_CONFIG_HASH
    session = SessionInfo(
        token=normalized["token"],
        device_id=normalized["device_id"],
        phone=normalized.get("phone") or "",
        mt_instance_id=normalized.get("mt_instance_id") or str(uuid4()),
        sync=SyncState(
            chats_sync=int(sync_raw.get("chats_sync", 0) or 0),
            contacts_sync=int(sync_raw.get("contacts_sync", 0) or 0),
            drafts_sync=int(sync_raw.get("drafts_sync", 0) or 0),
            presence_sync=int(sync_raw.get("presence_sync", 0) or 0),
            config_hash=config_hash,
        ),
    )
    store = SessionStore(work_dir, "session.db")
    try:
        await store.save_session(session)
    finally:
        await store.close()


def parse_session_payload(session_payload: str) -> dict[str, Any]:
    """Parse session JSON without opening a live MAX connection."""
    raw = (session_payload or "").strip()
    if not raw:
        raise MaxUserbotSessionError("session_payload пустой")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MaxUserbotSessionError("session_payload должен быть JSON") from exc
    if not isinstance(data, dict):
        raise MaxUserbotSessionError("session_payload должен быть JSON-объектом")
    bundle = normalize_bundle(data)
    account_id = str(bundle.get("max_account_id") or "").strip()
    return {
        "account_id": account_id,
        "max_account_id": account_id,
        "session_payload": bundle_to_session_payload(bundle),
        "bundle": bundle,
    }


def build_runtime_client(work_dir: str, bundle: dict[str, Any], *, reconnect: bool = True):
    from pymax import Client, ExtraConfig, WebClient
    from pymax.auth.base import AuthFlow

    class _SkipAuth(AuthFlow):
        async def authenticate(self, app) -> Any:
            raise RuntimeError("MAX userbot session auth is skipped")

    normalized = normalize_bundle(bundle)
    extra = ExtraConfig(
        device_id=normalized["device_id"],
        mt_instance_id=normalized.get("mt_instance_id") or str(uuid4()),
        reconnect=reconnect,
        reconnect_delay=5.0,
        log_level="WARNING",
        telemetry=False,
    )
    if normalized.get("transport") == "mobile":
        phone = normalized.get("phone") or "+70000000000"
        return Client(
            phone=phone,
            work_dir=work_dir,
            session_name="session.db",
            extra_config=extra,
            auth_flow=_SkipAuth(),
        )
    return WebClient(
        work_dir=work_dir,
        session_name="session.db",
        extra_config=extra,
        auth_flow=_SkipAuth(),
    )


async def validate_session_bundle(bundle: dict[str, Any], *, timeout_seconds: float = 45.0) -> dict[str, Any]:
    account_id = str(bundle.get("max_account_id") or "").strip()
    if account_id:
        normalized = normalize_bundle({**bundle, "max_account_id": account_id})
        return {
            "account_id": account_id,
            "max_account_id": account_id,
            "session_payload": bundle_to_session_payload(normalized),
            "display_name": account_id,
            "phone_number": normalized.get("phone") or None,
        }

    work_dir = tempfile.mkdtemp(prefix="rsd_max_validate_")
    try:
        await write_session_store(work_dir, bundle)
        client = build_runtime_client(work_dir, bundle, reconnect=False)
        ready = asyncio.Event()
        profile_holder: dict[str, Any] = {}
        error_holder: dict[str, Exception] = {}

        @client.on_start()
        async def on_start(active_client) -> None:
            try:
                me = active_client.me
                if me is None or me.contact is None:
                    raise MaxUserbotSessionError("MAX не вернул профиль аккаунта")
                resolved_id = str(me.contact.id)
                normalized = normalize_bundle({**bundle, "max_account_id": resolved_id})
                profile_holder["account_id"] = resolved_id
                profile_holder["max_account_id"] = resolved_id
                profile_holder["display_name"] = profile_display_name(me)
                profile_holder["phone_number"] = str(normalized.get("phone") or "")
                profile_holder["session_payload"] = bundle_to_session_payload(normalized)
            except Exception as exc:
                error_holder["error"] = exc
            finally:
                ready.set()

        task = asyncio.create_task(client.start())
        try:
            await asyncio.wait_for(ready.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise MaxUserbotSessionError("Таймаут проверки сессии MAX") from exc
        finally:
            with contextlib.suppress(Exception):
                await client.close()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if error_holder.get("error"):
            exc = error_holder["error"]
            if isinstance(exc, MaxUserbotSessionError):
                raise exc
            raise MaxUserbotSessionError(f"Не удалось проверить сессию MAX: {exc}") from exc
        if not profile_holder.get("account_id"):
            raise MaxUserbotSessionError("MAX не вернул id аккаунта для сессии")
        return profile_holder
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def normalize_max_phone_e164(value: str | None) -> str | None:
    """Нормализует российский/международный номер в формат +7XXXXXXXXXX."""
    digits = _PHONE_DIGITS_RE.sub("", value or "")
    if len(digits) < 10:
        return None
    if len(digits) >= 12 and digits.startswith("17"):
        digits = digits[1:]
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) < 11:
        return None
    return f"+{digits}"


def is_max_phone_target(value: str) -> bool:
    """Цель outreach по телефону (Excel) — с «+»; иначе считаем chat_id диалога."""
    return str(value or "").strip().startswith("+")


async def _run_max_client_once(
    bundle: dict[str, Any],
    *,
    timeout_seconds: float = 45.0,
    on_ready,
) -> Any:
    work_dir = tempfile.mkdtemp(prefix="rsd_max_send_")
    try:
        await write_session_store(work_dir, bundle)
        client = build_runtime_client(work_dir, bundle, reconnect=False)
        done = asyncio.Event()
        error_holder: dict[str, Exception] = {}
        result_holder: dict[str, Any] = {}

        @client.on_start()
        async def on_start(active_client) -> None:
            try:
                result_holder["value"] = await on_ready(active_client)
            except Exception as exc:
                error_holder["error"] = exc
            finally:
                done.set()

        task = asyncio.create_task(client.start())
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise MaxUserbotSessionError("Таймаут операции MAX userbot") from exc
        finally:
            with contextlib.suppress(Exception):
                await client.close()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if error_holder.get("error"):
            exc = error_holder["error"]
            if isinstance(exc, MaxUserbotSessionError):
                raise exc
            raise MaxUserbotSessionError(str(exc)) from exc
        return result_holder.get("value")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def resolve_max_dialog_chat_id_for_phone(bundle: dict[str, Any], phone_e164: str) -> str:
    """Найти пользователя MAX по телефону и вычислить id личного диалога."""
    normalized_phone = normalize_max_phone_e164(phone_e164)
    if not normalized_phone:
        raise MaxUserbotSessionError("Некорректный номер телефона для MAX")

    async def _resolve(active_client) -> str:
        me = active_client.me
        if me is None or me.contact is None:
            raise MaxUserbotSessionError("MAX не вернул профиль аккаунта")
        my_id = int(me.contact.id)
        try:
            user = await active_client.search_by_phone(normalized_phone)
        except Exception as exc:
            low = str(exc).casefold()
            if "not found" in low or "не найден" in low:
                raise MaxUserbotSessionError(
                    f"Пользователь MAX не найден по номеру {normalized_phone}"
                ) from exc
            raise MaxUserbotSessionError(
                f"Не удалось найти пользователя MAX по номеру: {exc}"
            ) from exc
        user_id = int(user.id)
        chat_id = int(active_client.get_chat_id(my_id, user_id))
        return str(chat_id)

    return str(await _run_max_client_once(bundle, on_ready=_resolve))


async def send_message_once(bundle: dict[str, Any], chat_id: str, text: str) -> str:
    """Отправить сообщение в известный chat_id. Возвращает chat_id."""
    normalized_text = (text or "").strip()
    if not normalized_text:
        raise MaxUserbotSessionError("Сообщение пустое")
    try:
        chat_id_int = int(str(chat_id).strip())
    except ValueError as exc:
        raise MaxUserbotSessionError("Некорректный chat_id MAX") from exc

    async def _send(active_client) -> str:
        await active_client.api.messages.send_message(chat_id_int, normalized_text)
        return str(chat_id_int)

    return str(await _run_max_client_once(bundle, on_ready=_send))


async def send_outreach_message_once(
    bundle: dict[str, Any],
    *,
    target_external_id: str,
    text: str,
) -> str:
    """
    Отправить outreach: по телефону (+7…) или в готовый chat_id.
    Возвращает chat_id диалога (для аналитики и FSM).
    """
    target = str(target_external_id or "").strip()
    normalized_text = (text or "").strip()
    if not target:
        raise MaxUserbotSessionError("Пустой идентификатор получателя MAX")
    if not normalized_text:
        raise MaxUserbotSessionError("Сообщение пустое")

    if is_max_phone_target(target):
        normalized_phone = normalize_max_phone_e164(target)
        if not normalized_phone:
            raise MaxUserbotSessionError("Некорректный номер телефона для MAX")

        async def _send_by_phone(active_client) -> str:
            me = active_client.me
            if me is None or me.contact is None:
                raise MaxUserbotSessionError("MAX не вернул профиль аккаунта")
            my_id = int(me.contact.id)
            try:
                user = await active_client.search_by_phone(normalized_phone)
            except Exception as exc:
                low = str(exc).casefold()
                if "not found" in low or "не найден" in low:
                    raise MaxUserbotSessionError(
                        f"Пользователь MAX не найден по номеру {normalized_phone}"
                    ) from exc
                raise MaxUserbotSessionError(
                    f"Не удалось найти пользователя MAX по номеру: {exc}"
                ) from exc
            chat_id = int(active_client.get_chat_id(my_id, int(user.id)))
            await active_client.api.messages.send_message(chat_id, normalized_text)
            return str(chat_id)

        return str(await _run_max_client_once(bundle, on_ready=_send_by_phone))

    return await send_message_once(bundle, target, normalized_text)


async def load_bundle_from_upload(filename: str, content: bytes) -> dict[str, Any]:
    name = (filename or "upload").lower()
    if name.endswith(".db"):
        return await _load_bundle_from_db(content)
    text = content.decode("utf-8", errors="ignore").strip()
    if not text:
        raise MaxUserbotSessionError("Файл сессии пустой")
    if name.endswith(".json") or text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MaxUserbotSessionError("Файл сессии не является валидным JSON") from exc
        if not isinstance(data, dict):
            raise MaxUserbotSessionError("JSON сессии должен быть объектом")
        return normalize_bundle(data)
    # Legacy: token only in plain text
    if len(text) < 20:
        raise MaxUserbotSessionError("Слишком короткий token в файле сессии")
    raise MaxUserbotSessionError(
        "Для импорта token укажите JSON с полями token и device_id, либо загрузите session.db PyMax"
    )


async def _load_bundle_from_db(content: bytes) -> dict[str, Any]:
    work_dir = tempfile.mkdtemp(prefix="rsd_max_import_db_")
    try:
        db_path = Path(work_dir) / "session.db"
        db_path.write_bytes(content)
        from pymax.session import SessionStore

        store = SessionStore(work_dir, "session.db")
        try:
            session = await store.load_session()
        finally:
            await store.close()
        if session is None:
            raise MaxUserbotSessionError("В файле session.db не найдена сессия PyMax")
        return normalize_bundle(
            {
                "token": session.token,
                "device_id": session.device_id,
                "phone": session.phone,
                "mt_instance_id": session.mt_instance_id,
                "sync": session.sync.model_dump(),
                "transport": "web",
            }
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
