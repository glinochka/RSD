"""Импорт лидов в общую базу ИИ МОП из Excel (2GIS / Яндекс Карты)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AiMopLead
from ...config import settings
from ...router_websites.utils import generate_slug_from_name
from ..sales_excel_import import parse_sales_excel


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


def _extract_address(extra: dict[str, Any]) -> str | None:
    for key in ("address", "адрес", "org_address"):
        val = extra.get(key)
        if val and str(val).strip():
            return str(val).strip()[:512]
    return None


def _extract_category(extra: dict[str, Any], org_name: str) -> str | None:
    for key in ("category", "рубрика", "rubric", "тип"):
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
    generated_emails = 0
    errors: list[str] = []

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
        if row.get("telegram"):
            extra["telegram"] = row.get("telegram")
        if row.get("whatsapp"):
            extra["whatsapp"] = row.get("whatsapp")

        phone = row.get("lpr_phone") or row.get("org_phone") or row.get("org_mobile")
        dedup = _dedup_key(
            email=None if email_generated else account_email,
            org_name=org_name if email_generated else None,
        )
        existing = await session.scalar(select(AiMopLead).where(AiMopLead.dedup_key == dedup))
        payload = {
            "org_name": org_name[:512],
            "email": account_email[:255],
            "lpr_name": (row.get("lpr_name") or None),
            "phone": (str(phone).strip()[:256] if phone else None),
            "telegram": (str(row.get("telegram") or "").strip()[:512] or None),
            "whatsapp": (str(row.get("whatsapp") or "").strip()[:512] or None),
            "address": _extract_address(extra),
            "category": _extract_category(extra, org_name),
            "yandex_url": _extract_yandex_url(extra, row.get("website")),
            "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None,
            "import_batch_id": batch_id,
            "updated_at": now,
        }
        if existing:
            if existing.status in ("outreach_sent", "processing"):
                skipped += 1
                continue
            for key, val in payload.items():
                if key != "import_batch_id" or existing.import_batch_id is None:
                    setattr(existing, key, val)
            if existing.status == "failed":
                existing.status = "pending"
                existing.last_error = None
            updated += 1
        else:
            session.add(
                AiMopLead(
                    dedup_key=dedup,
                    status="pending",
                    created_at=now,
                    **payload,
                )
            )
            inserted += 1

    await session.flush()
    return {
        "import_batch_id": batch_id,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "generated_emails": generated_emails,
        "errors": errors,
        "total_parsed": len(rows),
    }
