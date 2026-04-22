"""FSM lifecycle manager for sales contacts."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AgentSalesContact


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DISCOVERED": {"QUALIFIED", "SKIPPED"},
    "QUALIFIED": {"QUEUED", "SKIPPED"},
    "QUEUED": {"SENT", "SKIPPED"},
    "SENT": {"REPLIED_POSITIVE", "REPLIED_NEGATIVE", "NO_REPLY"},
    "REPLIED_POSITIVE": {"HANDOFF_CRM"},
    "REPLIED_NEGATIVE": set(),
    "NO_REPLY": set(),
    "HANDOFF_CRM": set(),
    "SKIPPED": set(),
}


class SalesFSMError(RuntimeError):
    pass


class SalesFSMService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _can_transition(current: str, new_state: str) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        return new_state in allowed

    async def get_or_create_contact(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
    ) -> AgentSalesContact:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(AgentSalesContact).where(
                        AgentSalesContact.agent_id == agent_id,
                        AgentSalesContact.user_external_id == user_external_id,
                        AgentSalesContact.source_chat_id == source_chat_id,
                    )
                )
                if row is not None:
                    return row
                row = AgentSalesContact(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=source_chat_id,
                    state="DISCOVERED",
                    created_at=self._now(),
                    updated_at=self._now(),
                    version=1,
                )
                session.add(row)
                await session.flush()
                return row

    async def transition_contact(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
        to_state: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_contacted_at: datetime | None = None,
        cooldown_until: datetime | None = None,
    ) -> AgentSalesContact:
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(
                    select(AgentSalesContact)
                    .where(
                        AgentSalesContact.agent_id == agent_id,
                        AgentSalesContact.user_external_id == user_external_id,
                        AgentSalesContact.source_chat_id == source_chat_id,
                    )
                    .with_for_update()
                )
                if row is None:
                    row = AgentSalesContact(
                        agent_id=agent_id,
                        user_external_id=user_external_id,
                        source_chat_id=source_chat_id,
                        state="DISCOVERED",
                        created_at=self._now(),
                        updated_at=self._now(),
                        version=1,
                    )
                    session.add(row)
                    await session.flush()

                current_state = (row.state or "DISCOVERED").strip().upper()
                next_state = (to_state or "").strip().upper()
                if not self._can_transition(current_state, next_state):
                    raise SalesFSMError(f"Illegal transition: {current_state} -> {next_state}")

                row.state = next_state
                row.last_reason = (reason or "").strip()[:128] or None
                row.last_contacted_at = last_contacted_at
                row.cooldown_until = cooldown_until
                row.metadata_json = json.dumps(metadata or {}, ensure_ascii=False) if metadata is not None else row.metadata_json
                row.version = int(row.version or 1) + 1
                row.updated_at = self._now()
                await session.flush()
                return row


_sales_fsm_service: SalesFSMService | None = None


def get_sales_fsm_service() -> SalesFSMService:
    global _sales_fsm_service
    if _sales_fsm_service is None:
        _sales_fsm_service = SalesFSMService()
    return _sales_fsm_service

