"""Idle browsing humanization: accounts randomly skim Telegram dialogs.

Uses the HUMANIZATION rest queue (next_humanization_at) so idle browsing
never blocks target actions and never competes with warmup/peer_dialog slots.
"""
from __future__ import annotations

import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomAutomation, PoolAccount, SocialAccount
from .account_pacing import account_humanization_should_idle, schedule_account_humanization_rest
from .human_dm import random_idle_browse
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    from typing import Any
    from datetime import datetime, timezone

    browsed = 0
    errors = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "automation_not_found"}

        rows = await _eligible_accounts(session, automation_id)
        if not rows:
            return {"browsed": 0, "errors": 0}

        # Pick a few random accounts per pass; don't browse every account every tick
        sample = rows if len(rows) <= 3 else random.sample(rows, 3)
        for pool_account, social in sample:
            try:
                async with TelegramAccountClient.for_account(social) as client:
                    await random_idle_browse(client, lab_mode=False)
                browsed += 1
                record_successful_humanization(social)
                schedule_account_humanization_rest(social)
                await session.commit()
            except Exception as exc:
                errors += 1
                logger.warning("Idle browse failed for account %s: %s", social.id, exc)
                try:
                    await session.rollback()
                except Exception:
                    pass
    return {"browsed": browsed, "errors": errors}
