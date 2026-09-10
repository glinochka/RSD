"""One claim per post: 30% chance to act, never twice in a row in the same channel."""
from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog


POST_ENGAGEMENT_ACTION = "post_engagement"
POST_ACTION_CHANCE = 0.30
POST_SHILL_CHANCE = 0.25

NEUROCOMMENTING = "neurocommenting"
SHILLING = "shilling"
SKIP = "skip"

ClaimResult = str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def post_target_id(chat_target_id: int, post_id: int) -> str:
    return f"{chat_target_id}:{post_id}"


def _post_id_from_target(chat_target_id: int, target_id: str | None) -> int | None:
    prefix = f"{chat_target_id}:"
    raw = str(target_id or "")
    if not raw.startswith(prefix):
        return None
    try:
        return int(raw[len(prefix):])
    except ValueError:
        return None


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


async def list_channel_post_claims(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
) -> list[tuple[int, AutomationActionLog]]:
    result = await session.execute(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == POST_ENGAGEMENT_ACTION,
        )
    )
    rows: list[tuple[int, AutomationActionLog]] = []
    for log in result.scalars().all():
        post_id = _post_id_from_target(chat_target_id, log.target_id)
        if post_id is None:
            continue
        rows.append((post_id, log))
    rows.sort(key=lambda item: item[0])
    return rows


def _pick_action(
    neuro_enabled: bool,
    shilling_enabled: bool,
    pick: Callable[[list[str]], str] | None,
    roll: Callable[[], float],
) -> str:
    options: list[str] = []
    if neuro_enabled:
        options.append(NEUROCOMMENTING)
    if shilling_enabled:
        options.append(SHILLING)
    if not options:
        return SKIP
    if len(options) == 1:
        return options[0]
    if pick is not None:
        return pick(options)
    return SHILLING if roll() < POST_SHILL_CHANCE else NEUROCOMMENTING


def _previous_was_action(older: list[tuple[int, AutomationActionLog]]) -> bool:
    if not older:
        return False
    return older[-1][1].result in {NEUROCOMMENTING, SHILLING}


def _decide_result(
    *,
    neuro_enabled: bool,
    shilling_enabled: bool,
    older: list[tuple[int, AutomationActionLog]],
    lab_mode: bool,
    activate_roll: Callable[[], float],
    pick: Callable[[list[str]], str] | None,
    type_roll: Callable[[], float],
) -> str:
    if not lab_mode and _previous_was_action(older):
        return SKIP
    if not lab_mode and activate_roll() >= POST_ACTION_CHANCE:
        return SKIP
    return _pick_action(neuro_enabled, shilling_enabled, pick, type_roll)


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
    pick_gap: Callable[[], int] | None = None,
    activate_roll: Callable[[], float] | None = None,
    lab_mode: bool = False,
) -> ClaimResult:
    """Decide once per post: skip / neurocommenting / shilling.

    Production: 30% chance to act, and never two actions in a row in the same channel.
    If both modules are on, shilling wins 25% of the time and a regular comment 75%.
    Lab mode always acts. Later callers reuse the first claim.
    """
    existing = await get_post_engagement_claim(session, automation_id, chat_target_id, post_id)
    if existing:
        return existing.result

    type_roller = roll or random.random
    chance_roller = activate_roll or random.random
    _ = pick_gap
    older = [
        item
        for item in await list_channel_post_claims(session, automation_id, chat_target_id)
        if item[0] < int(post_id)
    ]
    result = _decide_result(
        neuro_enabled=neuro_enabled,
        shilling_enabled=shilling_enabled,
        older=older,
        lab_mode=lab_mode,
        activate_roll=chance_roller,
        pick=pick,
        type_roll=type_roller,
    )

    payload: dict[str, Any] = {
        "chat_target_id": chat_target_id,
        "post_id": post_id,
        "neuro_enabled": neuro_enabled,
        "shilling_enabled": shilling_enabled,
        "lab_mode": lab_mode,
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
