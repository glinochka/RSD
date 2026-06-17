"""Поиск лида ИИ МОП по контакту в мессенджере."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopLead

_PHONE_DIGITS_RE = re.compile(r"\D+")
_ACTIVE_LEAD_STATUSES = ("outreach_queued", "outreach_sent")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digits_only(value: str | None) -> str:
    return _PHONE_DIGITS_RE.sub("", value or "")


def contact_match_keys(user_external_id: str | None) -> set[str]:
    """Нормализованные ключи для сопоставления outreach_target и входящего контакта."""
    keys: set[str] = set()
    raw = (user_external_id or "").strip()
    if not raw:
        return keys

    keys.add(raw)
    keys.add(raw.lower())
    keys.add(raw.lstrip("@").lower())

    local = raw.split("@")[0] if "@" in raw else raw
    digits = _digits_only(local)
    if digits:
        keys.add(digits)
        keys.add(f"+{digits}")
        if len(digits) == 11 and digits.startswith("8"):
            keys.add(f"+7{digits[1:]}")
            keys.add(f"7{digits[1:]}")
        elif len(digits) == 10 and digits.startswith("9"):
            keys.add(f"+7{digits}")
            keys.add(f"7{digits}")

    return {k for k in keys if k}


def _target_keys(target: str | None) -> set[str]:
    return contact_match_keys(target)


def parse_lead_extra(lead: AiMopLead) -> dict[str, Any]:
    raw = lead.extra_json
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def credentials_already_sent(lead: AiMopLead) -> bool:
    return bool(parse_lead_extra(lead).get("credentials_sent"))


async def mark_credentials_sent(*, lead_id: int) -> None:
    now = _utc_now()
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, lead_id)
            if lead is None:
                return
            extra = parse_lead_extra(lead)
            extra["credentials_sent"] = True
            extra["credentials_sent_at"] = now.isoformat()
            lead.extra_json = json.dumps(extra, ensure_ascii=False)
            lead.updated_at = now


async def find_lead_for_contact(
    *,
    agent_id: int,
    user_external_id: str | None,
) -> AiMopLead | None:
    """Найти лида по назначенному агенту и идентификатору контакта в мессенджере."""
    incoming_keys = contact_match_keys(user_external_id)
    if not incoming_keys:
        return None

    async with async_session_maker() as session:
        rows = (
            await session.scalars(
                select(AiMopLead)
                .where(
                    AiMopLead.assigned_agent_id == agent_id,
                    AiMopLead.status.in_(_ACTIVE_LEAD_STATUSES),
                )
                .order_by(AiMopLead.id.desc())
            )
        ).all()

    for lead in rows:
        if _target_keys(lead.outreach_target) & incoming_keys:
            return lead
    return None
