"""Session upload/health/hygiene must not kill a live Telegram login."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.custom.telegram_error_handler import (
    SessionInvalidError,
    _classify_telegram_error,
    _looks_like_session_busy_error,
    _looks_like_session_error,
)
from app.services.telegram_userbot_auth import (
    _TELEGRAM_ANDROID_API_ID,
    _TELEGRAM_DESKTOP_API_ID,
    iter_api_credential_candidates,
)


def test_duplicated_auth_key_is_busy_not_revoked():
    exc = type("AuthKeyDuplicatedError", (Exception,), {})(
        "The authorization key (session file) was used under two different IP addresses simultaneously "
        "(caused by GetStateRequest)"
    )
    assert _looks_like_session_busy_error(exc) is True
    assert _looks_like_session_error(exc) is False
    assert _classify_telegram_error(exc)["kind"] == "session_busy"


def test_auth_restart_is_busy_not_revoked():
    exc = type("AuthRestartError", (Exception,), {})("Restart the authorization key (caused by MsgInvokeRequest)")
    assert _classify_telegram_error(exc)["kind"] == "session_busy"


def test_unregistered_key_is_still_session_death():
    exc = type("AuthKeyUnregisteredError", (Exception,), {})(
        "The key is not registered in the system (caused by GetStateRequest)"
    )
    assert _looks_like_session_error(exc) is True
    assert _classify_telegram_error(exc)["kind"] == "session"


def test_generic_auth_or_admin_errors_are_not_session_death():
    assert _classify_telegram_error(Exception("CHAT_ADMIN_REQUIRED"))["kind"] != "session"
    assert _classify_telegram_error(Exception("The message ID used in the peer was invalid"))["kind"] != "session"
    assert _classify_telegram_error(SessionInvalidError("Session is not authorized"))["kind"] == "session"


def test_api_fallback_includes_official_desktop_and_android():
    pairs = iter_api_credential_candidates(12345, "a" * 32)
    ids = [item[0] for item in pairs]
    assert ids[0] == 12345
    assert _TELEGRAM_DESKTOP_API_ID in ids
    assert _TELEGRAM_ANDROID_API_ID in ids


def _write_pyrogram_session(path: Path, *, api_id: int = 2040, dc_id: int = 2) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE sessions (dc_id INTEGER PRIMARY KEY, api_id INTEGER, "
            "test_mode INTEGER, auth_key BLOB, date INTEGER, user_id INTEGER, is_bot INTEGER)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, 0, ?, 0, 1, 0)",
            (dc_id, api_id, b"\x01" * 256),
        )
        conn.commit()
    finally:
        conn.close()


def test_pyrogram_session_converts_to_telethon(tmp_path: Path):
    from app.services.custom.telegram_account_client import (
        convert_pyrogram_session_file,
        inspect_session_file,
        session_file_has_auth_key,
    )

    src = tmp_path / "pyro.session"
    dest = tmp_path / "tele.session"
    _write_pyrogram_session(src)
    assert inspect_session_file(src)["kind"] == "pyrogram"
    assert session_file_has_auth_key(src) is True
    converted = convert_pyrogram_session_file(src, dest)
    assert converted["kind"] == "telethon"
    assert converted["has_key"] is True
    assert inspect_session_file(src)["kind"] == "pyrogram"


@pytest.mark.asyncio
async def test_hygiene_mints_on_fresh_file_but_does_not_prune(tmp_path: Path, monkeypatch):
    from app.config import settings
    from app.services.custom import session_hygiene_service
    from app.services.telegram_userbot_auth import DEVICE_MODEL_SPARE

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    rel = "sessions/1/fresh.session"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 32)
    account = SimpleNamespace(
        id=9,
        session_file_path=rel,
        encrypted_session="fernet1:x",
        sessions_pruned_at=None,
        encrypted_spare_session=None,
        spare_session_file_path=None,
        spare_authorization_hash=None,
        updated_at=None,
    )
    pruned = {"called": False}
    minted = {"called": False}

    class _Client:
        client = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def fake_mint(client, account, automation_id):
        minted["called"] = True
        account.encrypted_spare_session = "fernet1:spare"
        account.spare_session_file_path = "sessions/1/9_spare.session"
        account.spare_authorization_hash = 111
        return 111

    async def fake_list(*args, **kwargs):
        return [
            SimpleNamespace(hash=0, device_model="RSD Platform"),
            SimpleNamespace(hash=111, device_model=DEVICE_MODEL_SPARE),
            SimpleNamespace(hash=222, device_model="iPhone 15"),
        ]

    async def mark_prune(*args, **kwargs):
        pruned["called"] = True
        return 1

    monkeypatch.setattr(
        session_hygiene_service.TelegramAccountClient,
        "for_account",
        classmethod(lambda cls, account, **kwargs: _Client()),
    )
    monkeypatch.setattr(session_hygiene_service, "_mint_spare_session", fake_mint)
    monkeypatch.setattr(session_hygiene_service, "_list_authorizations", fake_list)
    monkeypatch.setattr(session_hygiene_service, "_reset_extra_sessions", mark_prune)
    session = MagicMock()
    session.flush = AsyncMock()

    result = await session_hygiene_service.hygienize_account(session, account, 1)
    assert minted["called"] is False
    assert result["minted"] is False
    assert result["pruned"] == 0
    assert result["reason"] == "too_fresh"
    assert pruned["called"] is False


@pytest.mark.asyncio
async def test_hygiene_mints_only_after_session_ages(tmp_path: Path, monkeypatch):
    from app.config import settings
    from app.services.custom import session_hygiene_service
    from app.services.telegram_userbot_auth import DEVICE_MODEL_SPARE

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    rel = "sessions/1/aged.session"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 32)
    old = datetime.now(timezone.utc).timestamp() - (7 * 3600)
    os.utime(path, (old, old))
    account = SimpleNamespace(
        id=9,
        session_file_path=rel,
        encrypted_session="fernet1:x",
        sessions_pruned_at=None,
        encrypted_spare_session=None,
        spare_session_file_path=None,
        spare_authorization_hash=None,
        telegram_device=None,
        spare_telegram_device=None,
        updated_at=None,
    )
    minted = {"called": False}
    pruned = {"called": False}

    class _Client:
        client = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def fake_mint(client, account, automation_id):
        minted["called"] = True
        account.encrypted_spare_session = "fernet1:spare"
        account.spare_session_file_path = "sessions/1/9_spare.session"
        account.spare_authorization_hash = 111
        return 111

    async def fake_list(*args, **kwargs):
        return [
            SimpleNamespace(hash=0, device_model="PC 64bit"),
            SimpleNamespace(hash=111, device_model=DEVICE_MODEL_SPARE),
            SimpleNamespace(hash=222, device_model="iPhone 15"),
        ]

    async def mark_prune(*args, **kwargs):
        pruned["called"] = True
        return 1

    monkeypatch.setattr(
        session_hygiene_service.TelegramAccountClient,
        "for_account",
        classmethod(lambda cls, account, **kwargs: _Client()),
    )
    monkeypatch.setattr(session_hygiene_service, "_mint_spare_session", fake_mint)
    monkeypatch.setattr(session_hygiene_service, "_list_authorizations", fake_list)
    monkeypatch.setattr(session_hygiene_service, "_reset_extra_sessions", mark_prune)
    session = MagicMock()
    session.flush = AsyncMock()

    result = await session_hygiene_service.hygienize_account(session, account, 1)
    assert minted["called"] is True
    assert result["minted"] is True
    assert result["pruned"] == 1
    assert pruned["called"] is True


@pytest.mark.asyncio
async def test_hygiene_does_not_prune_when_spare_mint_fails(tmp_path: Path, monkeypatch):
    from app.config import settings
    from app.services.custom import session_hygiene_service

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    rel = "sessions/1/old.session"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 32)
    old = datetime.now(timezone.utc).timestamp() - 4000
    os.utime(path, (old, old))
    account = SimpleNamespace(
        id=9,
        session_file_path=rel,
        encrypted_session="fernet1:x",
        sessions_pruned_at=None,
        encrypted_spare_session=None,
        spare_session_file_path=None,
        spare_authorization_hash=None,
        updated_at=None,
    )
    pruned = {"called": False}

    class _Client:
        client = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def fail_mint(*args, **kwargs):
        raise RuntimeError("qr failed")

    async def mark_prune(*args, **kwargs):
        pruned["called"] = True
        return 2

    monkeypatch.setattr(
        session_hygiene_service.TelegramAccountClient,
        "for_account",
        classmethod(lambda cls, account, **kwargs: _Client()),
    )
    monkeypatch.setattr(session_hygiene_service, "_mint_spare_session", fail_mint)
    monkeypatch.setattr(session_hygiene_service, "_list_authorizations", AsyncMock(return_value=[]))
    monkeypatch.setattr(session_hygiene_service, "_reset_extra_sessions", mark_prune)
    session = MagicMock()
    session.flush = AsyncMock()

    result = await session_hygiene_service.hygienize_account(session, account, 1, force=True)
    assert result["pruned"] == 0
    assert pruned["called"] is False


def test_prune_never_resets_current_spare_or_our_devices():
    from types import SimpleNamespace

    from app.services.custom.session_hygiene_service import extra_authorization_hashes
    from app.services.telegram_userbot_auth import DEVICE_MODEL_MAIN, DEVICE_MODEL_SPARE

    auths = [
        SimpleNamespace(hash=0, device_model=DEVICE_MODEL_MAIN),
        SimpleNamespace(hash=111, device_model=DEVICE_MODEL_SPARE),
        SimpleNamespace(hash=50, device_model=DEVICE_MODEL_MAIN),
        SimpleNamespace(hash=222, device_model="iPhone 15"),
        SimpleNamespace(hash=333, device_model="Telegram Desktop"),
    ]
    assert extra_authorization_hashes(auths, spare_hash=111) == [222, 333]
    assert extra_authorization_hashes(auths, spare_hash=None) == [222, 333]
    # Realistic fingerprints for this account must also be kept.
    assert extra_authorization_hashes(
        auths,
        spare_hash=111,
        known_models={"PC 64bit", "iPhone 15"},
    ) == [333]


def test_prune_after_promote_keeps_old_main_and_new_current():
    from types import SimpleNamespace

    from app.services.custom.session_hygiene_service import extra_authorization_hashes
    from app.services.telegram_userbot_auth import DEVICE_MODEL_MAIN, DEVICE_MODEL_SPARE

    auths = [
        SimpleNamespace(hash=0, device_model=DEVICE_MODEL_SPARE),
        SimpleNamespace(hash=50, device_model=DEVICE_MODEL_MAIN),
        SimpleNamespace(hash=222, device_model="iPhone 15"),
    ]
    assert extra_authorization_hashes(auths, spare_hash=None) == [222]


def test_upload_health_queue_does_not_start_hygiene():
    from app.router_custom.automation_router import _queue_account_health_check

    tasks = MagicMock()
    _queue_account_health_check(tasks, 7)
    assert tasks.add_task.call_count == 1
    queued = tasks.add_task.call_args[0][0]
    name = getattr(queued, "__name__", str(queued)).lower()
    assert "hygiene" not in name
    assert "health" in name or "check" in name
