"""
Resolve `Agent` rows by external lookup id (Telegram bot_id, legacy pk, etc.).

`agents.id` is INTEGER (int32). Telegram `bot_id` and some Meta numeric ids can exceed
2**31 - 1. Comparing those values to `Agent.id` in SQL causes asyncpg overflow errors.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, or_

from ..alembic.models import Agent

# Same limit as `router_documents` / `_find_agent_by_lookup_id`.
MAX_INT32 = 2_147_483_647


def agent_by_lookup_id_filter(lookup_id: int) -> ColumnElement[bool]:
    """
    Boolean SQL expression: agent matches `lookup_id` by `bot_id` or, if in int32 range, by pk.

    Use for Telegram bot webhooks, userbots, WhatsApp userbot (same resolved bot_id), and
    any future channel that reuses Telegram `bot_id` as the public agent key.
    """
    if 0 < lookup_id <= MAX_INT32:
        return or_(Agent.bot_id == lookup_id, Agent.id == lookup_id)
    return Agent.bot_id == lookup_id
