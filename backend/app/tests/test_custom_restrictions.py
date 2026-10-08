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
from app.services.custom.account_session_guard_service import plan_session_guard
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
