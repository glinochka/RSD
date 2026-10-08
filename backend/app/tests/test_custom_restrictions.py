"""Restriction kinds, rotation skips, and session-guard planning."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.custom.account_restriction import (
    KIND_FROZEN,
    KIND_GEO,
    KIND_LIMITED,
    KIND_LIMITED_PERMANENT,
    KIND_NONE,
    apply_restriction_classification,
    classify_spambot_reply,
    expire_if_due,
    restriction_blocks_action,
    restriction_kind,
    restriction_label,
)
import pytest

from app.services.custom.account_session_guard_service import (
    decline_pending_password_reset,
    enforce_authorizations,
    looks_like_login_alert,
    plan_session_guard,
)
from app.services.custom.telegram_error_handler import parse_spambot_reply


def test_classify_spambot_kinds():
    clean = classify_spambot_reply("Good news, no limits are currently applied to your account.")
    assert clean["kind"] == KIND_NONE
    assert parse_spambot_reply(clean["detail"]) is False

    limited = classify_spambot_reply(
        "I'm afraid some Telegram users found your messages annoying and have reported them as spam. "
        "Your account is now limited until 15.10.2026."
    )
    assert limited["kind"] == KIND_LIMITED
    assert limited["until"].day == 15
    assert parse_spambot_reply("На ваш аккаунт наложены некоторые ограничения.") is True

    forever = classify_spambot_reply("Your account is now limited permanently / forever.")
    assert forever["kind"] == KIND_LIMITED_PERMANENT

    geo = classify_spambot_reply(
        "This phone number was recently created. Virtual numbers and VOIP are limited until you can write first."
    )
    assert geo["kind"] == KIND_GEO

    frozen = classify_spambot_reply("Your account is frozen. It will be deleted unless you appeal.")
    assert frozen["kind"] == KIND_FROZEN


def test_limited_blocks_dm_not_comments():
    account = SimpleNamespace(
        is_frozen=False,
        is_spamblocked=True,
        is_channel_banned=False,
        restriction_kind=KIND_LIMITED,
        restriction_until=None,
    )
    assert restriction_blocks_action(account, "dm") is True
    assert restriction_blocks_action(account, "dmp_outreach") is True
    assert restriction_blocks_action(account, "account_warmup") is True
    assert restriction_blocks_action(account, "peer_dialog") is True
    assert restriction_blocks_action(account, "inbound_dm") is False
    assert restriction_blocks_action(account, "commenting") is False
    assert restriction_blocks_action(account, "shilling") is False
    assert restriction_blocks_action(account, "discussion") is False
    assert restriction_blocks_action(account, "join") is False


def test_frozen_blocks_everything_channel_ban_blocks_groups():
    frozen = SimpleNamespace(
        is_frozen=True,
        is_spamblocked=False,
        is_channel_banned=False,
        restriction_kind=KIND_FROZEN,
        restriction_until=None,
    )
    assert restriction_kind(frozen) == KIND_FROZEN
    assert restriction_blocks_action(frozen, "commenting") is True
    banned = SimpleNamespace(
        is_frozen=False,
        is_spamblocked=False,
        is_channel_banned=True,
        restriction_kind=None,
        restriction_until=None,
    )
    assert restriction_blocks_action(banned, "commenting") is True
    assert restriction_blocks_action(banned, "dm") is False


def test_temporary_limit_expires():
    account = SimpleNamespace(
        is_frozen=False,
        is_spamblocked=True,
        restriction_kind=KIND_LIMITED,
        restriction_until=datetime.utcnow() - timedelta(hours=1),
        restriction_detail="old",
        spamblocked_at=datetime.utcnow(),
        spamblock_checked_at=None,
        updated_at=None,
    )
    assert expire_if_due(account) is True
    assert account.is_spamblocked is False
    assert restriction_kind(account) == KIND_NONE


def test_restriction_label_uses_until_date():
    account = SimpleNamespace(
        is_frozen=False,
        is_spamblocked=True,
        is_channel_banned=False,
        restriction_kind=KIND_LIMITED,
        restriction_until=datetime(2026, 10, 15),
    )
    assert "15.10" in (restriction_label(account) or "")


def test_apply_classification_sets_flags():
    account = SimpleNamespace(
        is_frozen=False,
        is_spamblocked=False,
        spamblocked_at=None,
        spamblock_checked_at=None,
        frozen_at=None,
        restriction_kind=None,
        restriction_until=None,
        restriction_detail=None,
        updated_at=None,
    )
    apply_restriction_classification(
        account,
        {"kind": KIND_GEO, "blocked": True, "until": None, "detail": "voip"},
    )
    assert account.is_spamblocked is True
    assert account.restriction_kind == KIND_GEO


def test_session_guard_kills_newcomers_except_during_pause():
    live = [
        {"hash": "0", "current": True},
        {"hash": "111", "current": False},
        {"hash": "999", "current": False},
    ]
    snapshot = plan_session_guard(set(), live, paused=False)
    assert snapshot["action"] == "snapshot"
    assert snapshot["terminate"] == []

    enforce = plan_session_guard({"0", "111"}, live, paused=False)
    assert enforce["action"] == "enforce"
    assert enforce["terminate"] == ["999"]

    paused = plan_session_guard({"0", "111"}, live, paused=True)
    assert paused["action"] == "pause_adopt"
    assert paused["terminate"] == []
    assert "999" in paused["keep"]


def test_session_guard_takeover_drops_every_extra_device():
    live = [
        {"hash": "0", "current": True},
        {"hash": "111", "current": False},
        {"hash": "999", "current": False},
    ]
    takeover = plan_session_guard(set(), live, paused=False, takeover=True)
    assert takeover["action"] == "takeover"
    assert takeover["terminate"] == ["111", "999"]
    assert takeover["keep"] == {"0"}

    hold = plan_session_guard(set(), [{"hash": "0", "current": True}], paused=False, takeover=True)
    assert hold["action"] == "hold"
    assert hold["terminate"] == []


def test_farm_guard_kills_incomplete_but_keeps_old_devices():
    live = [
        {"hash": "0", "current": True},
        {"hash": "111", "current": False},
        {"hash": "222", "current": False, "unconfirmed": True},
        {"hash": "333", "current": False, "password_pending": True},
    ]
    first = plan_session_guard(set(), live, paused=False)
    assert "111" in first["keep"]
    assert set(first["terminate"]) == {"222", "333"}

    later = plan_session_guard({"0", "111"}, live, paused=False)
    assert set(later["terminate"]) == {"222", "333"}
    assert "111" not in later["terminate"]


def test_login_alert_text_matches_new_and_incomplete_logins():
    assert looks_like_login_alert("New login detected from Chrome")
    assert looks_like_login_alert("Обнаружен новый вход в аккаунт")
    assert looks_like_login_alert("Незавершенная попытка входа")
    assert looks_like_login_alert("код для входа 12345") is False


@pytest.mark.asyncio
async def test_enforce_authorizations_drops_newcomer_on_farm():
    auths = [
        SimpleNamespace(
            hash=0, current=True, device_model="PC", platform="Windows", app_name="A",
            app_version="1", ip="1.1.1.1", country="RU", region="", date_created=1,
            date_active=2, password_pending=False, unconfirmed=False,
        ),
        SimpleNamespace(
            hash=111, current=False, device_model="iPhone", platform="iOS", app_name="Telegram",
            app_version="1", ip="2.2.2.2", country="RU", region="", date_created=1,
            date_active=2, password_pending=False, unconfirmed=False,
        ),
        SimpleNamespace(
            hash=999, current=False, device_model="Chrome", platform="Web", app_name="Telegram",
            app_version="1", ip="3.3.3.3", country="DE", region="", date_created=1,
            date_active=2, password_pending=False, unconfirmed=True,
        ),
    ]
    calls: list[str] = []

    class FakeClient:
        async def get_messages(self, peer, limit=8):
            calls.append("get_messages")
            return []

        async def __call__(self, request):
            name = type(request).__name__
            calls.append(name)
            if name == "GetAuthorizationsRequest":
                return SimpleNamespace(authorizations=list(auths))
            if name == "ResetAuthorizationRequest":
                auths[:] = [item for item in auths if int(item.hash) != int(request.hash)]
                return True
            if name == "GetPasswordRequest":
                return SimpleNamespace(pending_reset_date=None)
            if name == "DeclinePasswordResetRequest":
                return True
            raise AssertionError(name)

    account = SimpleNamespace(
        id=4,
        origin="farm",
        session_guard_enabled=True,
        session_guard_paused_until=None,
        session_guard_checked_at=None,
        cloud_password_reset_checked_at=None,
        known_auth_hashes=["0", "111"],
        telegram_session_count=None,
        created_at=datetime.utcnow() - timedelta(days=10),
        updated_at=None,
    )
    result = await enforce_authorizations(FakeClient(), account, force=True)
    assert "999" in result["terminated"]
    assert "111" not in result["terminated"]
    assert "0" in account.known_auth_hashes
    assert "111" in account.known_auth_hashes
    assert "GetAuthorizationsRequest" in calls


@pytest.mark.asyncio
async def test_decline_pending_cloud_password_reset():
    calls: list[str] = []

    class FakeClient:
        async def __call__(self, request):
            name = type(request).__name__
            calls.append(name)
            if name == "GetPasswordRequest":
                return SimpleNamespace(pending_reset_date=1_700_000_000)
            if name == "DeclinePasswordResetRequest":
                return True
            raise AssertionError(name)

    account = SimpleNamespace(
        id=5,
        cloud_password_reset_checked_at=None,
        updated_at=None,
    )
    result = await decline_pending_password_reset(FakeClient(), account, force=True)
    assert result["pending"] is True
    assert result["declined"] is True
    assert "DeclinePasswordResetRequest" in calls
    assert account.cloud_password_reset_checked_at is not None
