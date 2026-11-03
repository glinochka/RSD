"""DMP.one integration: create orders, receive webhooks/poll results, warm leads."""
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .lead_dedup import find_canonical_lead, find_existing_lead, mark_lead_duplicate
from .rotation_service import moscow_day_start_utc_naive, select_account_for_action
from .telegram_account_client import TelegramAccountClient, normalize_telegram_phone
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import (
    AutomationActionLog,
    CustomAutomation,
    CustomLead,
    CustomLeadMessage,
    CustomPrompt,
    DmpOneImport,
    LeadStatus,
    PromptType,
    SocialAccount,
)
from ...config import settings
from ...services.ai_authoring import ai_client
from .prompt_service import render_prompt

logger = logging.getLogger(__name__)


DEFAULT_DMP_OUTREACH_PROMPT = """Ты — живой человек в Telegram, пишешь первое сообщение посетителю сайта.
Коротко, по-человечески, без рекламного тона.
Имя: {name}
Компания: {company}
Сайт: {website}
Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}
Уже регистрировался: {registered}

Верни ТОЛЬКО JSON:
{
  "message": "текст первого сообщения"
}"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.DMP_ONE_API_BASE_URL,
        headers={"Authorization": f"Bearer {settings.DMP_ONE_API_KEY}"} if settings.DMP_ONE_API_KEY else {},
        timeout=settings.DMP_ONE_TIMEOUT_SECONDS,
    )


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.DMP_OUTREACH.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_DMP_OUTREACH_PROMPT


async def _generate_outreach_message(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    name: str,
    company: str,
    website: str = "",
    page: str = "",
    registered: str = "unknown",
) -> str:
    prompt = render_prompt(
        await _load_prompt(session, automation.id),
        {
            "name": name or "",
            "company": company or "",
            "website": website or "",
            "page": page or "",
            "partner_utm_url": (automation.partner_utm_url or "").strip(),
            "partner_promo_code": (automation.partner_promo_code or "").strip(),
            "registered": registered or "unknown",
        },
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        from .conversation_guard import sanitize_public_text

        return sanitize_public_text(str(data.get("message") or "").strip())[:500]
    except Exception as exc:
        logger.warning("DMP outreach generation failed: %s", exc)
        return ""


def public_webhook_url(automation_id: int, secret: str | None) -> str:
    base = (settings.BASE_URL or "").rstrip("/")
    if not base or not secret:
        return ""
    return f"{base}/api/custom/webhooks/dmp/{automation_id}/{secret}"


def ensure_dmp_webhook_secret(automation: CustomAutomation) -> str:
    if automation.dmp_webhook_secret:
        return automation.dmp_webhook_secret
    automation.dmp_webhook_secret = secrets.token_urlsafe(24)
    return automation.dmp_webhook_secret


def rotate_dmp_webhook_secret(automation: CustomAutomation) -> str:
    automation.dmp_webhook_secret = secrets.token_urlsafe(24)
    return automation.dmp_webhook_secret


def _secrets_match(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def dmp_webhook_secret_ok(automation: CustomAutomation | None, incoming: str) -> bool:
    incoming = (incoming or "").strip()
    if not incoming:
        return False
    own = (automation.dmp_webhook_secret or "").strip() if automation else ""
    if own:
        return _secrets_match(incoming, own)
    return _secrets_match(incoming, (settings.DMP_ONE_WEBHOOK_SECRET or "").strip())


def _callback_url(automation: CustomAutomation) -> str:
    secret = ensure_dmp_webhook_secret(automation)
    return public_webhook_url(automation.id, secret)


def lead_phone(lead: CustomLead) -> str | None:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    if lead.contact_type == "phone":
        return normalize_telegram_phone(lead.contact_value) or lead.contact_value
    for key in ("phone", "phone_number", "tel"):
        value = raw.get(key)
        if value:
            return normalize_telegram_phone(str(value)) or str(value)
    return None


def lead_website(lead: CustomLead) -> str:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    return str(raw.get("website") or lead.company or "")


def lead_page(lead: CustomLead) -> str:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    return str(raw.get("page") or lead.position or "")


async def check_lead_conversion(
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    url = (automation.conversion_check_url or "").strip()
    if not url:
        return {"skipped": True, "registered": None, "subscribed": None}
    payload = {
        "automation_id": automation.id,
        "lead_id": lead.id,
        "phone": lead_phone(lead),
        "website": lead_website(lead),
        "page": lead_page(lead),
        "contact_type": lead.contact_type,
        "contact_value": lead.contact_value,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json() if response.content else {}
    except Exception as exc:
        logger.warning("Conversion check failed for lead %s: %s", lead.id, exc)
        return {"skipped": True, "registered": None, "subscribed": None, "error": str(exc)[:200]}
    if not isinstance(data, dict):
        return {"skipped": True, "registered": None, "subscribed": None}
    registered = data.get("registered")
    subscribed = data.get("subscribed") if "subscribed" in data else data.get("purchased")
    return {
        "skipped": False,
        "registered": bool(registered) if registered is not None else None,
        "subscribed": bool(subscribed) if subscribed is not None else None,
        "raw": data,
    }


MAX_PHONE_IMPORTS_PER_DAY = 5


async def _phone_imports_today(session: AsyncSession, account_id: int) -> int:
    started = moscow_day_start_utc_naive()
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == "contact_import",
            AutomationActionLog.created_at >= started,
        )
    )
    return int(count or 0)


def _telegram_value_from_user(user: Any, fallback_phone: str | None) -> str:
    username = (getattr(user, "username", None) or "").strip()
    if username:
        return username.lstrip("@")
    user_id = getattr(user, "id", None)
    if user_id:
        return str(user_id)
    return fallback_phone or "unknown"


async def resolve_telegram_for_lead(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> str | None:
    """Resolve a DMP phone to a Telegram user via a trusted account (ImportContacts)."""
    if lead.contact_type == "telegram" and lead.contact_value and lead.contact_value != "unknown":
        if not normalize_telegram_phone(lead.contact_value):
            return lead.contact_value
    phone = lead_phone(lead)
    if not phone:
        return None
    from .chat_monitoring_module_service import leadgen_restrict_ids

    account = await select_account_for_action(
        session,
        automation,
        "dmp_outreach",
        thread_id=lead.id,
        consume_quota=False,
        restrict_account_ids=leadgen_restrict_ids(automation),
    )
    if not account or not account.session_file_path:
        return None
    if await _phone_imports_today(session, account.id) >= MAX_PHONE_IMPORTS_PER_DAY:
        logger.info("Skipping phone resolve for lead %s: daily ImportContacts cap", lead.id)
        return None
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            user = await client.resolve_phone(phone)
    except Exception as exc:
        logger.info("Telegram resolve failed for lead %s phone %s: %s", lead.id, phone, exc)
        return None
    import_log = AutomationActionLog(
        custom_automation_id=automation.id,
        social_account_id=account.id,
        action_type="contact_import",
        target_id=str(lead.id),
        target_type="lead",
        result="success",
        payload={"phone": phone},
        created_at=_utc_now(),
    )
    session.add(import_log)
    value = _telegram_value_from_user(user, phone)
    if not value or value == "unknown":
        import_log.result = "empty"
        return None

    duplicate = await find_existing_lead(
        session,
        automation.id,
        contact_type="telegram",
        contact_value=value,
        raw={"phone": phone, "resolved_telegram": value, "resolved_telegram_id": getattr(user, "id", None)},
        exclude_id=lead.id,
    )
    if duplicate:
        import_log.result = "duplicate"
        await mark_lead_duplicate(session, lead, duplicate, reason="resolved_to_existing_telegram")
        await session.commit()
        return None

    raw = dict(lead.dmp_raw_data or {})
    raw["resolved_telegram"] = value
    raw["resolved_telegram_id"] = getattr(user, "id", None)
    raw["resolved_telegram_username"] = getattr(user, "username", None)
    if phone:
        raw.setdefault("phone", phone)
    lead.dmp_raw_data = raw
    lead.contact_type = "telegram"
    lead.contact_value = value
    lead.updated_at = _utc_now()
    if not lead.assigned_account_id:
        lead.assigned_account_id = account.id
    return value


async def create_order(
    session: AsyncSession,
    automation_id: int,
    *,
    import_type: str,
    source_url: str | None,
    requested_count: int,
) -> DmpOneImport:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise RuntimeError("Automation not found")
    if not automation.is_dmp_one_enabled:
        raise ValueError("Модуль DMP.one выключен")
    if not settings.DMP_ONE_API_BASE_URL or not settings.DMP_ONE_API_KEY:
        raise RuntimeError("DMP.one is not configured (DMP_ONE_API_BASE_URL / DMP_ONE_API_KEY)")
    if import_type in {"website", "competitors"} and not (source_url or "").strip():
        raise ValueError("Укажите источник: сайт или URL")
    if requested_count < 1:
        raise ValueError("Количество должно быть больше нуля")

    if not automation.dmp_webhook_secret:
        ensure_dmp_webhook_secret(automation)
        await session.commit()

    payload = {
        "type": import_type,
        "source_url": source_url,
        "count": requested_count,
        "callback_url": _callback_url(automation),
    }
    try:
        async with _client() as client:
            response = await client.post("/orders", json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.exception("DMP.one order creation failed: %s", exc)
        raise RuntimeError(f"DMP.one order creation failed: {exc}") from exc

    if not isinstance(data, dict) or not data:
        raise RuntimeError("DMP.one returned an empty order response")

    external_order_id = str(data.get("order_id") or data.get("id") or "").strip()
    if not external_order_id:
        raise RuntimeError("DMP.one не вернул идентификатор заказа")
    status = str(data.get("status") or "pending").lower()
    cost = data.get("cost") or data.get("price") or data.get("cost_rub")
    estimated = data.get("estimated_count") or data.get("count") or requested_count

    dmp_import = DmpOneImport(
        custom_automation_id=automation_id,
        import_type=import_type,
        source_url=source_url,
        requested_count=requested_count,
        received_count=0,
        purchased_count=0,
        cost_rub=float(cost) if isinstance(cost, (int, float)) else None,
        cpl_rub=None,
        status=status if status in {"pending", "processing", "completed", "failed"} else "pending",
        raw_payload={
            "external_order_id": external_order_id,
            "order_response": data,
            "request_payload": payload,
        },
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(dmp_import)
    await session.commit()
    await session.refresh(dmp_import)
    return dmp_import


async def _fetch_order_results(external_order_id: str) -> dict[str, Any]:
    if not settings.DMP_ONE_API_BASE_URL:
        raise RuntimeError("DMP_ONE_API_BASE_URL is not configured")
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            async with _client() as client:
                response = await client.get(f"/orders/{external_order_id}")
                if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                    last_exc = RuntimeError(f"DMP.one HTTP {response.status_code}")
                    continue
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("DMP.one order payload is not an object")
            return data
        except RuntimeError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                continue
            raise
    raise RuntimeError(f"DMP.one order fetch failed: {last_exc}")


def _normalize_contact_record(data: dict) -> dict:
    """Collapse DMP.one field aliases (phone/site/page) into the keys the pipeline reads."""
    item = dict(data)
    phone = item.get("phone") or item.get("phone_number") or item.get("tel") or item.get("msisdn")
    if phone and not item.get("phone"):
        item["phone"] = phone
    website = item.get("website") or item.get("site") or item.get("domain")
    if website and not item.get("website"):
        item["website"] = website
    return item


def _as_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _lead_contact(data: dict) -> tuple[str, str]:
    data = _normalize_contact_record(data)
    phone = data.get("phone") or data.get("phone_number") or data.get("tel")
    telegram = data.get("telegram") or data.get("telegram_username") or data.get("tg")
    telegram_id = data.get("telegram_id") or data.get("tg_id")
    if telegram:
        return "telegram", str(telegram).lstrip("@")
    if telegram_id:
        return "telegram", str(telegram_id)
    if phone:
        normalized = normalize_telegram_phone(str(phone)) or str(phone).strip()
        return "phone", normalized
    return "unknown", "unknown"


def _normalize_webhook_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"contacts": [item for item in payload if isinstance(item, dict)], "type": "webhook"}
    if isinstance(payload, dict):
        return payload
    return {"contacts": []}


def _extract_leads_data(results: dict[str, Any]) -> list[dict[str, Any]]:
    leads_data = results.get("leads") or results.get("data") or results.get("contacts") or results.get("items") or []
    if isinstance(leads_data, dict):
        leads_data = [leads_data]
    if not isinstance(leads_data, list):
        leads_data = []
    if not leads_data and (results.get("phone") or results.get("phone_number") or results.get("telegram") or results.get("tel")):
        leads_data = [results]
    return [_normalize_contact_record(item) for item in leads_data if isinstance(item, dict)]


_VENDOR_OK = {"completed", "complete", "done", "success", "ready", "finished"}
_VENDOR_FAIL = {"failed", "error", "cancelled", "canceled", "rejected"}
_VENDOR_WAIT = {"pending", "processing", "in_progress", "new", "queued", "created"}


def _next_import_status(dmp_import: DmpOneImport, results: dict[str, Any], leads_data: list) -> str:
    vendor = str(results.get("status") or "").strip().lower()
    external_order_id = str((dmp_import.raw_payload or {}).get("external_order_id") or "").strip()
    if vendor in _VENDOR_FAIL:
        return "failed"
    if vendor in _VENDOR_OK:
        return "completed"
    if vendor in _VENDOR_WAIT and external_order_id:
        return "processing"
    if leads_data and not external_order_id:
        return "completed"
    if external_order_id and not leads_data:
        return "processing"
    if leads_data:
        return "completed"
    return "completed"


def _webhook_fingerprint(payload: dict[str, Any]) -> str:
    leads = _extract_leads_data(payload)
    parts: list[str] = []
    for item in leads:
        contact_type, contact_value = _lead_contact(item)
        parts.append(f"{contact_type}:{(contact_value or '').strip().lower()}")
    parts.sort()
    if parts:
        basis = "|".join(parts)
    else:
        basis = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)[:2000]
    return hashlib.sha256(basis.encode()).hexdigest()[:32]


async def _find_dmp_import(
    session: AsyncSession,
    automation_id: int,
    *,
    external_order_id: str = "",
    fingerprint: str = "",
) -> DmpOneImport | None:
    if external_order_id:
        try:
            bind = session.get_bind()
            dialect = bind.dialect.name
        except Exception:
            dialect = ""
        if dialect == "postgresql":
            found = await session.scalar(
                select(DmpOneImport).where(
                    DmpOneImport.custom_automation_id == automation_id,
                    DmpOneImport.raw_payload.contains({"external_order_id": external_order_id}),
                )
            )
            if found:
                return found
    if not external_order_id and not fingerprint:
        return None
    rows = (
        await session.scalars(
            select(DmpOneImport)
            .where(DmpOneImport.custom_automation_id == automation_id)
            .order_by(DmpOneImport.id.desc())
            .limit(500)
        )
    ).all()
    for row in rows:
        raw = row.raw_payload or {}
        if external_order_id and str(raw.get("external_order_id") or "") == external_order_id:
            return row
        if fingerprint and raw.get("webhook_fingerprint") == fingerprint:
            return row
    return None


def _fill_lead_gaps(lead: CustomLead, data: dict[str, Any]) -> None:
    changed = False
    raw = dict(lead.dmp_raw_data or {})
    for key, value in data.items():
        if value in (None, "", [], {}):
            continue
        if raw.get(key) in (None, "", [], {}):
            raw[key] = value
            changed = True
    if not (lead.full_name or "").strip():
        name = data.get("name") or data.get("full_name") or data.get("fio")
        if name:
            lead.full_name = str(name)[:255]
            changed = True
    if not (lead.company or "").strip():
        company = data.get("company") or data.get("organization") or data.get("org") or data.get("website")
        if company:
            lead.company = str(company)[:255]
            changed = True
    if not (lead.position or "").strip():
        position = data.get("position") or data.get("job") or data.get("page")
        if position:
            lead.position = str(position)[:255]
            changed = True
    if changed:
        lead.dmp_raw_data = raw
        lead.updated_at = _utc_now()


async def _send_outreach(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
    *,
    registered: str = "unknown",
) -> bool:
    if not settings.DMP_ONE_OUTREACH_ENABLED:
        return False
    if lead.contact_type != "telegram" or not lead.contact_value or lead.contact_value == "unknown":
        return False
    if lead.status in {LeadStatus.LOST.value, LeadStatus.SPAM.value, LeadStatus.CONVERTED.value}:
        return False

    canonical = await find_canonical_lead(session, automation.id, lead)
    if canonical.id != lead.id:
        await mark_lead_duplicate(session, lead, canonical, reason="duplicate_contact")
        await session.commit()
        return False

    existing_outgoing = await session.scalar(
        select(CustomLeadMessage.id).where(
            CustomLeadMessage.custom_lead_id == lead.id,
            CustomLeadMessage.direction == "outgoing",
        ).limit(1)
    )
    if existing_outgoing:
        return False

    from .chat_monitoring_module_service import leadgen_restrict_ids

    account = await select_account_for_action(
        session,
        automation,
        "dmp_outreach",
        thread_id=lead.id,
        restrict_account_ids=leadgen_restrict_ids(automation),
    )
    if not account or not account.session_file_path:
        return False

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False

    text = await _generate_outreach_message(
        session,
        automation,
        name=lead.full_name or "",
        company=lead.company or "",
        website=lead_website(lead),
        page=lead_page(lead),
        registered=registered,
    )
    if not text:
        return False

    try:
        async with TelegramAccountClient.for_account(account) as client:
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.send_message(lead.contact_value, text),
                action_type="dmp_outreach",
                target_id=f"lead:{lead.id}",
                target_type="lead",
                payload={"lead_id": lead.id, "contact_value": lead.contact_value, "text": text},
                automation_id=automation.id,
            )
    except Exception as exc:
        logger.warning("DMP outreach send failed for lead %s: %s", lead.id, exc)
        return False

    lead.assigned_account_id = account.id
    lead.last_message_at = _utc_now()
    lead.status = LeadStatus.WARMING.value
    lead.updated_at = _utc_now()

    msg = CustomLeadMessage(
        custom_lead_id=lead.id,
        social_account_id=account.id,
        direction="outgoing",
        text=text,
        sent_at=_utc_now(),
        created_at=_utc_now(),
    )
    session.add(msg)
    await session.commit()
    return True


async def process_dmp_lead(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    from .solution_templates import is_dmp_notify_pipeline, qualification_enabled

    if lead.status in {LeadStatus.LOST.value, LeadStatus.SPAM.value}:
        return {"lead_id": lead.id, "status": "skipped", "reason": lead.status}

    canonical = await find_canonical_lead(session, automation.id, lead)
    if canonical.id != lead.id:
        await mark_lead_duplicate(session, lead, canonical, reason="duplicate_contact")
        await session.commit()
        return {"lead_id": lead.id, "status": "duplicate", "canonical_lead_id": canonical.id}

    from .sasha_ai_service import lead_sasha_phone, maybe_send_lead_to_sasha, sasha_takes_over

    conversion = await check_lead_conversion(automation, lead)
    if conversion.get("subscribed"):
        lead.status = LeadStatus.CONVERTED.value
        lead.updated_at = _utc_now()
        lead.status_history = (lead.status_history or []) + [
            {"status": LeadStatus.CONVERTED.value, "changed_at": _utc_now().isoformat(), "reason": "conversion_check"}
        ]
        await session.commit()
        return {"lead_id": lead.id, "status": "converted", "reason": "already_subscribed"}

    # Phone leads go DMP → Sasha → back here → the same bot.
    # A contact without a callable number stays on the Telegram path.
    if sasha_takes_over(automation) and lead_sasha_phone(lead):
        sasha = await maybe_send_lead_to_sasha(session, automation, lead)
        return {"lead_id": lead.id, "status": "sasha", **(sasha or {})}

    if not qualification_enabled(automation):
        from .telegram_notify_bot_service import dispatch_dmp_notifications, dispatch_sales_bot_notification

        lead_id = lead.id
        if is_dmp_notify_pipeline(automation):
            dispatched = await dispatch_dmp_notifications(session, automation, lead)
        else:
            dispatched = await dispatch_sales_bot_notification(session, automation, lead)
        return {"lead_id": lead_id, "status": "transferred", **dispatched}

    registered = "yes" if conversion.get("registered") else "no" if conversion.get("registered") is False else "unknown"
    resolved = await resolve_telegram_for_lead(session, automation, lead)
    if not resolved and lead.contact_type != "telegram":
        await session.commit()
        return {"lead_id": lead.id, "status": "waiting_telegram"}

    sent = await _send_outreach(session, automation, lead, registered=registered)
    return {"lead_id": lead.id, "status": "warming" if sent else "new", "outreach": sent}


async def _create_leads_from_data(
    session: AsyncSession,
    automation_id: int,
    dmp_import: DmpOneImport,
    leads_data: list[dict],
) -> int:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return 0
    created = 0
    for data in leads_data:
        contact_type, contact_value = _lead_contact(data)
        if contact_type == "unknown" or not contact_value or contact_value == "unknown":
            continue
        existing = await find_existing_lead(
            session,
            automation_id,
            contact_type=contact_type,
            contact_value=contact_value,
            raw=data,
        )
        if existing:
            _fill_lead_gaps(existing, data)
            continue
        lead = CustomLead(
            custom_automation_id=automation_id,
            source="dmp_one",
            dmp_one_import_id=dmp_import.id,
            contact_type=contact_type,
            contact_value=contact_value,
            full_name=data.get("name") or data.get("full_name") or data.get("fio"),
            company=data.get("company") or data.get("organization") or data.get("org") or data.get("website"),
            position=data.get("position") or data.get("job") or data.get("page"),
            dmp_raw_data=data,
            status=LeadStatus.NEW.value,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(lead)
        await session.flush()
        await process_dmp_lead(session, automation, lead)
        created += 1

    return created


async def process_order_results(
    session: AsyncSession,
    automation_id: int,
    dmp_import: DmpOneImport,
    results: dict[str, Any],
) -> dict[str, Any]:
    leads_data = _extract_leads_data(results)
    received = _as_int(results.get("received_count") or results.get("count"), len(leads_data))
    purchased = _as_int(results.get("purchased_count") or results.get("bought_count"), len(leads_data))
    cost = results.get("cost") or results.get("cost_rub") or results.get("price")
    cost_rub = float(cost) if isinstance(cost, (int, float)) else dmp_import.cost_rub

    dmp_import.received_count = received
    dmp_import.purchased_count = purchased
    dmp_import.cost_rub = cost_rub
    if cost_rub and purchased:
        dmp_import.cpl_rub = round(cost_rub / purchased, 2)
    dmp_import.status = _next_import_status(dmp_import, results, leads_data)
    dmp_import.updated_at = _utc_now()
    dmp_import.raw_payload = {
        **(dmp_import.raw_payload or {}),
        "last_results": results,
    }
    await session.commit()

    created = await _create_leads_from_data(session, automation_id, dmp_import, leads_data)
    await session.commit()

    return {"created_leads": created, "received_count": received, "purchased_count": purchased}


async def handle_webhook(
    session: AsyncSession,
    automation_id: int,
    payload: Any,
) -> dict[str, Any]:
    payload = _normalize_webhook_payload(payload)
    order = payload.get("order")
    nested_order_id = order.get("id") if isinstance(order, dict) else None
    external_order_id = str(payload.get("order_id") or payload.get("id") or nested_order_id or "").strip()

    fingerprint = _webhook_fingerprint(payload)
    dmp_import = await _find_dmp_import(
        session,
        automation_id,
        external_order_id=external_order_id,
        fingerprint="" if external_order_id else fingerprint,
    )

    if not dmp_import:
        raw_payload = {"webhook_payload": payload, "webhook_fingerprint": fingerprint}
        if external_order_id:
            raw_payload["external_order_id"] = external_order_id
        dmp_import = DmpOneImport(
            custom_automation_id=automation_id,
            import_type=payload.get("type") or "webhook",
            source_url=payload.get("source_url"),
            requested_count=_as_int(payload.get("requested_count") or payload.get("count"), 0) or None,
            status="processing",
            raw_payload=raw_payload,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(dmp_import)
        await session.commit()
        await session.refresh(dmp_import)

    return await process_order_results(session, automation_id, dmp_import, payload)


async def poll_pending_imports(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker
    from ...alembic.models import CustomAutomation

    total_created = 0
    total_processed = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            logger.info("DMP.one automation not found for %s", automation_id)
            return {"imports_processed": 0, "leads_created": 0, "leads_retried": 0, "reason": "not_found"}

        orders_enabled = bool(automation.is_dmp_one_enabled)
        if orders_enabled:
            result = await session.execute(
                select(DmpOneImport).where(
                    DmpOneImport.custom_automation_id == automation_id,
                    DmpOneImport.status.in_({"pending", "processing"}),
                )
            )
            imports = result.scalars().all()
            for dmp_import in imports:
                external_order_id = (dmp_import.raw_payload or {}).get("external_order_id")
                if not external_order_id:
                    continue
                try:
                    data = await _fetch_order_results(external_order_id)
                    res = await process_order_results(session, automation_id, dmp_import, data)
                    total_created += res.get("created_leads", 0)
                    total_processed += 1
                except Exception as exc:
                    logger.warning("Polling DMP order %s failed: %s", external_order_id, exc)
        else:
            logger.info("DMP.one orders disabled for %s; retrying in-flight leads only", automation_id)

        retried = 0
        pending = await session.execute(
            select(CustomLead).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.source == "dmp_one",
                CustomLead.status == LeadStatus.NEW.value,
            ).limit(30)
        )
        for lead in pending.scalars().all():
            try:
                await process_dmp_lead(session, automation, lead)
                retried += 1
            except Exception as exc:
                logger.warning("Retry DMP outreach for lead %s failed: %s", lead.id, exc)

    return {
        "imports_processed": total_processed,
        "leads_created": total_created,
        "leads_retried": retried,
        "reason": None if orders_enabled else "orders_disabled",
    }
