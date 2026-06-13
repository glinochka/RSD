"""Пул контактов ИИ МОП: кого агент может обрабатывать в личке."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import AgentSalesContact, AgentSalesImportedContact
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .fsm import get_sales_fsm_service

_PHONE_DIGITS_RE = re.compile(r"\D+")
_POOL_OUTBOUND_STATES = frozenset(
    {
        "QUALIFIED",
        "QUEUED",
        "SENT",
        "REPLIED_POSITIVE",
        "REPLIED_NEGATIVE",
        "NO_REPLY",
        "HANDOFF_CRM",
    }
)
_RESERVED_SOURCE_CHAT_IDS = frozenset({"global", EXCEL_IMPORT_SOURCE_CHAT_ID})


def _digits_only(value: str | None) -> str:
    return _PHONE_DIGITS_RE.sub("", value or "")


def external_id_lookup_variants(user_external_id: str) -> list[str]:
    """Варианты идентификатора для сопоставления с Excel/ручной базой."""
    raw = (user_external_id or "").strip()
    if not raw:
        return []
    variants: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        key = value.strip()
        if not key:
            return
        folded = key.casefold()
        if folded in seen:
            return
        seen.add(folded)
        variants.append(key)

    _add(raw)
    if raw.startswith("+"):
        _add(raw[1:])
    digits = _digits_only(raw)
    if digits:
        _add(digits)
        if len(digits) == 11 and digits.startswith("8"):
            _add("7" + digits[1:])
            _add(f"+7{digits[1:]}")
        elif len(digits) == 11 and digits.startswith("7"):
            _add(f"+{digits}")
        elif len(digits) == 10 and digits.startswith("9"):
            _add("7" + digits)
            _add(f"+7{digits}")
    if "@" in raw:
        local = raw.split("@", 1)[0].strip()
        if local:
            _add(local)
    else:
        _add(raw.lstrip("@"))
    return variants


def _parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def contact_row_in_pool(row: AgentSalesContact) -> bool:
    metadata = _parse_metadata(row.metadata_json)
    if metadata.get("in_contact_pool") is True:
        return True
    source_chat_id = (row.source_chat_id or "").strip()
    if source_chat_id and source_chat_id not in _RESERVED_SOURCE_CHAT_IDS:
        return True
    state = (row.state or "DISCOVERED").strip().upper()
    return state in _POOL_OUTBOUND_STATES


async def _imported_contact_exists(
    session: AsyncSession,
    *,
    agent_id: int,
    user_external_id: str,
) -> bool:
    variants = external_id_lookup_variants(user_external_id)
    if not variants:
        return False
    row = await session.scalar(
        select(AgentSalesImportedContact.id)
        .where(
            AgentSalesImportedContact.agent_id == agent_id,
            AgentSalesImportedContact.target_external_id.in_(variants),
        )
        .limit(1)
    )
    return row is not None


async def user_in_agent_contact_pool(
    session: AsyncSession,
    *,
    agent_id: int,
    user_external_id: str,
) -> bool:
    """Контакт в пуле: Excel/ручная база, лидогенерация или уже ведётся диалог."""
    uid = (user_external_id or "").strip()
    if not uid:
        return False
    if await _imported_contact_exists(session, agent_id=agent_id, user_external_id=uid):
        return True
    variants = external_id_lookup_variants(uid)
    rows = (
        await session.scalars(
            select(AgentSalesContact).where(
                AgentSalesContact.agent_id == agent_id,
                AgentSalesContact.user_external_id.in_(variants),
            )
        )
    ).all()
    return any(contact_row_in_pool(row) for row in rows)


async def is_user_in_agent_contact_pool(
    *,
    agent_id: int,
    user_external_id: str,
) -> bool:
    async with async_session_maker() as session:
        async with session.begin():
            return await user_in_agent_contact_pool(
                session,
                agent_id=agent_id,
                user_external_id=user_external_id,
            )


async def register_user_in_agent_contact_pool(
    *,
    agent_id: int,
    user_external_id: str,
    source_chat_id: str,
    origin: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Пометить контакт как разрешённый для обработки (лидоген, outreach и т.д.)."""
    uid = (user_external_id or "").strip()
    if not uid:
        return
    chat_id = (source_chat_id or "global").strip() or "global"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fsm = get_sales_fsm_service()
    row = await fsm.get_or_create_contact(
        agent_id=agent_id,
        user_external_id=uid,
        source_chat_id=chat_id,
    )
    metadata = _parse_metadata(row.metadata_json)
    metadata["in_contact_pool"] = True
    metadata["pool_origin"] = (origin or "unknown").strip()[:64]
    metadata["pool_registered_at"] = now.isoformat()
    if extra:
        metadata["pool_extra"] = extra
    async with async_session_maker() as session:
        async with session.begin():
            locked = await session.scalar(
                select(AgentSalesContact)
                .where(
                    AgentSalesContact.id == row.id,
                )
                .with_for_update()
            )
            if locked is None:
                return
            locked.metadata_json = json.dumps(metadata, ensure_ascii=False)
            locked.updated_at = now
            locked.version = int(locked.version or 1) + 1
            await session.flush()
