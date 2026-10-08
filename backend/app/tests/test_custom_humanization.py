"""Humanization session: long-lived read mix, age stages, post-join settle."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.custom.account_pacing import (
    PHASE_OBSERVE,
    PHASE_RAMP,
    PHASE_REPLY,
    STAGE_CAUTIOUS,
    STAGE_NORMAL,
    STAGE_TRUSTED,
    account_humanization_stage,
)
from app.services.custom.account_warmup_service import (
    WARMUP_GAP_MAX_SECONDS,
    WARMUP_GAP_MIN_SECONDS,
    warmup_gap_seconds,
)
from app.services.custom.humanization_session import (
    CommentContactPolicy,
    SEED_CHANNEL_QUERIES,
    _action_catalog,
    add_commenter_contact,
    comment_contact_policy,
    is_comment_contact_day,
    lifetime_comment_contact_cap,
    pick_seed_channel,
    run_humanization_session,
    settle_after_join,
    typing_without_send,
)


class _TypingCM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    def __init__(self):
        self.calls: list[str] = []
        self.client = self

    async def get_dialogs(self, limit=20):
        self.calls.append("get_dialogs")
        user = SimpleNamespace(
            is_user=True,
            is_channel=False,
            is_group=False,
            entity=SimpleNamespace(id=11, bot=False, broadcast=False),
        )
        channel = SimpleNamespace(
            is_user=False,
            is_channel=True,
            is_group=False,
            entity=SimpleNamespace(id=22, bot=False, broadcast=True),
        )
        return [user, channel]

    async def get_messages(self, entity, limit=8, search=None, reply_to=None):
        self.calls.append("search" if search else "get_messages")
        sender = SimpleNamespace(
            id=44,
            bot=False,
            deleted=False,
            is_self=False,
            contact=False,
            first_name="Ира",
            last_name="",
            username="ira_from_comments",
            broadcast=False,
        )
        return [
            SimpleNamespace(
                id=10,
                text="hi",
                sender=sender,
                replies=SimpleNamespace(replies=2),
            )
        ]

    async def get_me(self):
        return SimpleNamespace(id=1)

    async def send_read_acknowledge(self, *args, **kwargs):
        self.calls.append("read")

    async def get_profile_photos(self, *args, **kwargs):
        self.calls.append("photos")
        return []

    async def send_message(self, *args, **kwargs):
        self.calls.append("send_message")
        return SimpleNamespace(id=1)

    async def send_reaction(self, *args, **kwargs):
        self.calls.append("send_reaction")

    async def forward_messages(self, *args, **kwargs):
        self.calls.append("forward_messages")
        return [SimpleNamespace(id=2)]

    async def pin_message(self, *args, **kwargs):
        self.calls.append("pin_message")

    async def edit_folder(self, *args, **kwargs):
        self.calls.append("edit_folder")

    async def get_entity(self, *args, **kwargs):
        self.calls.append("get_entity")
        return SimpleNamespace(id=22, title="Топор", username="topor", broadcast=True, megagroup=False)

    def action(self, entity, kind):
        self.calls.append(f"action:{kind}")
        return _TypingCM()

    async def __call__(self, request):
        name = type(request).__name__
        self.calls.append(name)
        if name == "SearchRequest":
            return SimpleNamespace(
                chats=[SimpleNamespace(id=55, title="Топор", username="topor", broadcast=True)],
                users=[],
                results=[],
            )
        return SimpleNamespace(peer_stories=[], stories=[], authorizations=[])


def _account(*, days: int) -> SimpleNamespace:
    now = datetime.utcnow().replace(tzinfo=None)
    return SimpleNamespace(id=7, created_at=now - timedelta(days=days))


def test_warmup_gap_lengthens_for_new_accounts():
    from app.services.custom.account_pacing import activity_interval_scale

    now = datetime.utcnow().replace(tzinfo=None)
    fresh = SimpleNamespace(created_at=now - timedelta(days=1))
    aged = SimpleNamespace(created_at=now - timedelta(days=20))
    assert account_humanization_stage(fresh, now=now) == STAGE_CAUTIOUS
    assert account_humanization_stage(aged, now=now) == STAGE_NORMAL
    scale = activity_interval_scale(fresh, now=now)
    for _ in range(15):
        assert 2 * 3600 * scale <= warmup_gap_seconds(fresh) <= 4 * 3600 * scale + 1
        assert WARMUP_GAP_MIN_SECONDS <= warmup_gap_seconds(aged) <= WARMUP_GAP_MAX_SECONDS
        assert WARMUP_GAP_MIN_SECONDS <= warmup_gap_seconds() <= WARMUP_GAP_MAX_SECONDS


def test_action_catalog_withholds_writes_from_new_accounts():
    cautious = {name for name, _fn in _action_catalog(STAGE_CAUTIOUS)}
    normal = {name for name, _fn in _action_catalog(STAGE_NORMAL)}
    trusted = {name for name, _fn in _action_catalog(STAGE_TRUSTED)}
    assert "stories" in cautious
    assert "scroll_channels" in cautious
    assert "typing_idle" in cautious
    assert "search_public" in cautious
    assert "read_comments" in cautious
    assert "react" not in cautious
    assert "comment_contact" not in cautious
    assert "saved" not in cautious
    assert "draft" not in cautious
    assert "ask_chat" not in cautious
    assert "react" in normal
    assert "draft" in normal
    assert "comment_contact" in normal
    ramp_new = {name for name, _fn in _action_catalog(STAGE_CAUTIOUS, phase=PHASE_RAMP)}
    assert "react" in ramp_new
    assert "comment_contact" in ramp_new
    assert "typing_idle" in ramp_new
    assert "forward_saved" in normal
    assert "saved" not in normal
    assert "saved" in trusted
    assert "comment_contact" in trusted
    assert "ask_chat" in trusted
    assert "pin_dm" in trusted
    observe = {name for name, _fn in _action_catalog(STAGE_CAUTIOUS, phase=PHASE_OBSERVE)}
    assert "react" in observe
    assert "comment_contact" in observe
    assert "typing_idle" in observe
    assert "search_public" not in observe
    assert "ask_chat" not in observe
    reply = {name for name, _fn in _action_catalog(STAGE_CAUTIOUS, phase=PHASE_REPLY)}
    assert "react_dm" in reply
    assert "ask_chat" not in reply


def test_seed_channel_search_picks_the_named_channels():
    assert SEED_CHANNEL_QUERIES == (
        "Рифмы и Панчи",
        "Топор Live",
        "Казань на максималках",
    )
    rhymes = SimpleNamespace(title="Рифмы и Панчи", username="rhymes", broadcast=True, megagroup=False, bot=False)
    noise = SimpleNamespace(title="Рифмы для детей", username="kids", broadcast=True, megagroup=False, bot=False)
    topor = SimpleNamespace(title="Топор Live", username="toporlive", broadcast=True, megagroup=False, bot=False)
    magazine = SimpleNamespace(title="ТОПОР", username="topor", broadcast=True, megagroup=False, bot=False)
    kazan = SimpleNamespace(title="Казань на максималках", username="kazanmax", broadcast=True, megagroup=False, bot=False)
    assert pick_seed_channel([noise, rhymes], "Рифмы и Панчи") is rhymes
    assert pick_seed_channel([magazine, topor], "Топор Live") is topor
    assert pick_seed_channel([kazan], "Казань на максималках") is kazan
    assert pick_seed_channel([magazine], "Топор Live") is None


@pytest.mark.asyncio
async def test_typing_without_send_does_not_send_message():
    client = FakeClient()
    ok = await typing_without_send(client, lab_mode=True)
    assert ok is True
    assert "get_dialogs" in client.calls
    assert "send_message" not in client.calls


@pytest.mark.asyncio
async def test_humanization_session_opens_dialogs_in_lab():
    client = FakeClient()
    outcome = await run_humanization_session(client, _account(days=40), lab_mode=True)
    assert outcome["stage"] == STAGE_TRUSTED
    assert "browse" in outcome["actions"]
    assert "get_dialogs" in client.calls
    assert "offline" not in outcome["actions"]
    assert "idle_hold" not in outcome["actions"]


@pytest.mark.asyncio
async def test_humanization_session_stays_online_after_primary_warmup(monkeypatch):
    calls: list[bool] = []

    async def fake_presence(client, *, offline, lab_mode=False):
        del client, lab_mode
        calls.append(offline)
        return True

    monkeypatch.setattr("app.services.custom.humanization_session.set_presence", fake_presence)
    outcome = await run_humanization_session(
        FakeClient(),
        _account(days=40),
        lab_mode=True,
        stay_online=True,
    )
    assert calls == [False]
    assert "offline" not in outcome["actions"]
    assert "idle_hold" not in outcome["actions"]
    assert "online" in outcome["actions"]


@pytest.mark.asyncio
async def test_settle_after_join_reads_history():
    client = FakeClient()
    account = _account(days=2)
    result = await settle_after_join(client, SimpleNamespace(id=99), account, lab_mode=True)
    assert "scroll" in result["actions"]
    assert "get_messages" in client.calls


def test_comment_contact_is_not_a_daily_quota():
    aged = _account(days=20)
    cap = lifetime_comment_contact_cap(aged.id)
    assert 9 <= cap <= 17
    assert comment_contact_policy(aged, added_count=cap).reason == "cap"
    assert comment_contact_policy(_account(days=2)).reason == "cautious"
    assert comment_contact_policy(aged, added_count=1, attempted_today=True).reason == "already_today"
    recent = datetime.utcnow().replace(tzinfo=None) - timedelta(hours=6)
    blocked = comment_contact_policy(aged, added_count=1, last_success_at=recent)
    assert blocked.allow is False
    assert blocked.reason in {"gap", "not_today"}

    due_day = None
    off_day = None
    start = datetime.utcnow().replace(tzinfo=None).date()
    for offset in range(40):
        day = start + timedelta(days=offset)
        if is_comment_contact_day(aged.id, day):
            due_day = day
        else:
            off_day = day
        if due_day and off_day:
            break
    assert due_day and off_day
    assert comment_contact_policy(
        aged,
        added_count=1,
        last_success_at=datetime.utcnow().replace(tzinfo=None) - timedelta(days=10),
        now=datetime(due_day.year, due_day.month, due_day.day, 12, 0),
    ).allow is True
    assert comment_contact_policy(
        aged,
        added_count=1,
        last_success_at=datetime.utcnow().replace(tzinfo=None) - timedelta(days=10),
        now=datetime(off_day.year, off_day.month, off_day.day, 12, 0),
    ).reason == "not_today"


def test_observe_phase_may_add_one_contact(monkeypatch):
    import app.services.custom.account_pacing as pacing

    monkeypatch.setattr(pacing, "SETTLE_HOURS", 24)
    now = datetime.utcnow().replace(tzinfo=None)
    young = SimpleNamespace(id=7, created_at=now - timedelta(hours=30))
    gate = comment_contact_policy(young, now=now)
    assert gate.allow is True
    assert comment_contact_policy(young, added_count=1, now=now).reason == "early_cap"


@pytest.mark.asyncio
async def test_adds_one_commenter_when_due_and_skips_when_capped():
    client = FakeClient()
    account = _account(days=20)
    denied = await add_commenter_contact(
        client,
        lab_mode=True,
        account=account,
        policy=CommentContactPolicy(False, "cap", cap=12, added=12),
    )
    assert denied is False
    ok = await add_commenter_contact(
        client,
        lab_mode=True,
        account=account,
        policy=CommentContactPolicy(True, "ok", cap=12, added=2),
    )
    assert ok is True
    assert client._comment_contact["status"] == "success"
    assert client._comment_contact["user_id"] == 44

