"""Per-task daily action quota.

Each Moscow day an account draws one number between the task's minimum and
maximum. That number is the ceiling for this task only. Delays, night hours,
per-chat limits and the farm-wide daily cap stay in force.
"""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import _daily_stable_frac, effective_daily_target_max
from .rotation_service import current_daily_messages_sent, moscow_day_start_utc_naive
from ...alembic.models import AutomationActionLog, CustomAutomation, SocialAccount

TASK_ACTION_TYPES: dict[str, tuple[str, ...]] = {
    "neurocommenting": ("neurocommenting",),
    "discussion": ("discussion",),
    "shilling": ("shilling_chat", "shilling_post"),
    "chat_monitoring": ("dm",),
    "chat_broadcast": ("chat_broadcast",),
    "dm_broadcast": ("dm_broadcast",),
    "masslooking": ("masslooking",),
    "masspriming": ("masspriming",),
    "parser": ("parser",),
}


def quota_bounds(cfg: Any, *, default_max: int, hi: int = 200) -> tuple[int, int] | None:
    """Inclusive (min, max). None means this task does not cap the account."""
    raw = cfg if isinstance(cfg, dict) else {}
    try:
        top = int(raw["max_per_account"]) if raw.get("max_per_account") not in (None, "") else int(default_max)
    except (TypeError, ValueError):
        top = int(default_max)
    top = max(0, min(hi, top))
    if top <= 0:
        return None
    try:
        if raw.get("min_per_account") in (None, ""):
            bottom = top
        else:
            bottom = int(raw["min_per_account"])
    except (TypeError, ValueError):
        bottom = top
    bottom = max(0, min(top, bottom))
    return bottom, top


def _task_salt(task_key: str) -> int:
    digest = hashlib.sha256(f"quota:{task_key}".encode()).hexdigest()
    return int(digest[:8], 16) % 100_000


def rolled_daily_actions(account_id: int, task_key: str, low: int, high: int) -> int:
    """Stable for one Moscow day. Inclusive on both ends. 0 is a quiet day."""
    lo = max(0, int(low))
    hi = max(lo, int(high))
    if hi == lo:
        return hi
    frac = _daily_stable_frac(int(account_id), _task_salt(task_key))
    span = hi - lo + 1
    return lo + min(span - 1, int(frac * span))


async def task_actions_today(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    action_types: tuple[str, ...],
) -> int:
    if not action_types:
        return 0
    started = moscow_day_start_utc_naive()
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type.in_(action_types),
            AutomationActionLog.result == "success",
            AutomationActionLog.created_at >= started,
        )
    )
    return int(count or 0)


async def account_blocked_for_task(
    session: AsyncSession,
    automation_id: int,
    account: SocialAccount | None,
    task_key: str,
    cfg: Any,
    *,
    default_max: int = 15,
    hi: int = 200,
    extra_done: int = 0,
) -> bool:
    """True when this account must not take another action in this task today."""
    if account is None:
        return True
    automation = await session.get(CustomAutomation, automation_id)
    farm = effective_daily_target_max(account, automation)
    if farm > 0 and current_daily_messages_sent(account) >= farm:
        return True
    bounds = quota_bounds(cfg, default_max=default_max, hi=hi)
    if bounds is None:
        return False
    limit = rolled_daily_actions(account.id, task_key, bounds[0], bounds[1])
    if limit <= 0:
        return True
    types = TASK_ACTION_TYPES.get(task_key, ())
    done = await task_actions_today(session, automation_id, account.id, types)
    return done + max(0, int(extra_done)) >= limit
