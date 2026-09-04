"""Cross-key deduplication for CustomLead (phone, telegram username, telegram id)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .telegram_account_client import normalize_telegram_phone
from ...alembic.models import CustomLead, LeadStatus

_INACTIVE_STATUSES = {LeadStatus.LOST.value, LeadStatus.SPAM.value}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _phone_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_telegram_phone(str(value).strip())
    return normalized or None


def _telegram_username_key(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip().lstrip("@").lower()
    if not raw or _phone_key(raw):
        return None
    return raw


def _telegram_id_key(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip().lstrip("-")
    if raw.isdigit():
        return raw
    return None


def lead_dedup_keys(
    contact_type: str | None,
    contact_value: str | None,
    raw: dict[str, Any] | None = None,
) -> set[str]:
    keys: set[str] = set()
    raw = raw if isinstance(raw, dict) else {}

    phone = None
    if (contact_type or "").strip().lower() == "phone":
        phone = _phone_key(contact_value)
    if not phone:
        for key in ("phone", "phone_number", "tel"):
            if raw.get(key):
                phone = _phone_key(str(raw[key]))
                if phone:
                    break
    if phone:
        keys.add(f"phone:{phone}")

    if (contact_type or "").strip().lower() == "telegram" and contact_value:
        value = str(contact_value).strip()
        phone_from_value = _phone_key(value)
        if phone_from_value:
            keys.add(f"phone:{phone_from_value}")
        else:
            user_key = _telegram_username_key(value)
            if user_key:
                keys.add(f"tg_user:{user_key}")
            tg_id = _telegram_id_key(value)
            if tg_id:
                keys.add(f"tg_id:{tg_id}")

    for key in ("telegram", "telegram_username", "tg"):
        if raw.get(key):
            user_key = _telegram_username_key(str(raw[key]))
            if user_key:
                keys.add(f"tg_user:{user_key}")
    for key in ("telegram_id", "tg_id", "resolved_telegram_id"):
        if raw.get(key):
            tg_id = _telegram_id_key(str(raw[key]))
            if tg_id:
                keys.add(f"tg_id:{tg_id}")
    if raw.get("resolved_telegram"):
        user_key = _telegram_username_key(str(raw["resolved_telegram"]))
        if user_key:
            keys.add(f"tg_user:{user_key}")

    return keys


def collect_lead_keys(lead: CustomLead) -> set[str]:
    return lead_dedup_keys(lead.contact_type, lead.contact_value, lead.dmp_raw_data)


async def find_canonical_lead(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
    *,
    include_inactive: bool = False,
) -> CustomLead:
    keys = collect_lead_keys(lead)
    if not keys:
        return lead
    result = await session.execute(
        select(CustomLead).where(CustomLead.custom_automation_id == automation_id)
    )
    matches: list[CustomLead] = []
    for candidate in result.scalars().all():
        if not include_inactive and candidate.status in _INACTIVE_STATUSES:
            continue
        if collect_lead_keys(candidate) & keys:
            matches.append(candidate)
    if not matches:
        return lead
    return min(matches, key=lambda item: (item.created_at or _utc_now(), item.id))


async def find_existing_lead(
    session: AsyncSession,
    automation_id: int,
    *,
    contact_type: str,
    contact_value: str,
    raw: dict[str, Any] | None = None,
    exclude_id: int | None = None,
) -> CustomLead | None:
    keys = lead_dedup_keys(contact_type, contact_value, raw)
    if not keys:
        return None
    result = await session.execute(
        select(CustomLead)
        .where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.status.notin_(tuple(_INACTIVE_STATUSES)),
        )
        .order_by(CustomLead.created_at.asc(), CustomLead.id.asc())
    )
    for lead in result.scalars().all():
        if exclude_id and lead.id == exclude_id:
            continue
        if collect_lead_keys(lead) & keys:
            return lead
    return None


async def mark_lead_duplicate(
    session: AsyncSession,
    lead: CustomLead,
    canonical: CustomLead,
    *,
    reason: str = "duplicate",
) -> bool:
    if lead.id == canonical.id or lead.status in _INACTIVE_STATUSES:
        return False
    lead.status = LeadStatus.LOST.value
    lead.status_history = (lead.status_history or []) + [
        {
            "status": LeadStatus.LOST.value,
            "changed_at": _utc_now().isoformat(),
            "reason": reason,
            "duplicate_of": canonical.id,
        }
    ]
    lead.updated_at = _utc_now()
    return True
