"""One roll per post: skip most of them, and never mix neurocommenting with shilling."""
from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog


POST_ENGAGEMENT_ACTION = "post_engagement"
POST_ACTION_PROBABILITY = 0.20

NEUROCOMMENTING = "neurocommenting"
SHILLING = "shilling"
SKIP = "skip"

ClaimResult = str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def post_target_id(chat_target_id: int, post_id: int) -> str:
    return f"{chat_target_id}:{post_id}"


async def get_post_engagement_claim(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    post_id: int,
) -> AutomationActionLog | None:
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == POST_ENGAGEMENT_ACTION,
            AutomationActionLog.target_id == post_target_id(chat_target_id, post_id),
        )
        .order_by(AutomationActionLog.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _pick_action(neuro_enabled: bool, shilling_enabled: bool, pick: Callable[[list[str]], str]) -> str:
    options: list[str] = []
    if neuro_enabled:
        options.append(NEUROCOMMENTING)
    if shilling_enabled:
        options.append(SHILLING)
    if not options:
        return SKIP
    return pick(options)


async def claim_post_engagement(
    session: AsyncSession,
    *,
    automation_id: int,
    chat_target_id: int,
    post_id: int,
    account_id: int,
    neuro_enabled: bool,
    shilling_enabled: bool,
    roll: Callable[[], float] | None = None,
    pick: Callable[[list[str]], str] | None = None,
) -> ClaimResult:
    """Decide once per post: skip / neurocommenting / shilling.

    The 20% roll is shared. If both modules are on, exactly one of them wins.
    Later callers reuse the first claim (earliest id) if two workers race.
    """
    existing = await get_post_engagement_claim(session, automation_id, chat_target_id, post_id)
    if existing:
        return existing.result

    rand = roll or random.random
    chooser = pick or random.choice
    if rand() >= POST_ACTION_PROBABILITY:
        result = SKIP
    else:
        result = _pick_action(neuro_enabled, shilling_enabled, chooser)

    payload: dict[str, Any] = {
        "chat_target_id": chat_target_id,
        "post_id": post_id,
        "neuro_enabled": neuro_enabled,
        "shilling_enabled": shilling_enabled,
    }
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account_id,
            action_type=POST_ENGAGEMENT_ACTION,
            target_id=post_target_id(chat_target_id, post_id),
            target_type="chat_post",
            result=result,
            payload=payload,
            created_at=_utc_now(),
        )
    )
    await session.commit()

    winner = await get_post_engagement_claim(session, automation_id, chat_target_id, post_id)
    return winner.result if winner else result
