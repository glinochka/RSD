"""Контекст sales-контакта (связь Excel-import ↔ FSM)."""

from __future__ import annotations

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AgentSalesImportedContact
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID


async def resolve_sales_source_chat_id(
    *,
    agent_id: int | None,
    user_external_id: str | None,
    default_source_chat_id: str,
) -> str:
    """Если пользователь из Excel-базы — используем отдельный ключ FSM."""
    if not agent_id or not (user_external_id or "").strip():
        return default_source_chat_id or "global"
    uid = user_external_id.strip()
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(AgentSalesImportedContact.id).where(
                    AgentSalesImportedContact.agent_id == agent_id,
                    AgentSalesImportedContact.target_external_id == uid,
                )
            )
    if row is not None:
        return EXCEL_IMPORT_SOURCE_CHAT_ID
    return default_source_chat_id or "global"
