"""Continue Telegram dialogues with intercepted/DMP leads and auto-transfer them."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .amocrm_service import transfer_lead_to_amocrm
from .dmp_one_service import check_lead_conversion, resolve_telegram_for_lead
from .human_dm import is_ready_to_reply
from .lead_dedup import find_canonical_lead, mark_lead_duplicate
from .lead_delivery_service import deliver_lead_to_manager
from .prompt_service import render_prompt
from .solution_templates import uses_sales_handoff
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import CustomAutomation, CustomLead, CustomLeadMessage, CustomPrompt, LeadStatus, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

DEFAULT_QUALIFICATION_PROMPT = """Ты квалифицируешь лид в Telegram-переписке.

История переписки:
{history}

Последнее сообщение лида:
{last_incoming}

Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}

Верни ТОЛЬКО JSON:
{
  "qualified": true/false,
  "lost": true/false,
  "continue": true/false,
  "reply": "следующее короткое сообщение, если continue=true"
}

qualified=true, если человек проявил интерес и готов к следующему шагу.
lost=true, если отказ, спам или нет смысла продолжать.
continue=true, если нужно ещё одно короткое сообщение для прогрева.
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


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
            CustomPrompt.prompt_type == PromptType.LEAD_QUALIFICATION.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_QUALIFICATION_PROMPT


async def auto_transfer_lead(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
) -> dict[str, Any]:
    from .solution_templates import is_dmp_notify_pipeline

    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return {"transferred": False, "reason": "automation_not_found"}
    if is_dmp_notify_pipeline(automation):
        from .telegram_notify_bot_service import dispatch_dmp_notifications

        return await dispatch_dmp_notifications(session, automation, lead)
    if not uses_sales_handoff(automation):
        lead.status = LeadStatus.CONVERTED.value
        lead.updated_at = _utc_now()
        lead.status_history = (lead.status_history or []) + [
            {"status": LeadStatus.CONVERTED.value, "changed_at": _utc_now().isoformat(), "reason": "seo_closed"}
        ]
        await session.commit()
        return {"transferred": False, "converted": True, "reason": "seo_saas"}

    result: dict[str, Any] = {"transferred": False}
    if automation.is_amocrm_enabled:
        amo = await transfer_lead_to_amocrm(session, automation_id, lead)
        result.update(amo)
        result["amocrm"] = amo
    if (automation.lead_manager_contact or "").strip():
        delivery = await deliver_lead_to_manager(session, automation_id, lead)
        result["notified"] = bool(delivery.get("delivered"))
        result["notify"] = delivery
        if delivery.get("delivered"):
            result["transferred"] = True
            result["reason"] = delivery.get("reason") or delivery.get("channel")
    elif result.get("transferred"):
        result["reason"] = result.get("reason") or "amocrm"
    return result


