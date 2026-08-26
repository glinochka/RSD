"""One claim per post: skip most of them, and never mix neurocommenting with shilling."""
from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog


POST_ENGAGEMENT_ACTION = "post_engagement"
MIN_POST_GAP = 1
MAX_POST_GAP = 2

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


def _pick_action(neuro_enabled: bool, shilling_enabled: bool, pick: Callable[[list[str]], str]) -> str:
    options: list[str] = []
    if neuro_enabled:
        options.append(NEUROCOMMENTING)
    if shilling_enabled:
        options.append(SHILLING)
    if not options:
        return SKIP
    return pick(options)


def _cadence_required_skips(
    older: list[tuple[int, AutomationActionLog]],
    pick_gap: Callable[[], int],
) -> tuple[int, int, bool]:
    consecutive_skips = 0
    last_action: AutomationActionLog | None = None
    for _post_id, log in reversed(older):
        if log.result == SKIP:
            consecutive_skips += 1
            continue
        last_action = log
        break
    if last_action:
        payload = last_action.payload or {}
        try:
            required = int(payload.get("next_skip"))
        except (TypeError, ValueError):
            required = pick_gap()
        required = max(MIN_POST_GAP, min(MAX_POST_GAP, required))
        return consecutive_skips, required, False
    required = None
    for _post_id, log in older:
        payload = log.payload or {}
        if payload.get("next_skip") is None:
            continue
        try:
            required = int(payload.get("next_skip"))
            break
        except (TypeError, ValueError):
            continue
    if required is None:
        required = pick_gap()
        return consecutive_skips, max(MIN_POST_GAP, min(MAX_POST_GAP, required)), True
    return consecutive_skips, max(MIN_POST_GAP, min(MAX_POST_GAP, required)), False


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
) -> ClaimResult:
    """Decide once per post: skip / neurocommenting / shilling.

    Cadence is 1 action per 2–3 posts on a channel (skip 1 or 2 after each action).
    If both modules are on, exactly one of them wins. Later callers reuse the first claim.
    `roll` is ignored; kept so older tests can still pass it.
    """
    del roll
    existing = await get_post_engagement_claim(session, automation_id, chat_target_id, post_id)
    if existing:
        return existing.result

    chooser = pick or random.choice
    gap = pick_gap or (lambda: random.randint(MIN_POST_GAP, MAX_POST_GAP))
    older = [
        item
        for item in await list_channel_post_claims(session, automation_id, chat_target_id)
        if item[0] < int(post_id)
    ]
    consecutive_skips, required, persist_initial_gap = _cadence_required_skips(older, gap)
    if consecutive_skips < required:
        result = SKIP
        next_skip = required if persist_initial_gap else None
    else:
        result = _pick_action(neuro_enabled, shilling_enabled, chooser)
        next_skip = gap() if result != SKIP else None

    payload: dict[str, Any] = {
        "chat_target_id": chat_target_id,
        "post_id": post_id,
        "neuro_enabled": neuro_enabled,
        "shilling_enabled": shilling_enabled,
    }
    if next_skip is not None:
        payload["next_skip"] = next_skip
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
