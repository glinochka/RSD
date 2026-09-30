"""Idle browsing humanization: one connected session of mixed read-activity.

Uses the HUMANIZATION rest queue (next_humanization_at) so this never blocks
target actions. One account per tick — the session itself is minutes, not a
connect/disconnect flash.
"""
from __future__ import annotations

import logging
import random
from typing import Any

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import AutomationActionLog, CustomAutomation, PoolAccount, SocialAccount
from .account_pacing import account_humanization_should_idle, moscow_now, schedule_account_humanization_rest
from .humanization_session import (
    COMMENT_CONTACT_ACTION,
    comment_contact_policy,
    run_humanization_session,
)
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient

logger = logging.getLogger(__name__)

ACCOUNTS_PER_PASS = 1


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


async def load_comment_contact_policy(session: AsyncSession, account: SocialAccount):
    result = await session.execute(
        select(AutomationActionLog).where(
            AutomationActionLog.social_account_id == account.id,
            AutomationActionLog.action_type == COMMENT_CONTACT_ACTION,
        )
    )
    logs = list(result.scalars().all())
    successes = [item for item in logs if item.result == "success"]
    known: set[int] = set()
    for item in successes:
        try:
            uid = int(item.target_id or 0)
        except (TypeError, ValueError):
            uid = 0
        if uid:
            known.add(uid)
    last = max((_naive(item.created_at) for item in successes if item.created_at), default=None)
    today = moscow_now().date()
    attempted_today = any(moscow_now(_naive(item.created_at)).date() == today for item in logs if item.created_at)
    policy = comment_contact_policy(
        account,
        added_count=len(successes),
        last_success_at=last,
        attempted_today=attempted_today,
    )
    policy.known_ids = known
    return policy


async def _eligible_accounts(session: AsyncSession, automation_id: int) -> list[tuple[PoolAccount, SocialAccount]]:
    result = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
            SocialAccount.session_file_path.isnot(None),
        )
    )
    return [
        (pool_account, social)
        for pool_account, social in result.all()
        if not account_humanization_should_idle(social)
    ]


async def run_idle_browse_pass(automation_id: int) -> dict[str, Any]:
    browsed = 0
    errors = 0
    sessions: list[dict[str, Any]] = []
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "automation_not_found"}

        rows = await _eligible_accounts(session, automation_id)
        if not rows:
            return {"browsed": 0, "errors": 0}

        sample = rows if len(rows) <= ACCOUNTS_PER_PASS else random.sample(rows, ACCOUNTS_PER_PASS)
        for pool_account, social in sample:
            try:
                policy = await load_comment_contact_policy(session, social)
                async with TelegramAccountClient.for_account(social) as client:
                    outcome = await run_humanization_session(
                        client, social, lab_mode=False, contact_policy=policy
                    )
                contact = outcome.get("comment_contact")
                if isinstance(contact, dict) and contact.get("status"):
                    session.add(
                        AutomationActionLog(
                            custom_automation_id=automation_id,
                            social_account_id=social.id,
                            action_type=COMMENT_CONTACT_ACTION,
                            target_id=str(contact.get("user_id") or ""),
                            target_type="user",
                            result=str(contact.get("status") or "empty")[:32],
                            payload={
                                "username": contact.get("username"),
                                "reason": policy.reason,
                                "added": policy.added,
                                "cap": policy.cap,
                            },
                            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        )
                    )
                browsed += 1
                sessions.append({"account_id": social.id, **outcome})
                record_successful_humanization(social)
                schedule_account_humanization_rest(social)
                await session.commit()
            except Exception as exc:
                errors += 1
                logger.warning("Humanization session failed for account %s: %s", social.id, exc)
                try:
                    await session.rollback()
                except Exception:
                    pass
    return {"browsed": browsed, "errors": errors, "sessions": sessions}
