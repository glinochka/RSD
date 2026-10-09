"""Session upload/health/hygiene must not kill a live Telegram login."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.custom.telegram_error_handler import (
    ProxyDeadError,
    SessionInvalidError,
    _classify_telegram_error,
    _looks_like_session_busy_error,
    _looks_like_session_error,
    looks_like_proxy_dead,
)
from app.services.telegram_userbot_auth import (
    _TELEGRAM_ANDROID_API_ID,
    _TELEGRAM_DESKTOP_API_ID,
    _TELEGRAM_IOS_API_ID,
    iter_api_credential_candidates,
)


def test_dead_proxy_is_not_session_death():
    exc = type("ProxyConnectionError", (Exception,), {})(
        "Could not connect to proxy 88.218.186.149:63065 [Connect call failed]"
    )
    assert looks_like_proxy_dead(exc) is True
    assert _classify_telegram_error(exc)["kind"] == "proxy"
    assert _looks_like_session_error(exc) is False
    assert looks_like_proxy_dead(ProxyDeadError("Прокси недоступен")) is True
    assert looks_like_proxy_dead(Exception("Connection to Telegram failed 5 time(s)")) is False
    assert looks_like_proxy_dead(
        Exception("Connection to Telegram failed 5 time(s) [proxy 88.218.186.149:63065]")
    ) is True


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
    assert _TELEGRAM_IOS_API_ID in ids


def test_api_fallback_prefers_ios_family():
    pairs = iter_api_credential_candidates(family="ios")
    ids = [item[0] for item in pairs]
    assert ids[0] == _TELEGRAM_IOS_API_ID
    assert _TELEGRAM_ANDROID_API_ID not in ids
    assert _TELEGRAM_DESKTOP_API_ID not in ids


def test_api_fallback_known_family_stays_on_that_client():
    pairs = iter_api_credential_candidates(family="android")
    ids = [item[0] for item in pairs]
    assert ids == [_TELEGRAM_ANDROID_API_ID]


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
    assert result["reason"] == "hygiene_disabled"
    assert pruned["called"] is False


@pytest.mark.asyncio
async def test_hygiene_does_not_mint_even_when_session_ages(tmp_path: Path, monkeypatch):
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
    assert minted["called"] is False
    assert result["minted"] is False
    assert result["pruned"] == 0
    assert result["reason"] == "hygiene_disabled"
    assert pruned["called"] is False


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
    assert result["reason"] == "hygiene_disabled"


@pytest.mark.asyncio
async def test_hygiene_does_not_reset_other_sessions_even_with_spare(tmp_path: Path, monkeypatch):
    from app.config import settings
    from app.services.custom import session_hygiene_service

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    rel = "sessions/1/main.session"
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 32)
    account = SimpleNamespace(
        id=9,
        session_file_path=rel,
        encrypted_session="fernet1:x",
        sessions_pruned_at=None,
        encrypted_spare_session="fernet1:spare",
        spare_session_file_path="sessions/1/9_spare.session",
        spare_authorization_hash=111,
        updated_at=None,
    )
    pruned = {"called": False}
    listed = {"called": False}

    class _Client:
        client = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def mark_list(*args, **kwargs):
        listed["called"] = True
        return []

    async def mark_prune(*args, **kwargs):
        pruned["called"] = True
        return 2

    monkeypatch.setattr(
        session_hygiene_service.TelegramAccountClient,
        "for_account",
        classmethod(lambda cls, account, **kwargs: _Client()),
    )
    monkeypatch.setattr(session_hygiene_service, "_list_authorizations", mark_list)
    monkeypatch.setattr(session_hygiene_service, "_reset_extra_sessions", mark_prune)
    session = MagicMock()
    session.flush = AsyncMock()

    result = await session_hygiene_service.hygienize_account(session, account, 1, force=True)
    assert result["reason"] == "hygiene_disabled"
    assert result["pruned"] == 0
    assert listed["called"] is False
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


def test_channel_posts_ignore_old_history():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from app.services.custom.neurocommenting_service import (
        collect_new_channel_posts,
        is_fresh_channel_post,
    )

    now = datetime(2026, 9, 21, 18, 0, 0)
    fresh = SimpleNamespace(id=20, text="new", date=now.replace(tzinfo=timezone.utc) - timedelta(minutes=5))
    stale = SimpleNamespace(id=19, text="stale", date=now.replace(tzinfo=timezone.utc) - timedelta(minutes=25))
    old = SimpleNamespace(id=10, text="old", date=now.replace(tzinfo=timezone.utc) - timedelta(days=5))
    missing = SimpleNamespace(date=None)
    assert is_fresh_channel_post(fresh, now=now) is True
    assert is_fresh_channel_post(stale, now=now) is False
    assert is_fresh_channel_post(old, now=now) is False
    assert is_fresh_channel_post(missing, now=now) is False
    assert is_fresh_channel_post(old, now=now, lab_mode=True) is True

    chat = SimpleNamespace(last_message_id=None)
    posts, latest, reason = collect_new_channel_posts([old, stale, fresh], chat, now=now)
    assert posts == []
    assert latest == 20
    assert reason == "armed_cursor"

    chat.last_message_id = "18"
    posts, latest, reason = collect_new_channel_posts([old, stale, fresh], chat, now=now)
    assert [item.id for item in posts] == [20]
    assert latest == 20
    assert reason is None

    chat.last_message_id = "20"
    newer = SimpleNamespace(id=21, text="just now", date=now.replace(tzinfo=timezone.utc) - timedelta(minutes=2))
    posts, latest, reason = collect_new_channel_posts([old, fresh, newer], chat, now=now)
    assert [item.id for item in posts] == [21]
    assert latest == 21
    assert reason is None


def test_accounts_sleep_at_night_and_rest_longer_first_week(monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    monkeypatch.setattr("app.services.custom.account_pacing.SETTLE_HOURS", 24)

    from app.services.custom.account_pacing import (
        CAUTIOUS_TARGET_REST_MAX_SECONDS,
        CAUTIOUS_TARGET_REST_MIN_SECONDS,
        PHASE_OBSERVE,
        PHASE_REPLY,
        PHASE_SETTLE,
        TARGET_REST_MAX_SECONDS,
        TARGET_REST_MIN_SECONDS,
        activity_interval_scale,
        activity_ramp_factor,
        account_humanization_stage,
        account_in_first_week,
        account_in_settle_rest,
        account_may_do_work,
        account_may_first_write_dm,
        account_may_humanize,
        account_may_keep_alive,
        account_may_reply_dm,
        account_should_idle,
        account_upload_phase,
        humanization_ramp_factor,
        account_humanization_should_idle,
        humanization_rest_seconds,
        humanization_session_action_budget,
        humanization_session_seconds,
        in_account_active_hours,
        join_daily_cap,
        rest_seconds_for_account,
    )

    moscow = ZoneInfo("Europe/Moscow")
    day = datetime(2026, 9, 21, 12, 0, tzinfo=moscow)
    night = datetime(2026, 9, 21, 21, 30, tzinfo=moscow)
    assert in_account_active_hours(day) is True
    assert in_account_active_hours(night) is False

    now = datetime(2026, 9, 21, 12, 0, 0)
    settling = SimpleNamespace(id=1, created_at=now - timedelta(hours=12), flood_quarantined_until=None, next_action_at=None, next_humanization_at=None)
    day_one = SimpleNamespace(id=2, created_at=now - timedelta(hours=30), flood_quarantined_until=None, next_action_at=None, next_humanization_at=None)
    day_two = SimpleNamespace(id=3, created_at=now - timedelta(hours=50), flood_quarantined_until=None, next_action_at=None, next_humanization_at=None)
    fresh = SimpleNamespace(id=4, created_at=now - timedelta(days=4))
    aged = SimpleNamespace(id=5, created_at=now - timedelta(days=10))
    veteran = SimpleNamespace(id=6, created_at=now - timedelta(days=40))
    assert account_upload_phase(settling, now=now) == PHASE_SETTLE
    assert account_upload_phase(day_one, now=now) == PHASE_OBSERVE
    assert account_upload_phase(day_two, now=now) == PHASE_REPLY
    assert account_in_settle_rest(settling, now=now) is True
    assert account_in_settle_rest(day_one, now=now) is False
    assert activity_ramp_factor(settling, now=now) == 0.0
    assert activity_ramp_factor(day_one, now=now) == 0.0
    assert activity_ramp_factor(day_two, now=now) == 0.0
    assert account_may_do_work(day_two, now=now) is False
    assert account_may_first_write_dm(day_two, now=now) is False
    assert account_may_reply_dm(day_two, now=now) is True
    assert account_may_keep_alive(day_one, now=now) is False
    assert account_may_keep_alive(fresh, now=now) is True
    assert abs(humanization_ramp_factor(day_one, now=now) - 0.10) < 0.001
    assert abs(humanization_ramp_factor(day_two, now=now) - 0.20) < 0.001
    assert 0.24 <= activity_ramp_factor(fresh, now=now) <= 0.50
    assert humanization_ramp_factor(fresh, now=now) == 1.0
    assert activity_ramp_factor(veteran, now=now) == 1.0
    assert account_should_idle(settling, now=now, ignore_hours=True) is True
    assert account_should_idle(day_one, now=now, ignore_hours=True) is True
    assert account_humanization_should_idle(settling, now=now, ignore_hours=True) is True
    assert account_humanization_should_idle(day_one, now=now, ignore_hours=True) is False
    assert join_daily_cap(day_one, now=now) in {2, 3}
    assert account_in_first_week(fresh, now=now) is True
    assert account_in_first_week(aged, now=now) is False
    assert account_humanization_stage(fresh, now=now) == "cautious"
    assert account_humanization_stage(aged, now=now) == "normal"
    assert account_humanization_stage(veteran, now=now) == "trusted"
    first_week = rest_seconds_for_account(fresh, now=now)
    later = rest_seconds_for_account(aged, now=now)
    scale = activity_interval_scale(fresh, now=now)
    assert CAUTIOUS_TARGET_REST_MIN_SECONDS * scale <= first_week <= CAUTIOUS_TARGET_REST_MAX_SECONDS * scale
    assert TARGET_REST_MIN_SECONDS <= later <= TARGET_REST_MAX_SECONDS
    assert humanization_ramp_factor(veteran, now=now) == 1.0
    assert 40 <= humanization_session_seconds(day_one, now=now) <= 90
    assert 60 <= humanization_session_seconds(day_two, now=now) <= 140
    assert 240 <= humanization_session_seconds(veteran, now=now) <= 420
    assert 2 <= humanization_session_action_budget(day_one, now=now) <= 3
    assert 7 <= humanization_session_action_budget(veteran, now=now) <= 10
    assert humanization_session_action_budget(settling, now=now) == 0
    for _ in range(8):
        rest = humanization_rest_seconds(veteran, now=now)
        assert 15 * 60 <= rest <= 30 * 60
    stolen = SimpleNamespace(
        id=9,
        origin="intercept",
        created_at=now,
        flood_quarantined_until=None,
        next_action_at=None,
        next_humanization_at=None,
    )
    assert account_in_settle_rest(stolen, now=now) is False
    assert account_may_keep_alive(stolen, now=now) is True
    assert account_may_do_work(stolen, now=now) is False
    assert account_may_humanize(stolen, now=now) is False


def test_peer_opener_is_always_the_veteran(monkeypatch):
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    import app.services.custom.account_pacing as pacing
    from app.services.custom.account_peer_dialog_service import _peer_opener

    monkeypatch.setattr(pacing, "SETTLE_HOURS", 24)
    now = datetime.utcnow().replace(tzinfo=None)
    young = SimpleNamespace(id=1, created_at=now - timedelta(hours=50), username="new_acc")
    veteran = SimpleNamespace(id=2, created_at=now - timedelta(days=20), username="old_acc")
    ordered = _peer_opener(young, veteran)
    assert ordered is not None
    assert ordered[0] is veteran
    assert ordered[1] is young
    assert pacing.account_may_first_write_dm(young, now=now) is False
    assert pacing.account_may_first_write_dm(veteran, now=now) is True
    assert _peer_opener(young, SimpleNamespace(id=3, created_at=now - timedelta(hours=52), username="also_new")) is None


def test_peer_dialog_does_not_park_public_writes():
    from app.services.custom.account_pacing import action_uses_humanization_rest, action_uses_target_rest

    assert action_uses_humanization_rest("humanization_session") is True
    assert action_uses_target_rest("peer_dialog") is False
    assert action_uses_humanization_rest("peer_dialog") is True
    assert action_uses_target_rest("inbound_dm") is False
    assert action_uses_humanization_rest("inbound_dm") is True
    assert action_uses_target_rest("account_warmup") is False
    assert action_uses_target_rest("neurocommenting") is True
    assert action_uses_target_rest("shilling_chat") is True


def test_active_hours_are_jittered_per_account():
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from app.services.custom.account_pacing import (
        account_active_window,
        farm_overlap_active_hours,
        in_account_active_hours,
        profile_edit_allowed,
    )

    moscow = ZoneInfo("Europe/Moscow")
    early = datetime(2026, 9, 21, 7, 20, tzinfo=moscow)
    noon = datetime(2026, 9, 21, 12, 0, tzinfo=moscow)
    night = datetime(2026, 9, 21, 22, 0, tzinfo=moscow)
    left = SimpleNamespace(id=1)
    right = SimpleNamespace(id=99)
    assert account_active_window(left) != account_active_window(right)
    assert in_account_active_hours(noon, left) is True
    assert in_account_active_hours(night, left) is False
    start, _end = account_active_window(left)
    before_personal = datetime(2026, 9, 21, int(start), 0, tzinfo=moscow) - timedelta(minutes=20)
    if before_personal.hour >= 7:
        assert in_account_active_hours(before_personal, left) is False
        assert farm_overlap_active_hours(early) is True

    uploaded = SimpleNamespace(id=5, created_at=datetime(2026, 9, 21, 10, 0, 0))
    assert profile_edit_allowed(uploaded, now=datetime(2026, 9, 21, 18, 0, 0)) is False
    assert profile_edit_allowed(uploaded, now=datetime(2026, 9, 21, 18, 0, 0), force=True) is True
    later = datetime(2026, 9, 23, 12, 0, 0)
    assert profile_edit_allowed(uploaded, now=later) is True


def test_upload_health_queue_does_not_start_hygiene():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from app.services.custom.neurocommenting_service import is_fresh_channel_post

    now = datetime(2026, 9, 21, 18, 0, 0)
    fresh = SimpleNamespace(date=now.replace(tzinfo=timezone.utc) - timedelta(minutes=5))
    old = SimpleNamespace(date=now.replace(tzinfo=timezone.utc) - timedelta(days=5))
    missing = SimpleNamespace(date=None)
    assert is_fresh_channel_post(fresh, now=now) is True
    assert is_fresh_channel_post(old, now=now) is False
    assert is_fresh_channel_post(missing, now=now) is False
    assert is_fresh_channel_post(old, now=now, lab_mode=True) is True


def test_upload_health_queue_does_not_start_hygiene():
    from app.router_custom.automation_router import _queue_account_health_check

    tasks = MagicMock()
    _queue_account_health_check(tasks, 7)
    assert tasks.add_task.call_count == 1
    queued = tasks.add_task.call_args[0][0]
    name = getattr(queued, "__name__", str(queued)).lower()
    assert "hygiene" not in name
    assert "health" in name or "check" in name
