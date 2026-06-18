"""Учёт успешно отправленных каналов outreach ИИ МОП (для частичного retry)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AgentSalesDmQueue, AiMopLead

_OUTREACH_SENT_KEY = "outreach_sent_channels"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_extra(lead: AiMopLead) -> dict[str, Any]:
    raw = lead.extra_json
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_queue_meta(item: AgentSalesDmQueue) -> dict[str, Any]:
    if not item.metadata_json:
        return {}
    try:
        data = json.loads(item.metadata_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def channel_key(*, channel: str, target: str) -> str:
    return f"{channel.strip().lower()}:{target.strip()}"


def get_completed_outreach_channels(lead: AiMopLead) -> set[str]:
    extra = _parse_extra(lead)
    raw = extra.get(_OUTREACH_SENT_KEY)
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


async def record_outreach_channel_sent(
    *,
    lead_id: int,
    channel: str,
    target: str,
) -> None:
    key = channel_key(channel=channel, target=target)
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, lead_id)
            if lead is None:
                return
            extra = _parse_extra(lead)
            sent = get_completed_outreach_channels(lead)
            sent.add(key)
            extra[_OUTREACH_SENT_KEY] = sorted(sent)
            lead.extra_json = json.dumps(extra, ensure_ascii=False)
            lead.updated_at = _utc_now()


async def count_pending_ai_mop_dm_for_lead(*, lead_id: int) -> int:
    async with async_session_maker() as session:
        rows = (
            await session.scalars(
                select(AgentSalesDmQueue).where(
                    AgentSalesDmQueue.status == "pending",
                    AgentSalesDmQueue.source_chat_id == "ai_mop",
                )
            )
        ).all()
    return sum(
        1
        for row in rows
        if int(_parse_queue_meta(row).get("ai_mop_lead_id") or 0) == int(lead_id)
    )
