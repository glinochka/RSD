"""Хуки DM-очереди для обновления статусов лидов ИИ МОП."""

from __future__ import annotations

import json
import logging
from typing import Any

from ...alembic.models import AgentSalesDmQueue
from ..sales.fsm import SalesFSMService
from .lead_status import mark_lead_outreach_send_failed, mark_lead_outreach_sent
from .outreach import AI_MOP_SOURCE_CHAT_ID

logger = logging.getLogger(__name__)


def _parse_meta(item: AgentSalesDmQueue) -> dict[str, Any]:
    if not item.metadata_json:
        return {}
    try:
        data = json.loads(item.metadata_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


async def on_dm_queue_sent(item: AgentSalesDmQueue) -> None:
    meta = _parse_meta(item)
    lead_id = meta.get("ai_mop_lead_id")
    if lead_id is None:
        return
    try:
        await mark_lead_outreach_sent(lead_id=int(lead_id), agent_id=int(item.agent_id))
        fsm = SalesFSMService()
        try:
            await fsm.transition_contact(
                agent_id=item.agent_id,
                user_external_id=str(item.target_user_external_id),
                source_chat_id=AI_MOP_SOURCE_CHAT_ID,
                to_state="SENT",
                reason="ai_mop_first_message_sent",
            )
        except Exception:
            logger.debug("FSM SENT transition skipped ai_mop lead_id=%s", lead_id, exc_info=True)
    except Exception:
        logger.warning("Failed to mark AI MOP lead sent lead_id=%s", lead_id, exc_info=True)


async def on_dm_queue_failed(item: AgentSalesDmQueue, *, error: str, final: bool) -> None:
    if not final:
        return
    meta = _parse_meta(item)
    lead_id = meta.get("ai_mop_lead_id")
    if lead_id is None:
        return
    try:
        await mark_lead_outreach_send_failed(
            lead_id=int(lead_id),
            agent_id=int(item.agent_id),
            error=error,
        )
    except Exception:
        logger.warning("Failed to mark AI MOP lead send failed lead_id=%s", lead_id, exc_info=True)
