"""Sasha AI autodial: push DMP contacts, receive call results, qualify leads.

Sasha AI docs: https://docs.trysasha.ru/api-ref
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .lead_dedup import find_existing_lead
from .telegram_account_client import normalize_telegram_phone
from ...alembic.models import CustomAutomation, CustomLead, LeadStatus, SashaAiCall
from ...config import settings

logger = logging.getLogger(__name__)

SASHA_STATUS_QUEUED = "queued"
SASHA_STATUS_UPLOADED = "uploaded"
SASHA_STATUS_SKIPPED = "skipped"
SASHA_STATUS_CALLED = "called"
SASHA_STATUS_CONNECTED = "connected"
SASHA_STATUS_COMMITTED = "committed"
SASHA_STATUS_REJECTED = "rejected"
SASHA_STATUS_NO_ANSWER = "no_answer"
SASHA_STATUS_FAILED = "failed"

_COMMITTED_LEAD_STATUSES = {
    LeadStatus.QUALIFIED.value,
    LeadStatus.TRANSFERRED.value,
    LeadStatus.PROCESSING.value,
    LeadStatus.CONVERTED.value,
}
_INACTIVE_LEAD_STATUSES = {LeadStatus.LOST.value, LeadStatus.SPAM.value}
_UPLOAD_URL_RE = re.compile(r"upload-contacts-integrations/webhook/", re.IGNORECASE)
_SASHA_HOST_HINTS = ("trysasha", "aicalls")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def public_sasha_webhook_url(automation_id: int, secret: str | None) -> str:
    base = (settings.BASE_URL or "").rstrip("/")
    if not base or not secret:
        return ""
    return f"{base}/api/custom/webhooks/sasha/{automation_id}/{secret}"


def ensure_sasha_webhook_secret(automation: CustomAutomation) -> str:
    if automation.sasha_webhook_secret:
        return automation.sasha_webhook_secret
    automation.sasha_webhook_secret = secrets.token_urlsafe(24)
    return automation.sasha_webhook_secret


def rotate_sasha_webhook_secret(automation: CustomAutomation) -> str:
    automation.sasha_webhook_secret = secrets.token_urlsafe(24)
    return automation.sasha_webhook_secret


def _secrets_match(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def sasha_webhook_secret_ok(automation: CustomAutomation | None, incoming: str) -> bool:
    incoming = (incoming or "").strip()
    if not incoming or not automation:
        return False
    return _secrets_match(incoming, (automation.sasha_webhook_secret or "").strip())


def verify_sasha_hmac(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    expected = (secret or "").strip()
    incoming = (signature or "").strip()
    if incoming.lower().startswith("sha256="):
        incoming = incoming.split("=", 1)[1].strip()
    if not expected or not incoming:
        return False
    computed = hmac.new(expected.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if len(computed) != len(incoming):
        return False
    return hmac.compare_digest(computed, incoming.lower())


def sasha_is_configured(automation: CustomAutomation | None) -> bool:
    if not automation:
        return False
    return bool((automation.sasha_upload_url or "").strip())


def sasha_takes_over(automation: CustomAutomation | None) -> bool:
    if not automation or not automation.is_sasha_ai_enabled:
        return False
    if not bool(getattr(automation, "sasha_auto_push", True)):
        return False
    return sasha_is_configured(automation)


def sasha_phone_digits(value: str | None) -> str | None:
    normalized = normalize_telegram_phone(value)
    if not normalized:
        digits = re.sub(r"\D+", "", value or "")
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10 and digits.startswith("9"):
            digits = "7" + digits
        if len(digits) >= 11:
            return digits[:11] if digits.startswith("7") else digits
        return None
    return normalized.lstrip("+")


def lead_sasha_phone(lead: CustomLead) -> str | None:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    if lead.contact_type == "phone":
        return sasha_phone_digits(lead.contact_value)
    for key in ("phone", "phone_number", "tel"):
        if raw.get(key):
            digits = sasha_phone_digits(str(raw.get(key)))
            if digits:
                return digits
    return sasha_phone_digits(lead.contact_value)


def validate_sasha_upload_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Укажите полный HTTPS URL вебхука загрузки контактов Sasha AI")
    if not _UPLOAD_URL_RE.search(parsed.path) and not any(hint in parsed.netloc.lower() for hint in _SASHA_HOST_HINTS):
        raise ValueError(
            "URL должен быть webhook загрузки контактов Sasha AI "
            "(…/api/upload-contacts-integrations/webhook/…)"
        )
    return value


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _website_tag(website: str) -> str:
    raw = (website or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or parsed.path or raw).lower()
    return host[4:] if host.startswith("www.") else host


def build_sasha_contact(lead: CustomLead, *, upload_format: str = "api") -> dict[str, Any] | None:
    phone = lead_sasha_phone(lead)
    if not phone:
        return None
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    website = _stringify(raw.get("website") or lead.company)
    page = _stringify(raw.get("page") or lead.position)
    name = _stringify(lead.full_name or raw.get("name") or raw.get("full_name") or raw.get("fio"))
    company = _stringify(lead.company or raw.get("company") or raw.get("organization"))
    ip = _stringify(raw.get("ip"))
    if (upload_format or "api").lower() == "dmp":
        payload: dict[str, Any] = {"phone": phone}
        if website:
            payload["website"] = website
        extras = {
            "page": page,
            "ip": ip,
            "name": name,
            "company": company,
            "lead_id": str(lead.id),
        }
        for key, value in extras.items():
            if value:
                payload[key] = value
        return payload

    tags = ["dmp.one"]
    site_tag = _website_tag(website)
    if site_tag:
        tags.append(site_tag)
    additional: dict[str, Any] = {"lead_id": str(lead.id)}
    if name:
        additional["client_name"] = name
    if website:
        additional["website"] = website
    if page:
        additional["page"] = page
    if company:
        additional["company"] = company
    if ip:
        additional["ip"] = ip
    return {"phone": phone, "tags": tags, "additionalFields": additional}


def _patch_sasha_meta(lead: CustomLead, **fields: Any) -> None:
    raw = dict(lead.dmp_raw_data or {}) if isinstance(lead.dmp_raw_data, dict) else {}
    blob = dict(raw.get("sasha") or {}) if isinstance(raw.get("sasha"), dict) else {}
    blob.update(fields)
    raw["sasha"] = blob
    lead.dmp_raw_data = raw


def sasha_settings_payload(automation: CustomAutomation) -> dict[str, Any]:
    secret = automation.sasha_webhook_secret
    return {
        "is_sasha_ai_enabled": bool(automation.is_sasha_ai_enabled),
        "sasha_upload_url": automation.sasha_upload_url or "",
        "sasha_upload_format": automation.sasha_upload_format or "api",
        "sasha_auto_push": bool(getattr(automation, "sasha_auto_push", True)),
        "sasha_qualify_on_commit": bool(getattr(automation, "sasha_qualify_on_commit", True)),
        "sasha_notify_on_commit": bool(getattr(automation, "sasha_notify_on_commit", True)),
        "sasha_webhook_secret": secret,
        "sasha_webhook_url": public_sasha_webhook_url(automation.id, secret),
        "sasha_hmac_secret": automation.sasha_hmac_secret or "",
        "sasha_hmac_secret_set": bool((automation.sasha_hmac_secret or "").strip()),
        "sasha_connected": bool(automation.is_sasha_ai_enabled and sasha_is_configured(automation)),
    }


def apply_sasha_settings(automation: CustomAutomation, payload: dict[str, Any]) -> None:
    if "is_sasha_ai_enabled" in payload and payload["is_sasha_ai_enabled"] is not None:
        automation.is_sasha_ai_enabled = bool(payload["is_sasha_ai_enabled"])
    if "sasha_upload_url" in payload and payload["sasha_upload_url"] is not None:
        automation.sasha_upload_url = validate_sasha_upload_url(str(payload["sasha_upload_url"]))
    if "sasha_upload_format" in payload and payload["sasha_upload_format"]:
        fmt = str(payload["sasha_upload_format"]).strip().lower()
        automation.sasha_upload_format = fmt if fmt in {"api", "dmp"} else "api"
    if "sasha_hmac_secret" in payload and payload["sasha_hmac_secret"] is not None:
        automation.sasha_hmac_secret = str(payload["sasha_hmac_secret"]).strip() or None
    if "sasha_auto_push" in payload and payload["sasha_auto_push"] is not None:
        automation.sasha_auto_push = bool(payload["sasha_auto_push"])
    if "sasha_qualify_on_commit" in payload and payload["sasha_qualify_on_commit"] is not None:
        automation.sasha_qualify_on_commit = bool(payload["sasha_qualify_on_commit"])
    if "sasha_notify_on_commit" in payload and payload["sasha_notify_on_commit"] is not None:
        automation.sasha_notify_on_commit = bool(payload["sasha_notify_on_commit"])
    if automation.is_sasha_ai_enabled or sasha_is_configured(automation):
        ensure_sasha_webhook_secret(automation)
    if sasha_is_configured(automation) and payload.get("is_sasha_ai_enabled") is None:
        if payload.get("sasha_upload_url"):
            automation.is_sasha_ai_enabled = True
    automation.updated_at = _utc_now()


async def push_lead_to_sasha(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    if not sasha_is_configured(automation):
        return {"status": "not_configured", "lead_id": lead.id}
    if lead.status in _INACTIVE_LEAD_STATUSES:
        return {"status": "skipped", "reason": lead.status, "lead_id": lead.id}
    if lead.sasha_status in {SASHA_STATUS_UPLOADED, SASHA_STATUS_COMMITTED, SASHA_STATUS_CONNECTED, SASHA_STATUS_CALLED}:
        return {"status": lead.sasha_status, "lead_id": lead.id, "already": True}

    contact = build_sasha_contact(lead, upload_format=automation.sasha_upload_format or "api")
    if not contact:
        lead.sasha_status = SASHA_STATUS_SKIPPED
        lead.updated_at = _utc_now()
        _patch_sasha_meta(lead, last_error="Нет телефона для прозвона")
        await session.commit()
        return {"status": SASHA_STATUS_SKIPPED, "reason": "no_phone", "lead_id": lead.id}

    lead.sasha_status = SASHA_STATUS_QUEUED
    lead.updated_at = _utc_now()
    await session.commit()

    url = (automation.sasha_upload_url or "").strip()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=[contact], headers={"Content-Type": "application/json"})
            body_text = (response.text or "")[:1000]
            try:
                data = response.json() if response.content else {}
            except Exception:
                data = {}
            if response.status_code >= 400:
                raise RuntimeError(f"Sasha AI HTTP {response.status_code}: {body_text or data}")
    except Exception as exc:
        logger.warning("Sasha AI upload failed for lead %s: %s", lead.id, exc)
        lead.sasha_status = SASHA_STATUS_FAILED
        lead.updated_at = _utc_now()
        _patch_sasha_meta(lead, last_error=str(exc)[:400], last_payload=contact)
        await session.commit()
        return {"status": SASHA_STATUS_FAILED, "error": str(exc)[:400], "lead_id": lead.id}

    skipped = data.get("skippedPhones") if isinstance(data, dict) else None
    skipped_reason = ""
    if isinstance(skipped, list):
        phone = contact.get("phone")
        for item in skipped:
            if not isinstance(item, dict):
                continue
            if sasha_phone_digits(str(item.get("phone") or "")) == phone or str(item.get("phone") or "") == phone:
                skipped_reason = str(item.get("reason") or "skipped")
                break
    uploaded = int(data.get("uploadedCount") or 0) if isinstance(data, dict) else 0
    now = _utc_now()
    if skipped_reason and uploaded == 0:
        already = "существует" in skipped_reason.lower() or "already" in skipped_reason.lower()
        lead.sasha_status = SASHA_STATUS_UPLOADED if already else SASHA_STATUS_SKIPPED
        _patch_sasha_meta(lead, last_error=skipped_reason, last_response=data)
    else:
        lead.sasha_status = SASHA_STATUS_UPLOADED
        _patch_sasha_meta(lead, last_error=None, last_response=data)
    lead.sasha_uploaded_at = now
    lead.updated_at = now
    await session.commit()
    return {
        "status": lead.sasha_status,
        "lead_id": lead.id,
        "uploaded_count": uploaded,
        "skipped_reason": skipped_reason or None,
        "message": (data.get("message") if isinstance(data, dict) else None),
    }


async def maybe_send_lead_to_sasha(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any] | None:
    if not sasha_takes_over(automation):
        return None
    return await push_lead_to_sasha(session, automation, lead)


async def push_pending_leads(automation_id: int, *, limit: int = 40) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    pushed = 0
    failed = 0
    skipped = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not automation.is_sasha_ai_enabled or not sasha_is_configured(automation):
            return {"pushed": 0, "failed": 0, "skipped": 0, "reason": "not_configured"}
        result = await session.execute(
            select(CustomLead)
            .where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.status.notin_(tuple(_INACTIVE_LEAD_STATUSES)),
                CustomLead.sasha_status.in_((SASHA_STATUS_QUEUED, SASHA_STATUS_FAILED, None, "")),
            )
            .order_by(CustomLead.created_at.asc())
            .limit(limit)
        )
        leads = list(result.scalars().all())
        pending = await session.execute(
            select(CustomLead)
            .where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.source == "dmp_one",
                CustomLead.sasha_status.is_(None),
                CustomLead.status.notin_(tuple(_INACTIVE_LEAD_STATUSES)),
            )
            .order_by(CustomLead.created_at.asc())
            .limit(max(0, limit - len(leads)))
        )
        seen = {lead.id for lead in leads}
        for lead in pending.scalars().all():
            if lead.id not in seen:
                leads.append(lead)
        for lead in leads:
            outcome = await push_lead_to_sasha(session, automation, lead)
            status_value = outcome.get("status")
            if status_value == SASHA_STATUS_UPLOADED:
                pushed += 1
            elif status_value == SASHA_STATUS_FAILED:
                failed += 1
            else:
                skipped += 1
    return {"pushed": pushed, "failed": failed, "skipped": skipped}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _quality(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, number))


def format_transcript(history: list | None) -> str:
    lines: list[str] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "").lower()
        speaker = "Клиент" if role == "user" else "Sasha"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def warmth_label(quality: int | None) -> str:
    if quality is None:
        return "не оценён"
    if quality >= 7:
        return "горячий"
    if quality >= 4:
        return "тёплый"
    return "холодный"


def call_outcome_label(row: SashaAiCall) -> str:
    if row.is_commit:
        return "лид"
    if (row.agreements_status or "") == "close":
        return "отказ"
    if (row.session_result_status or "") == "failed" or (row.status or "") == "failed":
        return "недозвон"
    if (row.lead_destination or "") == "callback":
        return "перезвон"
    if (row.status or "") == "completed":
        return "разговор"
    return row.event_type or "событие"


def sasha_card_payload(call: SashaAiCall | None) -> dict[str, Any]:
    if call is None:
        return {}
    return {
        "is_commit": bool(call.is_commit),
        "client_name": call.client_name,
        "client_facts": call.client_facts,
        "agreements": call.agreements,
        "lead_quality": call.lead_quality,
        "lead_destination": call.lead_destination,
        "record_url": call.record_url,
        "transcript": format_transcript(call.transcript),
        "outcome": call_outcome_label(call),
    }


def format_sasha_lead_message(lead: CustomLead, call: SashaAiCall | None = None) -> str:
    from .telegram_notify_bot_service import format_lead_bot_message

    return format_lead_bot_message(lead, sasha=sasha_card_payload(call) or None)


async def _match_lead(
    session: AsyncSession,
    automation_id: int,
    *,
    phone: str | None,
    additional: dict[str, Any],
) -> CustomLead | None:
    lead_id = additional.get("lead_id") or additional.get("leadId")
    if lead_id:
        try:
            lead = await session.get(CustomLead, int(lead_id))
        except (TypeError, ValueError):
            lead = None
        if lead and lead.custom_automation_id == automation_id:
            return lead
    digits = sasha_phone_digits(phone)
    if not digits:
        return None
    return await find_existing_lead(
        session,
        automation_id,
        contact_type="phone",
        contact_value=digits,
        raw={"phone": digits, **additional},
    )


async def _ensure_lead_for_call(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    phone: str | None,
    additional: dict[str, Any],
    client_name: str | None,
) -> CustomLead | None:
    lead = await _match_lead(session, automation.id, phone=phone, additional=additional)
    if lead:
        return lead
    digits = sasha_phone_digits(phone)
    if not digits:
        return None
    now = _utc_now()
    lead = CustomLead(
        custom_automation_id=automation.id,
        source="sasha_ai",
        contact_type="phone",
        contact_value=digits,
        full_name=client_name or None,
        company=_stringify(additional.get("website") or additional.get("company")) or None,
        position=_stringify(additional.get("page")) or None,
        dmp_raw_data={"phone": digits, **additional, "source": "sasha_ai"},
        status=LeadStatus.NEW.value,
        sasha_status=SASHA_STATUS_CALLED,
        created_at=now,
        updated_at=now,
    )
    session.add(lead)
    await session.flush()
    return lead


def _event_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("id") or "").strip()
    if value:
        return value[:64]
    call_id = str((_as_dict(payload.get("call")).get("id") or "")).strip()
    event_type = str(payload.get("type") or "call_result")
    if call_id:
        return f"{event_type}:{call_id}"[:64]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return digest[:64]


async def handle_sasha_webhook(
    session: AsyncSession,
    automation: CustomAutomation,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_id = _event_id(payload)
    existing = await session.scalar(
        select(SashaAiCall).where(
            SashaAiCall.custom_automation_id == automation.id,
            SashaAiCall.event_id == event_id,
        )
    )
    if existing:
        return {"status": "duplicate", "call_id": existing.id, "lead_id": existing.custom_lead_id}

    call_data = _as_dict(payload.get("call"))
    contact = _as_dict(payload.get("contact"))
    agreements = _as_dict(call_data.get("agreements"))
    details = _as_dict(call_data.get("callDetails"))
    session_data = _as_dict(call_data.get("callSession"))
    session_result = _as_dict(session_data.get("result"))
    additional = _as_dict(contact.get("additionalFields"))
    call_list = _as_dict(payload.get("callList"))
    transcript = _as_list(details.get("chatHistory"))
    phone = contact.get("phone") or additional.get("phone")
    is_commit = bool(agreements.get("isCommit"))
    quality = _quality(agreements.get("lead_quality"))
    client_name = _stringify(agreements.get("client_name")) or None
    client_facts = _stringify(agreements.get("client_facts")) or None
    agreement_text = _stringify(agreements.get("agreements")) or None
    event_type = str(payload.get("type") or "call_result")
    call_status = _stringify(call_data.get("status")) or None
    hangup = _stringify(call_data.get("hangupReason")) or None
    now = _utc_now()

    lead = await _ensure_lead_for_call(
        session,
        automation,
        phone=str(phone) if phone else None,
        additional=additional,
        client_name=client_name,
    )

    row = SashaAiCall(
        custom_automation_id=automation.id,
        custom_lead_id=lead.id if lead else None,
        event_id=event_id,
        event_type=event_type[:32],
        call_id=_stringify(call_data.get("id")) or None,
        session_id=_stringify(session_data.get("id")) or None,
        call_list_id=_stringify(call_list.get("id")) or None,
        call_list_name=_stringify(call_list.get("name")) or None,
        phone=sasha_phone_digits(str(phone) if phone else None),
        status=call_status,
        hangup_reason=hangup,
        duration_ms=int(call_data["duration"]) if isinstance(call_data.get("duration"), (int, float)) else None,
        started_at=_parse_dt(call_data.get("startedAt")),
        connected_at=_parse_dt(call_data.get("connectedAt")),
        ended_at=_parse_dt(call_data.get("endedAt")),
        is_commit=is_commit,
        client_name=client_name,
        client_facts=client_facts,
        agreements=agreement_text,
        lead_quality=quality,
        lead_destination=_stringify(agreements.get("lead_destination")) or None,
        agreements_status=_stringify(agreements.get("status")) or None,
        session_result_status=_stringify(session_result.get("status")) or None,
        session_result_reason=_stringify(session_result.get("reason")) or None,
        record_url=_stringify(call_data.get("recordUrl")) or None,
        transcript=transcript,
        lead_transfer=_as_dict(agreements.get("leadTransfer")),
        raw_payload=payload,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    call_row_id = row.id
    lead_id = lead.id if lead else None

    notified = False
    if lead:
        notified = await _apply_call_to_lead(
            session, automation, lead, row, contact=contact, additional=additional,
        )

    await session.commit()
    return {
        "status": "accepted",
        "call_id": call_row_id,
        "lead_id": lead_id,
        "event_type": event_type,
        "is_commit": is_commit,
        "notified": notified,
    }


async def _apply_call_to_lead(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
    call: SashaAiCall,
    *,
    contact: dict[str, Any],
    additional: dict[str, Any],
) -> bool:
    now = _utc_now()
    lead.sasha_last_event_at = now
    lead.sasha_external_contact_id = _stringify(contact.get("id")) or lead.sasha_external_contact_id
    if call.client_name and not lead.full_name:
        lead.full_name = call.client_name
    elif call.client_name:
        lead.full_name = call.client_name
    website = _stringify(additional.get("website"))
    if website and not lead.company:
        lead.company = website
    if call.lead_quality is not None:
        lead.sasha_lead_quality = call.lead_quality
    summary_parts = [part for part in (call.client_facts, call.agreements) if part]
    if summary_parts:
        lead.sasha_summary = " · ".join(summary_parts)[:2000]
    elif call.transcript:
        lead.sasha_summary = format_transcript(call.transcript)[:2000]

    if call.is_commit:
        lead.sasha_is_commit = True
        lead.sasha_status = SASHA_STATUS_COMMITTED
    elif (call.agreements_status or "") == "close":
        lead.sasha_status = SASHA_STATUS_REJECTED
    elif (call.session_result_status or "") == "failed" or (call.status or "") == "failed":
        lead.sasha_status = SASHA_STATUS_NO_ANSWER
    elif (call.status or "") == "completed":
        lead.sasha_status = SASHA_STATUS_CONNECTED
    else:
        lead.sasha_status = SASHA_STATUS_CALLED
    lead.updated_at = now
    _patch_sasha_meta(
        lead,
        last_event_type=call.event_type,
        last_call_id=call.call_id,
        last_outcome=call_outcome_label(call),
        last_error=None,
        **sasha_card_payload(call),
    )

    if call.is_commit:
        return await _handle_committed_lead(session, automation, lead, call)
    return False


async def _handle_committed_lead(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
    call: SashaAiCall,
) -> bool:
    if lead.status not in _COMMITTED_LEAD_STATUSES and getattr(automation, "sasha_qualify_on_commit", True):
        lead.status = LeadStatus.QUALIFIED.value
        lead.status_history = (lead.status_history or []) + [
            {
                "status": LeadStatus.QUALIFIED.value,
                "changed_at": _utc_now().isoformat(),
                "reason": "sasha_commit",
                "lead_quality": call.lead_quality,
            }
        ]

    if not getattr(automation, "sasha_notify_on_commit", True):
        return False
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    blob = raw.get("sasha") if isinstance(raw.get("sasha"), dict) else {}
    if blob.get("notified_event_id"):
        return True

    from .solution_templates import is_dmp_notify_pipeline, uses_sales_handoff

    if is_dmp_notify_pipeline(automation) or uses_sales_handoff(automation):
        from .lead_warmup_service import auto_transfer_lead

        delivered = await auto_transfer_lead(
            session,
            automation.id,
            lead,
            handoff_reason="sasha_commit",
        )
        bot = delivered.get("bot") if isinstance(delivered.get("bot"), dict) else {}
        bot_sent = delivered.get("bot_sent") or bot.get("bot_sent")
        sent = bool(delivered.get("transferred") or bot_sent)
    else:
        from .telegram_notify_bot_service import dispatch_sales_bot_notification

        delivered = await dispatch_sales_bot_notification(
            session,
            automation,
            lead,
            handoff_reason="sasha_commit",
        )
        bot_sent = delivered.get("bot_sent")
        sent = bool(bot_sent or delivered.get("transferred"))
    if sent:
        await session.refresh(lead)
        _patch_sasha_meta(lead, notified_event_id=call.event_id, bot_sent=bot_sent)
    return sent


def serialize_sasha_call(row: SashaAiCall) -> dict[str, Any]:
    return {
        "id": row.id,
        "custom_automation_id": row.custom_automation_id,
        "custom_lead_id": row.custom_lead_id,
        "event_id": row.event_id,
        "event_type": row.event_type,
        "call_id": row.call_id,
        "session_id": row.session_id,
        "call_list_id": row.call_list_id,
        "call_list_name": row.call_list_name,
        "phone": row.phone,
        "status": row.status,
        "hangup_reason": row.hangup_reason,
        "duration_ms": row.duration_ms,
        "started_at": row.started_at,
        "connected_at": row.connected_at,
        "ended_at": row.ended_at,
        "is_commit": row.is_commit,
        "client_name": row.client_name,
        "client_facts": row.client_facts,
        "agreements": row.agreements,
        "lead_quality": row.lead_quality,
        "warmth": warmth_label(row.lead_quality),
        "lead_destination": row.lead_destination,
        "agreements_status": row.agreements_status,
        "session_result_status": row.session_result_status,
        "session_result_reason": row.session_result_reason,
        "record_url": row.record_url,
        "transcript": row.transcript or [],
        "transcript_text": format_transcript(row.transcript),
        "lead_transfer": row.lead_transfer or {},
        "outcome": call_outcome_label(row),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def list_sasha_calls(
    session: AsyncSession,
    automation_id: int,
    *,
    outcome: str | None = None,
    lead_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SashaAiCall], int]:
    stmt = select(SashaAiCall).where(SashaAiCall.custom_automation_id == automation_id)
    count_stmt = select(func.count(SashaAiCall.id)).where(SashaAiCall.custom_automation_id == automation_id)
    if lead_id:
        stmt = stmt.where(SashaAiCall.custom_lead_id == lead_id)
        count_stmt = count_stmt.where(SashaAiCall.custom_lead_id == lead_id)
    if outcome == "committed":
        stmt = stmt.where(SashaAiCall.is_commit.is_(True))
        count_stmt = count_stmt.where(SashaAiCall.is_commit.is_(True))
    elif outcome == "rejected":
        stmt = stmt.where(SashaAiCall.agreements_status == "close")
        count_stmt = count_stmt.where(SashaAiCall.agreements_status == "close")
    elif outcome == "no_answer":
        stmt = stmt.where(
            (SashaAiCall.status == "failed") | (SashaAiCall.session_result_status == "failed")
        )
        count_stmt = count_stmt.where(
            (SashaAiCall.status == "failed") | (SashaAiCall.session_result_status == "failed")
        )
    elif outcome == "talked":
        stmt = stmt.where(SashaAiCall.status == "completed")
        count_stmt = count_stmt.where(SashaAiCall.status == "completed")
    result = await session.execute(
        stmt.order_by(SashaAiCall.created_at.desc()).limit(limit).offset(offset)
    )
    total = await session.scalar(count_stmt)
    return list(result.scalars().all()), int(total or 0)


async def sasha_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    total_calls = await session.scalar(
        select(func.count(SashaAiCall.id)).where(SashaAiCall.custom_automation_id == automation_id)
    )
    committed = await session.scalar(
        select(func.count(SashaAiCall.id)).where(
            SashaAiCall.custom_automation_id == automation_id,
            SashaAiCall.is_commit.is_(True),
        )
    )
    completed = await session.scalar(
        select(func.count(SashaAiCall.id)).where(
            SashaAiCall.custom_automation_id == automation_id,
            SashaAiCall.status == "completed",
        )
    )
    failed = await session.scalar(
        select(func.count(SashaAiCall.id)).where(
            SashaAiCall.custom_automation_id == automation_id,
            SashaAiCall.status == "failed",
        )
    )
    avg_quality = await session.scalar(
        select(func.avg(SashaAiCall.lead_quality)).where(
            SashaAiCall.custom_automation_id == automation_id,
            SashaAiCall.lead_quality.isnot(None),
        )
    )
    uploaded = await session.scalar(
        select(func.count(CustomLead.id)).where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.sasha_status.in_(
                (
                    SASHA_STATUS_UPLOADED,
                    SASHA_STATUS_CALLED,
                    SASHA_STATUS_CONNECTED,
                    SASHA_STATUS_COMMITTED,
                    SASHA_STATUS_REJECTED,
                    SASHA_STATUS_NO_ANSWER,
                )
            ),
        )
    )
    queued = await session.scalar(
        select(func.count(CustomLead.id)).where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.sasha_status.in_((SASHA_STATUS_QUEUED, SASHA_STATUS_FAILED)),
        )
    )
    committed_leads = await session.scalar(
        select(func.count(CustomLead.id)).where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.sasha_is_commit.is_(True),
        )
    )
    return {
        "queued": int(queued or 0),
        "uploaded": int(uploaded or 0),
        "calls": int(total_calls or 0),
        "completed": int(completed or 0),
        "failed": int(failed or 0),
        "committed_calls": int(committed or 0),
        "committed_leads": int(committed_leads or 0),
        "avg_quality": round(float(avg_quality), 1) if avg_quality is not None else None,
    }
