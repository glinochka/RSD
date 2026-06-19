"""Нормализация контактов из Excel для outreach в WhatsApp / Telegram userbot."""

from __future__ import annotations

import json
import re
from typing import Any

from ..sales_excel_import import _normalize_whatsapp_import_value

_TG_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/(?P<path>[^/?#]+)",
    re.I,
)
_PHONE_DIGITS_RE = re.compile(r"\D+")
_TG_UNDMABLE_PREFIXES = ("joinchat/", "join/", "+", "c/", "addlist/", "addstickers/", "share/")
_TG_RESERVED_USERNAMES = frozenset({"s", "share", "addstickers", "iv", "proxy", "socks"})


def _digits_only(value: str | None) -> str:
    return _PHONE_DIGITS_RE.sub("", value or "")


def _opt(value: str | None) -> str | None:
    s = (value or "").strip()
    return s or None


def _normalize_ru_phone_digits(raw: str | None) -> str | None:
    digits = _digits_only(raw)
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
    return digits


def _phone_targets_from_row(
    *,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> list[str]:
    """Уникальные телефоны: сначала мобильный, затем городской, затем ЛПР."""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in (org_mobile, org_phone, lpr_phone):
        digits = _normalize_ru_phone_digits(raw)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        ordered.append(digits)
    return ordered


def _is_telegram_bot_or_channel_username(username: str) -> bool:
    u = username.strip().lstrip("@").casefold()
    if not u:
        return True
    if u in _TG_RESERVED_USERNAMES:
        return True
    if u.endswith("bot"):
        return True
    return False


def _is_telegram_undmable_path(path: str) -> bool:
    p = path.strip().lstrip("@")
    low = p.casefold()
    if not low:
        return True
    for prefix in _TG_UNDMABLE_PREFIXES:
        if low.startswith(prefix):
            return True
    if _is_telegram_bot_or_channel_username(low):
        return True
    return False


def _telegram_target_from_link(raw: str) -> tuple[str | None, dict[str, Any]]:
    m = _TG_LINK_RE.match(raw.strip())
    if not m:
        return None, {}
    path = m.group("path").strip().lstrip("@")
    if _is_telegram_undmable_path(path):
        return None, {"source": "telegram_link_skipped", "path": path, "raw": raw}
    if path.startswith("+") or path.replace(" ", "").isdigit():
        digits = _normalize_ru_phone_digits(path)
        if digits:
            return f"+{digits}", {"source": "telegram_link_phone", "raw": raw, "digits": digits}
        return None, {"source": "telegram_link_invalid", "raw": raw}
    return path.lstrip("@"), {"source": "telegram_link", "username": path, "raw": raw}


def _telegram_target_from_raw(raw: str) -> tuple[str | None, dict[str, Any]]:
    text = raw.strip()
    if not text:
        return None, {}
    if _TG_LINK_RE.match(text):
        return _telegram_target_from_link(text)
    if text.startswith("@"):
        username = text[1:].strip()
        if _is_telegram_bot_or_channel_username(username):
            return None, {"source": "telegram_at_skipped", "raw": text}
        return username, {"source": "telegram_at", "raw": text}
    if text.startswith("+") or text.isdigit():
        digits = _normalize_ru_phone_digits(text)
        if digits:
            return f"+{digits}", {"source": "telegram_phone", "raw": text, "digits": digits}
    return None, {}


def _telegram_dedup_key(target: str) -> str:
    digits = _normalize_ru_phone_digits(target)
    if digits:
        return f"phone:{digits}"
    return f"user:{target.casefold().lstrip('@')}"


def collect_all_telegram_outreach_targets(
    *,
    telegram: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Все уникальные Telegram-цели: ссылка/username + каждый телефон отдельно."""
    results: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def _add(target: str, hint: dict[str, Any]) -> None:
        key = _telegram_dedup_key(target)
        if key in seen:
            return
        seen.add(key)
        results.append((target, hint))

    if telegram:
        target, hint = _telegram_target_from_raw(telegram)
        if target:
            _add(target, hint)

    for digits in _phone_targets_from_row(
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    ):
        _add(f"+{digits}", {"source": "phone", "digits": digits})

    return results


def collect_all_whatsapp_outreach_targets(
    *,
    whatsapp: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Все уникальные WhatsApp-цели: wa.me-ссылка + каждый телефон отдельно."""
    results: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def _add(digits: str, hint: dict[str, Any]) -> None:
        normalized = _normalize_ru_phone_digits(digits) or digits
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        results.append((normalized, hint))

    if whatsapp:
        normalized = _normalize_whatsapp_import_value(_opt(whatsapp))
        if normalized:
            m = re.search(r"wa\.me/(\d+)", normalized, re.I)
            digits = m.group(1) if m else _digits_only(normalized)
            if len(digits) >= 10:
                _add(digits, {"source": "whatsapp", "raw": whatsapp, "wa_url": normalized})

    for digits in _phone_targets_from_row(
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    ):
        _add(digits, {"source": "phone", "digits": digits})

    return results


def collect_telegram_targets(
    *,
    telegram: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, list[str], dict[str, Any]]:
    """Первый target + остальные (legacy / fallback при отправке)."""
    targets = collect_all_telegram_outreach_targets(
        telegram=telegram,
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    )
    if not targets:
        return None, [], {}
    primary, primary_hint = targets[0]
    fallbacks = [target for target, _ in targets[1:]]
    hint = dict(primary_hint)
    if fallbacks:
        hint["fallback_targets"] = fallbacks
    return primary, fallbacks, hint


def collect_whatsapp_targets(
    *,
    whatsapp: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, list[str], dict[str, Any]]:
    targets = collect_all_whatsapp_outreach_targets(
        whatsapp=whatsapp,
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    )
    if not targets:
        return None, [], {}
    primary, primary_hint = targets[0]
    fallbacks = [target for target, _ in targets[1:]]
    hint = dict(primary_hint)
    if fallbacks:
        hint["fallback_targets"] = fallbacks
    return primary, fallbacks, hint


def normalize_whatsapp_target(
    *,
    whatsapp: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    primary, _fallbacks, hint = collect_whatsapp_targets(
        whatsapp=whatsapp,
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    )
    return primary, hint


def normalize_telegram_target(
    *,
    telegram: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    primary, _fallbacks, hint = collect_telegram_targets(
        telegram=telegram,
        lpr_phone=lpr_phone,
        org_mobile=org_mobile,
        org_phone=org_phone,
    )
    return primary, hint


def pick_outreach_channel(
    row: dict[str, Any],
    *,
    whatsapp_available: bool,
    telegram_available: bool,
) -> tuple[str | None, str | None, dict[str, Any]]:
    """
    Выбор канала и target_external_id для строки Excel.
    Приоритет: заполненная колонка WhatsApp / Telegram → телефон (WA, затем TG).
    """
    has_wa_col = bool(_opt(row.get("whatsapp")))
    has_tg_col = bool(_opt(row.get("telegram")))

    if whatsapp_available and has_wa_col:
        wa_target, wa_hint = normalize_whatsapp_target(
            whatsapp=row.get("whatsapp"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if wa_target:
            return "whatsapp_userbot", wa_target, wa_hint

    if telegram_available and has_tg_col:
        tg_target, tg_hint = normalize_telegram_target(
            telegram=row.get("telegram"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if tg_target:
            return "telegram_userbot", tg_target, tg_hint

    if whatsapp_available:
        wa_target, wa_hint = normalize_whatsapp_target(
            whatsapp=row.get("whatsapp"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if wa_target:
            return "whatsapp_userbot", wa_target, wa_hint

    if telegram_available:
        tg_target, tg_hint = normalize_telegram_target(
            telegram=row.get("telegram"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if tg_target:
            return "telegram_userbot", tg_target, tg_hint

    return None, None, {}


def collect_all_messenger_channels(
    row: dict[str, Any],
    *,
    whatsapp_available: bool,
    telegram_available: bool,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Все уникальные каналы outreach: каждая ссылка и каждый телефон — отдельная очередь."""
    channels: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[str] = set()

    def _append(channel: str, target: str, hint: dict[str, Any]) -> None:
        key = f"{channel}:{target.strip().casefold()}"
        if key in seen:
            return
        seen.add(key)
        channels.append((channel, target, hint))

    phones = {
        "lpr_phone": row.get("lpr_phone"),
        "org_mobile": row.get("org_mobile"),
        "org_phone": row.get("org_phone"),
    }

    if whatsapp_available:
        for target, hint in collect_all_whatsapp_outreach_targets(
            whatsapp=row.get("whatsapp"),
            **phones,
        ):
            _append("whatsapp_userbot", target, hint)

    if telegram_available:
        for target, hint in collect_all_telegram_outreach_targets(
            telegram=row.get("telegram"),
            **phones,
        ):
            _append("telegram_userbot", target, hint)

    return channels


def build_import_dedup_key(
    *,
    org_name: str,
    channel: str,
    target_external_id: str,
) -> str:
    org = re.sub(r"\s+", " ", (org_name or "").strip().casefold())[:120]
    target = (target_external_id or "").strip().casefold()[:120]
    return f"{channel}:{target}:{org}"[:128]


def hint_to_json(hint: dict[str, Any]) -> str | None:
    if not hint:
        return None
    return json.dumps(hint, ensure_ascii=False)
