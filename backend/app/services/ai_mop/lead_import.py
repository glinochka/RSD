"""Импорт лидов в общую базу ИИ МОП из Excel (2GIS / Яндекс Карты)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AiMopLead
from ...config import settings
from ...router_websites.utils import generate_slug_from_name
from ..sales_excel_import import parse_sales_excel

_EMAIL_LOCAL_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?P<num>\d+)$")
_MAX_ACCOUNT_EMAIL_CANDIDATES = 1000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dedup_key(*, email: str | None = None, org_name: str | None = None) -> str:
    if email and "@" in email:
        normalized = email.strip().casefold()
    else:
        normalized = (org_name or "").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:64]


def generate_account_email_from_org(org_name: str) -> str:
    """Login-email из латинского slug названия компании."""
    slug = generate_slug_from_name(org_name.strip() or "business")
    domain = (settings.AI_MOP_ACCOUNT_EMAIL_DOMAIN or "rsd-ai.ru").strip().lstrip("@")
    return f"{slug}@{domain}"[:255]


def account_email_candidates(preferred_email: str, *, max_candidates: int = _MAX_ACCOUNT_EMAIL_CANDIDATES) -> list[str]:
    """Варианты email: base@domain, base1@domain, base2@domain, …"""
    preferred = preferred_email.strip().casefold()
    local, _, domain = preferred.rpartition("@")
    if not local or not domain:
        raise ValueError(f"Invalid account email: {preferred_email}")

    match = _EMAIL_LOCAL_SUFFIX_RE.match(local)
    if match:
        base_local = match.group("base")
        start_suffix = int(match.group("num"))
        candidates = [f"{base_local}{start_suffix}@{domain}"]
        first_suffix = start_suffix + 1
    else:
        base_local = local
        candidates = [f"{base_local}@{domain}"]
        first_suffix = 1

    for suffix in range(first_suffix, first_suffix + max(0, max_candidates - len(candidates))):
        candidate = f"{base_local}{suffix}@{domain}"
        if candidate not in candidates:
            candidates.append(candidate)
    return [candidate[:255] for candidate in candidates]


async def allocate_unique_account_email(user_dao, preferred_email: str) -> str:
    """Подобрать свободный login-email, добавляя суффикс 1, 2, 3… при занятости."""
    for candidate in account_email_candidates(preferred_email):
        existing = await user_dao.find_one_by_filter(email=candidate)
        if existing is None:
            return candidate
    raise ValueError(f"Could not allocate unique account email for {preferred_email}")


def _extract_address(extra: dict[str, Any], *, city: str | None = None, region: str | None = None) -> str | None:
    addr = None
    for key in ("address", "адрес", "org_address"):
        val = extra.get(key)
        if val and str(val).strip():
            addr = str(val).strip()
            break
    parts = [p.strip() for p in (region, city, addr) if p and str(p).strip()]
    if parts:
        return ", ".join(dict.fromkeys(parts))[:512]
    return None


def _extract_category(extra: dict[str, Any], org_name: str) -> str | None:
    rubric = None
    subrubric = None
    for key in ("rubric", "рубрика", "category_rubric"):
        val = extra.get(key)
        if val and str(val).strip():
            rubric = str(val).strip()
            break
    for key in ("subrubric", "подрубрика", "category_subrubric"):
        val = extra.get(key)
        if val and str(val).strip():
            subrubric = str(val).strip()
            break
    if rubric and subrubric:
        return f"{rubric} — {subrubric}"[:256]
    if rubric:
        return rubric[:256]
    for key in ("category", "рубрика", "rubric"):
        val = extra.get(key)
        if val and str(val).strip():
            return str(val).strip()[:256]
    return None


def _extract_yandex_url(extra: dict[str, Any], website: str | None) -> str | None:
    for candidate in (extra.get("yandex_url"), extra.get("yandex"), extra.get("карта"), website):
        if not candidate:
            continue
        s = str(candidate).strip()
        if "yandex" in s.casefold() and ("maps" in s.casefold() or "map" in s.casefold()):
            return s[:512]
    return None


def _apply_import_payload(existing: AiMopLead, payload: dict[str, Any]) -> None:
    for key, val in payload.items():
        if key != "import_batch_id" or existing.import_batch_id is None:
            setattr(existing, key, val)
    if existing.status == "failed":
        existing.status = "pending"
        existing.last_error = None


async def _find_existing_lead(
    session: AsyncSession,
    *,
    dedup: str,
    batch_by_dedup: dict[str, AiMopLead],
) -> AiMopLead | None:
    pending = batch_by_dedup.get(dedup)
    if pending is not None:
        return pending
    with session.no_autoflush:
        return await session.scalar(select(AiMopLead).where(AiMopLead.dedup_key == dedup))


async def import_ai_mop_leads_from_excel(
    session: AsyncSession,
    *,
    file_bytes: bytes,
) -> dict[str, Any]:
    """Парсит Excel и upsert-ит лиды в ai_mop_leads."""
    rows = parse_sales_excel(file_bytes)
    batch_id = uuid.uuid4().hex[:16]
    now = _utc_now()
    inserted = 0
    updated = 0
    skipped = 0
    skipped_duplicate_in_file = 0
    generated_emails = 0
    errors: list[str] = []
    batch_by_dedup: dict[str, AiMopLead] = {}

    for row in rows:
        org_name = (row.get("org_name") or "").strip()
        if not org_name:
            skipped += 1
            continue

        contact_email = (row.get("email") or "").strip()
        if contact_email and "@" in contact_email:
            account_email = contact_email
            email_generated = False
        else:
            account_email = generate_account_email_from_org(org_name)
            email_generated = True
            generated_emails += 1

        extra = dict(row.get("extras") or {}) if isinstance(row.get("extras"), dict) else {}
        if contact_email and "@" in contact_email:
            extra["contact_email"] = contact_email
        extra["account_email_generated"] = email_generated
        if row.get("region"):
            extra.setdefault("region", row.get("region"))
        if row.get("city"):
            extra.setdefault("city", row.get("city"))
        if row.get("category_rubric"):
            extra.setdefault("rubric", row.get("category_rubric"))
        if row.get("category_subrubric"):
            extra.setdefault("subrubric", row.get("category_subrubric"))
        if row.get("telegram"):
            extra["telegram"] = row.get("telegram")
        if row.get("whatsapp"):
            extra["whatsapp"] = row.get("whatsapp")
        if row.get("messenger_max"):
            extra["messenger_max"] = row.get("messenger_max")
        if row.get("vk"):
            extra["vk"] = row.get("vk")
        if row.get("youtube"):
            extra["youtube"] = row.get("youtube")
        for phone_key in ("lpr_phone", "org_phone", "org_mobile"):
            val = row.get(phone_key)
            if val and str(val).strip():
                extra[phone_key] = str(val).strip()

        phone = row.get("org_mobile") or row.get("org_phone") or row.get("lpr_phone")
        dedup = _dedup_key(
            email=None if email_generated else account_email,
            org_name=org_name if email_generated else None,
        )
        if dedup in batch_by_dedup:
            skipped_duplicate_in_file += 1

        existing = await _find_existing_lead(session, dedup=dedup, batch_by_dedup=batch_by_dedup)
        payload = {
            "org_name": org_name[:512],
            "email": account_email[:255],
            "lpr_name": (row.get("lpr_name") or None),
            "phone": (str(phone).strip()[:256] if phone else None),
            "telegram": (str(row.get("telegram") or "").strip()[:512] or None),
            "whatsapp": (str(row.get("whatsapp") or "").strip()[:512] or None),
            "address": _extract_address(
                extra,
                city=(row.get("city") or extra.get("city")),
                region=(row.get("region") or extra.get("region")),
            ),
            "category": _extract_category(extra, org_name),
            "yandex_url": _extract_yandex_url(extra, row.get("website")),
            "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None,
            "import_batch_id": batch_id,
            "updated_at": now,
        }
        if existing:
            if existing.status in ("outreach_sent", "processing", "provisioned", "outreach_queued"):
                skipped += 1
                batch_by_dedup[dedup] = existing
                continue
            _apply_import_payload(existing, payload)
            updated += 1
            batch_by_dedup[dedup] = existing
        else:
            lead = AiMopLead(
                dedup_key=dedup,
                status="pending",
                created_at=now,
                **payload,
            )
            session.add(lead)
            batch_by_dedup[dedup] = lead
            inserted += 1

    await session.flush()
    return {
        "import_batch_id": batch_id,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "skipped_duplicate_in_file": skipped_duplicate_in_file,
        "generated_emails": generated_emails,
        "errors": errors,
        "total_parsed": len(rows),
    }
