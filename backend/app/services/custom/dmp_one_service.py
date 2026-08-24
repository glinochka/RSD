"""DMP.one integration: create orders, receive webhooks/poll results, warm leads."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import CustomLead, CustomLeadMessage, CustomPrompt, DmpOneImport, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_DMP_OUTREACH_PROMPT = """Ты — менеджер компании. Ты пишешь первое сообщение в Telegram человеку, который посетил сайт или проявил интерес к услугам (SEO, маркетинг, сайт, автоматизация, CRM).
Сообщение должно быть коротким, дружелюбным, без навязчивых продаж и без ссылок.

Имя: {name}
Компания: {company}

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
    automation_id: int,
    *,
    name: str,
    company: str,
) -> str:
    prompt = (await _load_prompt(session, automation_id)).format(
        name=name or "",
        company=company or "",
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        return str(data.get("message") or "").strip()[:500]
    except Exception as exc:
        logger.warning("DMP outreach generation failed: %s", exc)
        return ""


def _callback_url(automation_id: int) -> str:
    base = settings.BASE_URL or ""
    if not base:
        return ""
    return f"{base.rstrip('/')}/api/custom/automations/{automation_id}/dmp/webhook"


async def create_order(
    session: AsyncSession,
    automation_id: int,
    *,
    import_type: str,
    source_url: str | None,
    requested_count: int,
) -> DmpOneImport:
    if not settings.DMP_ONE_API_BASE_URL or not settings.DMP_ONE_API_KEY:
        raise RuntimeError("DMP.one is not configured (DMP_ONE_API_BASE_URL / DMP_ONE_API_KEY)")

    payload = {
        "type": import_type,
        "source_url": source_url,
        "count": requested_count,
        "callback_url": _callback_url(automation_id),
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

    external_order_id = str(data.get("order_id") or data.get("id") or "")
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
    async with _client() as client:
        response = await client.get(f"/orders/{external_order_id}")
        response.raise_for_status()
        return response.json()


def _lead_contact(data: dict) -> tuple[str, str]:
    phone = data.get("phone") or data.get("phone_number") or data.get("tel")
    telegram = data.get("telegram") or data.get("telegram_username") or data.get("tg")
    telegram_id = data.get("telegram_id") or data.get("tg_id")
    if telegram:
        return "telegram", str(telegram).lstrip("@")
    if telegram_id:
        return "telegram", str(telegram_id)
    if phone:
        return "phone", str(phone)
    return "unknown", "unknown"


async def _send_outreach(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
) -> bool:
    if not settings.DMP_ONE_OUTREACH_ENABLED:
        return False
    if lead.contact_type != "telegram" or not lead.contact_value or lead.contact_value == "unknown":
        return False

    account = await select_account_for_action(session, automation_id, "dm", thread_id=lead.id)
    if not account or not account.session_file_path:
        return False

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False

    text = await _generate_outreach_message(
        session,
        automation_id,
        name=lead.full_name or "",
        company=lead.company or "",
    )
    if not text:
        return False

    try:
        async with TelegramAccountClient(str(session_path)) as client:
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.send_message(lead.contact_value, text),
                action_type="dmp_outreach",
                target_id=f"lead:{lead.id}",
                target_type="lead",
                payload={"lead_id": lead.id, "contact_value": lead.contact_value, "text": text},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("DMP outreach send failed for lead %s: %s", lead.id, exc)
        return False

    lead.assigned_account_id = account.id
    lead.last_message_at = _utc_now()
    lead.status = "warming"
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


async def _create_leads_from_data(
    session: AsyncSession,
    automation_id: int,
    dmp_import: DmpOneImport,
    leads_data: list[dict],
) -> int:
    created = 0
    for data in leads_data:
        contact_type, contact_value = _lead_contact(data)
        lead = CustomLead(
            custom_automation_id=automation_id,
            source="dmp_one",
            dmp_one_import_id=dmp_import.id,
            contact_type=contact_type,
            contact_value=contact_value,
            full_name=data.get("name") or data.get("full_name") or data.get("fio"),
            company=data.get("company") or data.get("organization") or data.get("org"),
            position=data.get("position") or data.get("job"),
            dmp_raw_data=data,
            status="new",
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(lead)
        await session.flush()

        if lead.contact_type == "telegram":
            await _send_outreach(session, automation_id, lead)
        created += 1

    return created


async def process_order_results(
    session: AsyncSession,
    automation_id: int,
    dmp_import: DmpOneImport,
    results: dict[str, Any],
) -> dict[str, Any]:
    leads_data = results.get("leads") or results.get("data") or results.get("contacts") or []
    if not isinstance(leads_data, list):
        leads_data = []

    received = int(results.get("received_count") or results.get("count") or len(leads_data))
    purchased = int(results.get("purchased_count") or results.get("bought_count") or len(leads_data))
    cost = results.get("cost") or results.get("cost_rub") or results.get("price")
    cost_rub = float(cost) if isinstance(cost, (int, float)) else dmp_import.cost_rub

    dmp_import.received_count = received
    dmp_import.purchased_count = purchased
    dmp_import.cost_rub = cost_rub
    if cost_rub and purchased:
        dmp_import.cpl_rub = round(cost_rub / purchased, 2)
    dmp_import.status = "completed" if leads_data else "processing"
    dmp_import.updated_at = _utc_now()
    dmp_import.raw_payload = {
        **(dmp_import.raw_payload or {}),
        "last_results": results,
    }
    await session.commit()

    created = await _create_leads_from_data(session, automation_id, dmp_import, leads_data)

    return {"created_leads": created, "received_count": received, "purchased_count": purchased}


async def handle_webhook(
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    external_order_id = str(
        payload.get("order_id")
        or payload.get("id")
        or (payload.get("order") or {}).get("id")
        or ""
    )

    dmp_import = None
    if external_order_id:
        dmp_import = await session.scalar(
            select(DmpOneImport).where(
                DmpOneImport.custom_automation_id == automation_id,
                DmpOneImport.raw_payload.contains({"external_order_id": external_order_id}),
            )
        )

    if not dmp_import:
        dmp_import = DmpOneImport(
            custom_automation_id=automation_id,
            import_type=payload.get("type") or "webhook",
            source_url=payload.get("source_url"),
            requested_count=payload.get("requested_count") or payload.get("count"),
            status="processing",
            raw_payload={"webhook_payload": payload},
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
        if not automation or not automation.is_dmp_one_enabled:
            logger.info("DMP.one disabled or automation not found for %s", automation_id)
            return {"imports_processed": 0, "leads_created": 0, "reason": "feature_disabled"}

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

    return {"imports_processed": total_processed, "leads_created": total_created}