async def _classify_dialogue(
    session: AsyncSession,
    automation: CustomAutomation,
    history: str,
    last_incoming: str,
) -> dict[str, Any]:
    prompt = render_prompt(
        await _load_prompt(session, automation.id),
        {
            "history": history or "",
            "last_incoming": last_incoming or "",
            "partner_utm_url": automation.partner_utm_url or "",
            "partner_promo_code": automation.partner_promo_code or "",
        },
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        data = _extract_json(response.choices[0].message.content or "")
        return {
            "qualified": bool(data.get("qualified")),
            "lost": bool(data.get("lost")),
            "continue": bool(data.get("continue", True)),
            "reply": str(data.get("reply") or "").strip()[:500],
        }
    except Exception as exc:
        logger.warning("Lead qualification LLM failed: %s", exc)
        return {"qualified": False, "lost": False, "continue": False, "reply": ""}


def _peer_from_lead(lead: CustomLead) -> str | int | None:
    value = (lead.contact_value or "").strip()
    if not value or value == "unknown":
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    return value.lstrip("@")


async def _history_text(session: AsyncSession, lead_id: int) -> str:
    result = await session.execute(
        select(CustomLeadMessage)
        .where(CustomLeadMessage.custom_lead_id == lead_id)
        .order_by(CustomLeadMessage.sent_at.asc())
        .limit(20)
    )
    lines = []
    for message in result.scalars().all():
        prefix = "Лид" if message.direction == "incoming" else "Мы"
        lines.append(f"{prefix}: {message.text}")
    return "\n".join(lines)


async def _process_lead(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    if lead.status in {LeadStatus.LOST.value, LeadStatus.SPAM.value}:
        return {"lead_id": lead.id, "status": "skipped", "reason": lead.status}

    canonical = await find_canonical_lead(session, automation.id, lead)
    if canonical.id != lead.id:
        await mark_lead_duplicate(session, lead, canonical, reason="duplicate_contact")
        await session.commit()
        return {"lead_id": lead.id, "status": "duplicate", "canonical_lead_id": canonical.id}

    conversion = await check_lead_conversion(automation, lead)
    if conversion.get("subscribed"):
        lead.status = LeadStatus.CONVERTED.value
        lead.updated_at = _utc_now()
        lead.status_history = (lead.status_history or []) + [
            {"status": LeadStatus.CONVERTED.value, "changed_at": _utc_now().isoformat(), "reason": "conversion_check"}
        ]
        await session.commit()
        return {"lead_id": lead.id, "status": "converted", "reason": "already_subscribed"}

    if lead.contact_type != "telegram":
        resolved = await resolve_telegram_for_lead(session, automation, lead)
        if not resolved:
            return {"lead_id": lead.id, "status": "waiting_telegram"}
        await session.commit()

    if lead.status == LeadStatus.QUALIFIED.value:
        transferred = await auto_transfer_lead(session, automation.id, lead)
        return {"lead_id": lead.id, **transferred}

    account = await session.get(SocialAccount, lead.assigned_account_id) if lead.assigned_account_id else None
    if not account or not account.session_file_path or account.is_banned or not account.is_active:
        return {"lead_id": lead.id, "status": "skipped", "reason": "no_account"}

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return {"lead_id": lead.id, "status": "skipped", "reason": "session_missing"}

    peer = _peer_from_lead(lead)
    if not peer:
        return {"lead_id": lead.id, "status": "skipped", "reason": "no_peer"}

    incoming: list[dict[str, Any]] = []
    last_tg_message: Any | None = None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.resolve_peer(peer)
            history = await client.get_messages(entity, limit=20)
            cutoff = lead.last_message_at
            for msg in reversed(list(history or [])):
                if not msg or not msg.text or getattr(msg, "out", False):
                    continue
                sent_at = msg.date.replace(tzinfo=None) if msg.date and msg.date.tzinfo else msg.date
                if cutoff and sent_at and sent_at <= cutoff:
                    continue
                incoming.append({
                    "text": msg.text,
                    "external_message_id": str(msg.id),
                    "sent_at": sent_at or _utc_now(),
                })
                last_tg_message = msg
    except Exception as exc:
        logger.warning("Fetch lead dialog %s failed: %s", lead.id, exc)
        return {"lead_id": lead.id, "status": "error", "reason": str(exc)[:200]}

    if not incoming:
        return {"lead_id": lead.id, "status": "idle"}

    if last_tg_message is not None:
        delay_key = f"lead:{lead.id}:{getattr(last_tg_message, 'id', incoming[-1]['external_message_id'])}"
        if not is_ready_to_reply(last_tg_message, delay_key):
            return {"lead_id": lead.id, "status": "waiting_delay"}

    last_text = ""
    for item in incoming:
        session.add(
            CustomLeadMessage(
                custom_lead_id=lead.id,
                direction="incoming",
                text=item["text"],
                external_message_id=item["external_message_id"],
                sent_at=item["sent_at"],
                created_at=_utc_now(),
            )
        )
        last_text = item["text"]
        lead.last_message_at = item["sent_at"]
    lead.status = LeadStatus.WARMING.value
    lead.updated_at = _utc_now()
    await session.commit()

    decision = await _classify_dialogue(
        session,
        automation,
        await _history_text(session, lead.id),
        last_text,
    )
    if decision["lost"]:
        lead.status = LeadStatus.LOST.value
        lead.updated_at = _utc_now()
        await session.commit()
        return {"lead_id": lead.id, "status": "lost"}

    if decision["qualified"] or not automation.lead_warmup_enabled:
        lead.status = LeadStatus.QUALIFIED.value
        lead.updated_at = _utc_now()
        await session.commit()
        transferred = await auto_transfer_lead(session, automation.id, lead)
        status = "converted" if transferred.get("converted") else ("transferred" if transferred.get("transferred") else "qualified")
        return {"lead_id": lead.id, "status": status, **transferred}

    reply = decision.get("reply") or ""
    if not reply or not decision["continue"]:
        return {"lead_id": lead.id, "status": "waiting"}

    read_max_id = None
    if last_tg_message is not None and getattr(last_tg_message, "id", None) is not None:
        read_max_id = int(last_tg_message.id)
    elif incoming:
        try:
            read_max_id = int(incoming[-1]["external_message_id"])
        except (TypeError, ValueError):
            read_max_id = None

    try:
        async with TelegramAccountClient.for_account(account) as client:
            async def _send():
                await client.human_reply(peer, reply, max_id=read_max_id)

            await execute_with_telegram_retry(
                session,
                account,
                _send,
                action_type="lead_warmup",
                target_id=f"lead:{lead.id}",
                target_type="lead",
                payload={"text": reply},
                automation_id=automation.id,
            )
    except Exception as exc:
        logger.warning("Warmup reply failed for lead %s: %s", lead.id, exc)
        return {"lead_id": lead.id, "status": "send_failed"}

    session.add(
        CustomLeadMessage(
            custom_lead_id=lead.id,
            social_account_id=account.id,
            direction="outgoing",
            text=reply,
            sent_at=_utc_now(),
            created_at=_utc_now(),
        )
    )
    lead.last_message_at = _utc_now()
    lead.updated_at = _utc_now()
    await session.commit()
    return {"lead_id": lead.id, "status": "replied"}


async def run_lead_warmup_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "not_found"}
        if not (automation.is_chat_monitoring_enabled or automation.is_dmp_one_enabled):
            return {"status": "skipped", "reason": "feature_disabled"}

        result = await session.execute(
            select(CustomLead).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.status.in_([LeadStatus.NEW.value, LeadStatus.WARMING.value, LeadStatus.QUALIFIED.value]),
            ).order_by(CustomLead.updated_at.asc()).limit(50)
        )
        leads = list(result.scalars().all())
        stats = {"processed": 0, "replied": 0, "transferred": 0, "lost": 0}
        for lead in leads:
            try:
                outcome = await _process_lead(session, automation, lead)
                stats["processed"] += 1
                status = outcome.get("status")
                if status == "replied":
                    stats["replied"] += 1
                elif outcome.get("transferred") or status == "transferred":
                    stats["transferred"] += 1
                elif status == "lost":
                    stats["lost"] += 1
            except Exception as exc:
                logger.exception("Lead warmup failed for %s: %s", lead.id, exc)
        return stats
