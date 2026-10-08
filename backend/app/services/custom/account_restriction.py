"""Telegram account limits as they actually work, not as a single spamblock flag.

Official FAQ (telegram.org/faq_spam) and runtime errors:

* ``limited`` — classic spam restriction. Cannot write first to strangers or
  invite people. Mutual-contact DMs, replies if they wrote first, groups and
  comments still work. First hit lasts days; repeats last longer.
* ``limited_permanent`` — same scope, no expiry in @SpamBot ("forever").
* ``geo`` — new / VOIP / recycled numbers get the same limited API before they
  even send (FAQ Q8). Scope is still DM+invite, not a total freeze.
* ``frozen`` — FrozenMethodInvalidError. Read-only, appeal window, then the
  account can be deleted. This is the "iron" all-actions block, not PeerFlood.
* ``channel_banned`` — UserBannedInChannelError. Groups/channels refuse writes;
  DMs may still work. Orthogonal to limited.
* FloodWait is a rate-limit, not a spamblock.

There is no official "spamblock that forbids comments forever". That pattern
is freeze or a full ban.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

KIND_NONE = "none"
KIND_LIMITED = "limited"
KIND_LIMITED_PERMANENT = "limited_permanent"
KIND_GEO = "geo"
KIND_FROZEN = "frozen"

LIMITED_KINDS = {KIND_LIMITED, KIND_LIMITED_PERMANENT, KIND_GEO}

DM_ACTIONS = {
    "dm",
    "dmp",
    "dmp_outreach",
    "warmup_dm",
    "lead_warmup",
    "peer_dialog",
    "account_warmup",
}
CHANNEL_WRITE_ACTIONS = {
    "commenting",
    "shilling",
    "discussion",
    "chat_broadcast",
    "masspriming",
    "join",
}

_MONTHS = {
    "jan": 1, "january": 1, "янв": 1, "января": 1, "январь": 1,
    "feb": 2, "february": 2, "фев": 2, "февраля": 2, "февраль": 2,
    "mar": 3, "march": 3, "мар": 3, "марта": 3, "март": 3,
    "apr": 4, "april": 4, "апр": 4, "апреля": 4, "апрель": 4,
    "may": 5, "мая": 5, "май": 5,
    "jun": 6, "june": 6, "июн": 6, "июня": 6, "июнь": 6,
    "jul": 7, "july": 7, "июл": 7, "июля": 7, "июль": 7,
    "aug": 8, "august": 8, "авг": 8, "августа": 8, "август": 8,
    "sep": 9, "september": 9, "сен": 9, "сентября": 9, "сентябрь": 9,
    "oct": 10, "october": 10, "окт": 10, "октября": 10, "октябрь": 10,
    "nov": 11, "november": 11, "ноя": 11, "ноября": 11, "ноябрь": 11,
    "dec": 12, "december": 12, "дек": 12, "декабря": 12, "декабрь": 12,
}

_OK = (
    "good news, no limits",
    "no limits are currently applied",
    "свободен от каких-либо ограничений",
    "нет ограничений",
    "не ограничен",
    "limits have been lifted",
    "restrictions have been lifted",
    "we have lifted",
    "ограничения сняты",
    "сняли ограничения",
    "больше нет ограничений",
)
_BLOCK = (
    "your account is now limited",
    "your account was blocked for spam",
    "limited until",
    "reported them as spam",
    "reported as spam",
    "наложены некоторые ограничения",
    "наложены ограничения",
    "аккаунт ограничен",
    "временно ограничен",
    "получили жалобы",
    "как спам",
    "too many reports",
)
_FOREVER = (
    "forever",
    "permanently",
    "indefinitely",
    "permanent restriction",
    "навсегда",
    "бессрочн",
    "без срока",
    "постоянн",
)
_FROZEN = (
    "your account is frozen",
    "account is frozen",
    "аккаунт заморожен",
    "заморожен до",
    "read-only mode",
    "только чтение",
    "будет удален",
    "будет удалён",
    "will be deleted",
)
_GEO = (
    "virtual number",
    "voip",
    "just signed up",
    "just created",
    "recently created",
    "previous owner",
    "this phone number",
    "new phone numbers",
    "виртуальн",
    "voip-номер",
    "только что создан",
    "недавно создан",
    "новый номер",
    "предыдущ",
    "этот номер",
)
_UNTIL_RE = re.compile(
    r"(?:until|till|limited until|ограничен[аоы]?\s+до|до)\s+"
    r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[a-zA-Zа-яА-ЯёЁ.]+\s+\d{4})",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_NAMED_DATE_RE = re.compile(r"^(\d{1,2})\s+([a-zA-Zа-яА-ЯёЁ.]+)\s+(\d{4})$")

_KIND_LABELS = {
    KIND_LIMITED: "ЛС/инвайт",
    KIND_LIMITED_PERMANENT: "ЛС навсегда",
    KIND_GEO: "Гео-лимит",
    KIND_FROZEN: "Заморозка",
}
_KIND_SCOPES = {
    KIND_LIMITED: "dm_invite",
    KIND_LIMITED_PERMANENT: "dm_invite",
    KIND_GEO: "dm_invite",
    KIND_FROZEN: "all",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


def _parse_until(blob: str) -> datetime | None:
    match = _UNTIL_RE.search(blob or "")
    if not match:
        return None
    raw = match.group(1).strip().rstrip(".")
    numeric = _NUMERIC_DATE_RE.match(raw)
    if numeric:
        day, month, year = (int(numeric.group(1)), int(numeric.group(2)), int(numeric.group(3)))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    iso = _ISO_DATE_RE.match(raw)
    if iso:
        try:
            return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    named = _NAMED_DATE_RE.match(raw)
    if named:
        month = _MONTHS.get(named.group(2).strip(".").lower())
        if not month:
            return None
        try:
            return datetime(int(named.group(3)), month, int(named.group(1)))
        except ValueError:
            return None
    return None


def classify_spambot_reply(text: str | None) -> dict[str, Any] | None:
    """Parse @SpamBot copy into a restriction kind. None = unknown chatter."""
    blob = (text or "").strip().lower()
    if not blob:
        return None
    if any(marker in blob for marker in _OK):
        return {
            "kind": KIND_NONE,
            "blocked": False,
            "until": None,
            "detail": (text or "").strip()[:280],
        }
    if any(marker in blob for marker in _FROZEN):
        return {
            "kind": KIND_FROZEN,
            "blocked": True,
            "until": _parse_until(blob),
            "detail": (text or "").strip()[:280],
        }
    if not any(marker in blob for marker in _BLOCK) and not any(marker in blob for marker in _GEO):
        return None
    until = _parse_until(blob)
    if any(marker in blob for marker in _GEO):
        kind = KIND_GEO
    elif any(marker in blob for marker in _FOREVER) and until is None:
        kind = KIND_LIMITED_PERMANENT
    else:
        kind = KIND_LIMITED
    return {
        "kind": kind,
        "blocked": True,
        "until": until,
        "detail": (text or "").strip()[:280],
    }


def restriction_kind(account: Any, *, now: datetime | None = None) -> str:
    expire_if_due(account, now=now)
    if getattr(account, "is_frozen", False):
        return KIND_FROZEN
    kind = str(getattr(account, "restriction_kind", None) or "").strip().lower()
    if kind in LIMITED_KINDS:
        return kind
    if getattr(account, "is_spamblocked", False):
        return KIND_LIMITED
    return KIND_NONE


def restriction_scope(account: Any) -> str | None:
    kind = restriction_kind(account)
    if getattr(account, "is_channel_banned", False) and kind not in {KIND_FROZEN}:
        if kind in LIMITED_KINDS:
            return "dm_invite_and_channels"
        return "channels"
    return _KIND_SCOPES.get(kind)


def restriction_label(account: Any) -> str | None:
    kind = restriction_kind(account)
    if kind == KIND_NONE and getattr(account, "is_channel_banned", False):
        return "Бан в каналах"
    if kind == KIND_NONE:
        return None
    label = _KIND_LABELS.get(kind, kind)
    until = _naive(getattr(account, "restriction_until", None))
    if kind == KIND_LIMITED and until:
        return f"{label} до {until.strftime('%d.%m')}"
    if getattr(account, "is_channel_banned", False) and kind in LIMITED_KINDS:
        return f"{label} + каналы"
    return label


def expire_if_due(account: Any, *, now: datetime | None = None) -> bool:
    kind = str(getattr(account, "restriction_kind", None) or "").strip().lower()
    if kind == KIND_LIMITED_PERMANENT or kind == KIND_FROZEN:
        return False
    until = _naive(getattr(account, "restriction_until", None))
    if until is None or kind not in LIMITED_KINDS:
        return False
    current = _naive(now) or _utc_now()
    if until > current:
        return False
    clear_limited(account)
    return True


def clear_limited(account: Any) -> None:
    account.is_spamblocked = False
    account.spamblocked_at = None
    kind = str(getattr(account, "restriction_kind", None) or "").strip().lower()
    if kind in LIMITED_KINDS or not kind:
        account.restriction_kind = None
        account.restriction_until = None
        account.restriction_detail = None
    account.spamblock_checked_at = _utc_now()
    account.updated_at = _utc_now()


def apply_restriction_classification(account: Any, info: dict[str, Any] | None) -> None:
    if not info:
        return
    kind = str(info.get("kind") or KIND_NONE).strip().lower()
    account.spamblock_checked_at = _utc_now()
    account.updated_at = _utc_now()
    account.restriction_detail = (info.get("detail") or None)
    if kind == KIND_NONE or info.get("blocked") is False:
        if getattr(account, "is_frozen", False):
            return
        clear_limited(account)
        return
    if kind == KIND_FROZEN:
        account.is_frozen = True
        account.frozen_at = account.frozen_at or _utc_now()
        account.restriction_kind = KIND_FROZEN
        account.restriction_until = info.get("until")
        return
    if kind not in LIMITED_KINDS:
        kind = KIND_LIMITED
    account.is_spamblocked = True
    account.spamblocked_at = account.spamblocked_at or _utc_now()
    account.restriction_kind = kind
    account.restriction_until = info.get("until")


def apply_limited_flag(
    account: Any,
    *,
    blocked: bool,
    kind: str | None = None,
    until: datetime | None = None,
    detail: str | None = None,
) -> None:
    if blocked:
        apply_restriction_classification(
            account,
            {
                "kind": kind or KIND_LIMITED,
                "blocked": True,
                "until": until,
                "detail": detail,
            },
        )
        return
    clear_limited(account)


def restriction_blocks_action(account: Any | None, action_type: str) -> bool:
    if account is None:
        return True
    expire_if_due(account)
    kind = restriction_kind(account)
    if kind == KIND_FROZEN:
        return True
    if kind in LIMITED_KINDS and action_type in DM_ACTIONS:
        return True
    if getattr(account, "is_channel_banned", False) and action_type in CHANNEL_WRITE_ACTIONS:
        return True
    return False
