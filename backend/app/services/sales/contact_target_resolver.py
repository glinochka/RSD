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


def _digits_only(value: str | None) -> str:
    return _PHONE_DIGITS_RE.sub("", value or "")


def normalize_whatsapp_target(
    *,
    whatsapp: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Возвращает (user_external_id для аналитики/очереди, hint)."""
    for raw in (whatsapp, lpr_phone, org_mobile, org_phone):
        normalized = _normalize_whatsapp_import_value(_opt(raw))
        if not normalized:
            continue
        m = re.search(r"wa\.me/(\d+)", normalized, re.I)
        digits = m.group(1) if m else _digits_only(normalized)
        if len(digits) >= 10:
            return digits, {"source": "whatsapp", "raw": raw, "wa_url": normalized}
    return None, {}


def _opt(value: str | None) -> str | None:
    s = (value or "").strip()
    return s or None


def normalize_telegram_target(
    *,
    telegram: str | None = None,
    lpr_phone: str | None = None,
    org_mobile: str | None = None,
    org_phone: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """
    target_external_id: numeric id, @username, или телефон в международном формате (+7...).
    Telethon get_entity принимает эти формы на отправке.
    """
    if telegram:
        raw = telegram.strip()
        m = _TG_LINK_RE.match(raw)
        if m:
            path = m.group("path").strip().lstrip("@")
            if path.startswith("+") or path.replace(" ", "").isdigit():
                digits = _digits_only(path)
                if len(digits) >= 10:
                    if len(digits) == 11 and digits.startswith("8"):
                        digits = "7" + digits[1:]
                    elif len(digits) == 10 and digits.startswith("9"):
                        digits = "7" + digits
                    return f"+{digits}", {"source": "telegram_link", "path": path, "raw": raw}
            if path:
                return path.lstrip("@"), {"source": "telegram_link", "username": path, "raw": raw}
        if raw.startswith("@"):
            return raw[1:], {"source": "telegram_at", "raw": raw}
        if raw.startswith("+") or raw.isdigit():
            digits = _digits_only(raw)
            if len(digits) >= 10:
                return f"+{digits}", {"source": "telegram_phone", "raw": raw}

    for raw in (lpr_phone, org_mobile, org_phone):
        if not raw:
            continue
        digits = _digits_only(raw)
        if len(digits) >= 10:
            if len(digits) == 11 and digits.startswith("8"):
                digits = "7" + digits[1:]
            elif len(digits) == 10 and digits.startswith("9"):
                digits = "7" + digits
            return f"+{digits}", {"source": "phone", "raw": raw}
    return None, {}


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
    """Все доступные каналы outreach (WhatsApp + Telegram), без выбора одного."""
    channels: list[tuple[str, str, dict[str, Any]]] = []
    if whatsapp_available:
        wa_target, wa_hint = normalize_whatsapp_target(
            whatsapp=row.get("whatsapp"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if wa_target:
            channels.append(("whatsapp_userbot", wa_target, wa_hint))
    if telegram_available:
        tg_target, tg_hint = normalize_telegram_target(
            telegram=row.get("telegram"),
            lpr_phone=row.get("lpr_phone"),
            org_mobile=row.get("org_mobile"),
            org_phone=row.get("org_phone"),
        )
        if tg_target:
            channels.append(("telegram_userbot", tg_target, tg_hint))
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
