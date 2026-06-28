"""Планирование холодного outreach по импортированной Excel-базе sales_manager."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentSalesImportedContact
from ...utils.agent_template_config import parse_agent_template_config
from ..template_runtime import TemplateRuntimeService
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .dm_queue_service import get_dm_queue_service
from .fsm import SalesFSMService
from .outreach_scheduling import next_stagger_delay_minutes, schedule_after_stagger
from .sales_playbook import EXCEL_COLD_OUTREACH_EXTRA

logger = logging.getLogger(__name__)

# За один запуск фона — не более N LLM-композиций (остальное — повторная загрузка / следующий батч).
DEFAULT_OUTREACH_BATCH_LIMIT = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cold_outreach_user_message(row: AgentSalesImportedContact) -> str:
    parts = [f"Компания: {row.org_name}"]
    if row.lpr_name:
        parts.append(f"ЛПР: {row.lpr_name}")
    if row.lpr_phone:
        parts.append(f"Телефон ЛПР: {row.lpr_phone}")
    if row.telegram:
        parts.append(f"Telegram: {row.telegram}")
    if row.whatsapp:
        parts.append(f"WhatsApp: {row.whatsapp}")
    parts.append(EXCEL_COLD_OUTREACH_EXTRA)
    return "\n".join(parts)


async def schedule_outreach_for_import_batch(
    *,
    agent_id: int,
    import_batch_id: str,
    limit: int = DEFAULT_OUTREACH_BATCH_LIMIT,
) -> dict[str, Any]:
    """Сгенерировать тексты и поставить в очередь DM для pending контактов батча."""
    runtime = TemplateRuntimeService()
    fsm = SalesFSMService()
    queue = get_dm_queue_service()
    queued = 0
    skipped = 0
    failed = 0

    async with async_session_maker() as session:
        async with session.begin():
            agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
            if agent is None or agent.template_type != "sales_manager":
                return {"error": "Agent not found or not sales_manager", "queued": 0}

            if not agent.is_active:
                return {"error": "Агент выключен", "queued": 0}

            template_config = parse_agent_template_config(agent.template_config)
            knowledge_scope_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
            system_prompt = str(agent.system_prompt or "").strip()

            rows = (
                await session.execute(
                    select(AgentSalesImportedContact)
                    .where(
                        AgentSalesImportedContact.agent_id == agent_id,
                        AgentSalesImportedContact.import_batch_id == import_batch_id,
                        AgentSalesImportedContact.outreach_status == "pending",
                    )
                    .order_by(AgentSalesImportedContact.id)
                    .limit(max(1, min(limit, 500)))
                )
            ).scalars().all()

    qualification = {
        "decision": "engage",
        "intent": "target_warm",
        "confidence": 1.0,
        "reason": "excel_import_cold_outreach",
        "lead_temperature": "warm",
        "stage_hint": "discovery",
        "handoff_ready": False,
        "workflow_outcome": "continue",
        "lead_heat_score": 60 if int(template_config.get("lead_score_scale") or 100) == 100 else 6.0,
        "resilience_score": 50 if int(template_config.get("lead_score_scale") or 100) == 100 else 5.0,
        "engagement_score": 40 if int(template_config.get("lead_score_scale") or 100) == 100 else 4.0,
    }

    cumulative_stagger_minutes = 0.0
    for row in rows:
        cumulative_stagger_minutes += next_stagger_delay_minutes()
        scheduled_for = schedule_after_stagger(cumulative_minutes=cumulative_stagger_minutes)
        try:
            context_list, _sources = await runtime.retrieve_offer_context(
                user_message=_cold_outreach_user_message(row),
                knowledge_scope_id=knowledge_scope_id,
                enable_smart_search=runtime._is_smart_search_enabled(template_config),
            )
            message_text = await runtime.compose_dm(
                prompt=system_prompt,
                user_message=_cold_outreach_user_message(row),
                qualification=qualification,
                context_list=context_list,
                template_config=template_config,
                current_sales_state="DISCOVERED",
                recent_history=[],
                interaction_hint="cold_outreach",
                runtime_context={"user_display_name": str(row.org_name or "").strip() or None},
            )
            if not message_text.strip():
                raise RuntimeError("Пустой текст сообщения")

            hint: dict[str, Any] | None = None
            if row.target_resolve_hint:
                try:
                    parsed = json.loads(row.target_resolve_hint)
                    if isinstance(parsed, dict):
                        hint = parsed
                except json.JSONDecodeError:
                    hint = None
            from .contact_target_resolver import attach_target_hint_to_dm_meta

            meta: dict[str, Any] = attach_target_hint_to_dm_meta(
                {
                    "channel": row.channel,
                    "import_batch_id": import_batch_id,
                    "imported_contact_id": row.id,
                    "org_name": row.org_name,
                    "source": "excel_import",
                },
                hint,
            )

            await queue.enqueue_dm(
                agent_id=agent_id,
                target_user_external_id=row.target_external_id,
                source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
                message_text=message_text.strip(),
                scheduled_for=scheduled_for,
                metadata=meta,
            )

            await fsm.get_or_create_contact(
                agent_id=agent_id,
                user_external_id=row.target_external_id,
                source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
            )
            try:
                await fsm.transition_contact(
                    agent_id=agent_id,
                    user_external_id=row.target_external_id,
                    source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
                    to_state="QUALIFIED",
                    reason="excel_import_outreach",
                )
                await fsm.transition_contact(
                    agent_id=agent_id,
                    user_external_id=row.target_external_id,
                    source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
                    to_state="QUEUED",
                    reason="excel_import_outreach",
                )
            except Exception:
                logger.debug("FSM transition skipped for excel import contact_id=%s", row.id, exc_info=True)

            async with async_session_maker() as session:
                async with session.begin():
                    await session.execute(
                        update(AgentSalesImportedContact)
                        .where(AgentSalesImportedContact.id == row.id)
                        .values(
                            outreach_status="queued",
                            queued_at=_utc_now(),
                            updated_at=_utc_now(),
                            last_error=None,
                        )
                    )
            queued += 1
        except Exception as exc:
            logger.warning(
                "excel outreach failed agent_id=%s contact_id=%s: %s",
                agent_id,
                row.id,
                exc,
            )
            failed += 1
            async with async_session_maker() as session:
                async with session.begin():
                    await session.execute(
                        update(AgentSalesImportedContact)
                        .where(AgentSalesImportedContact.id == row.id)
                        .values(
                            outreach_status="failed",
                            last_error=str(exc)[:500],
                            updated_at=_utc_now(),
                        )
                    )

    return {
        "import_batch_id": import_batch_id,
        "queued": queued,
        "failed": failed,
        "skipped": skipped,
    }


async def mark_import_contact_sent(*, imported_contact_id: int) -> None:
    from .sales_followup_service import enqueue_follow_up_reminders

    now = _utc_now()
    channel = "telegram_userbot"
    agent_id = 0
    target = ""
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(AgentSalesImportedContact).where(AgentSalesImportedContact.id == imported_contact_id)
            )
            if row is None:
                return
            channel = row.channel
            agent_id = int(row.agent_id)
            target = row.target_external_id
            await session.execute(
                update(AgentSalesImportedContact)
                .where(AgentSalesImportedContact.id == imported_contact_id)
                .values(outreach_status="sent", sent_at=now, updated_at=now)
            )

    if agent_id and target:
        try:
            await enqueue_follow_up_reminders(
                agent_id=agent_id,
                imported_contact_id=imported_contact_id,
                target_user_external_id=target,
                channel=channel,
                first_sent_at=now,
            )
        except Exception:
            logger.warning(
                "Failed to enqueue follow-ups imported_contact_id=%s",
                imported_contact_id,
                exc_info=True,
            )
