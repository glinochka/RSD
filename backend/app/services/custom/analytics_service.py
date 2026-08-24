"""Analytics aggregation for /custom dashboards."""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AccountClass,
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    CustomLead,
    DmpOneImport,
    PoolAccount,
    SocialAccount,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _account_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    total = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(PoolAccount.custom_automation_id == automation_id)
    )
    active = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
    )
    banned = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_banned.is_(True),
        )
    )

    class_counts = {}
    for cls in AccountClass:
        count = await session.scalar(
            select(func.count(SocialAccount.id)).join(
                PoolAccount, PoolAccount.social_account_id == SocialAccount.id
            ).where(
                PoolAccount.custom_automation_id == automation_id,
                SocialAccount.account_class == cls.value,
            )
        )
        class_counts[cls.value] = count or 0

    return {
        "total": total or 0,
        "active": active or 0,
        "banned": banned or 0,
        "by_class": class_counts,
    }


async def _lead_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    total = await session.scalar(
        select(func.count(CustomLead.id)).where(CustomLead.custom_automation_id == automation_id)
    )

    status_counts = {}
    result = await session.execute(
        select(CustomLead.status, func.count(CustomLead.id)).where(
            CustomLead.custom_automation_id == automation_id
        ).group_by(CustomLead.status)
    )
    for status, count in result.all():
        status_counts[status] = count

    source_counts = {}
    result = await session.execute(
        select(CustomLead.source, func.count(CustomLead.id)).where(
            CustomLead.custom_automation_id == automation_id
        ).group_by(CustomLead.source)
    )
    for source, count in result.all():
        source_counts[source] = count

    recent = await session.execute(
        select(CustomLead).where(CustomLead.custom_automation_id == automation_id).order_by(
            CustomLead.created_at.desc()
        ).limit(10)
    )

    return {
        "total": total or 0,
        "by_status": status_counts,
        "by_source": source_counts,
        "recent": [row for row in recent.scalars().all()],
    }


async def _dmp_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    requested = await session.scalar(
        select(func.sum(DmpOneImport.requested_count)).where(
            DmpOneImport.custom_automation_id == automation_id
        )
    )
    received = await session.scalar(
        select(func.sum(DmpOneImport.received_count)).where(
            DmpOneImport.custom_automation_id == automation_id
        )
    )
    purchased = await session.scalar(
        select(func.sum(DmpOneImport.purchased_count)).where(
            DmpOneImport.custom_automation_id == automation_id
        )
    )
    cost = await session.scalar(
        select(func.sum(DmpOneImport.cost_rub)).where(
            DmpOneImport.custom_automation_id == automation_id
        )
    )
    cpl = None
    if purchased:
        cpl = round((cost or 0) / purchased, 2)

    return {
        "requested": int(requested or 0),
        "received": int(received or 0),
        "purchased": int(purchased or 0),
        "cost_rub": round(cost or 0, 2),
        "cpl_rub": cpl,
    }


async def _action_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    since_24h = _utc_now() - timedelta(hours=24)
    since_7d = _utc_now() - timedelta(days=7)

    counts_24h = {}
    result = await session.execute(
        select(AutomationActionLog.action_type, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.created_at >= since_24h,
            AutomationActionLog.result == "success",
        ).group_by(AutomationActionLog.action_type)
    )
    for action_type, count in result.all():
        counts_24h[action_type] = count

    counts_7d = {}
    result = await session.execute(
        select(AutomationActionLog.action_type, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.created_at >= since_7d,
            AutomationActionLog.result == "success",
        ).group_by(AutomationActionLog.action_type)
    )
    for action_type, count in result.all():
        counts_7d[action_type] = count

    total = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.result == "success",
        )
    )

    return {
        "total": total or 0,
        "last_24h": counts_24h,
        "last_7d": counts_7d,
    }


async def _chat_target_stats(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    total = await session.scalar(
        select(func.count(ChatTarget.id)).where(ChatTarget.custom_automation_id == automation_id)
    )
    joined = await session.scalar(
        select(func.count(ChatTarget.id)).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.join_status == "joined",
        )
    )
    pending = await session.scalar(
        select(func.count(ChatTarget.id)).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.join_status == "pending",
        )
    )

    mode_counts = {}
    result = await session.execute(
        select(ChatTarget.mode, func.count(ChatTarget.id)).where(
            ChatTarget.custom_automation_id == automation_id
        ).group_by(ChatTarget.mode)
    )
    for mode, count in result.all():
        mode_counts[mode] = count

    recent = await session.execute(
        select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id).order_by(
            ChatTarget.created_at.desc()
        ).limit(10)
    )

    return {
        "total": total or 0,
        "joined": joined or 0,
        "pending": pending or 0,
        "by_mode": mode_counts,
        "recent": [row for row in recent.scalars().all()],
    }


async def get_automation_dashboard(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    return {
        "automation_id": automation_id,
        "name": automation.name if automation else None,
        "client_name": automation.client_name if automation else None,
        "accounts": await _account_stats(session, automation_id),
        "leads": await _lead_stats(session, automation_id),
        "dmp": await _dmp_stats(session, automation_id),
        "actions": await _action_stats(session, automation_id),
        "chats": await _chat_target_stats(session, automation_id),
        "updated_at": _utc_now().isoformat(),
    }


async def _automation_summary(session: AsyncSession, automation: CustomAutomation) -> dict[str, Any]:
    automation_id = automation.id
    total_leads = await session.scalar(
        select(func.count(CustomLead.id)).where(CustomLead.custom_automation_id == automation_id)
    )
    total_accounts = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(PoolAccount.custom_automation_id == automation_id)
    )
    banned_accounts = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_banned.is_(True),
        )
    )
    total_messages = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.result == "success",
        )
    )
    return {
        "id": automation_id,
        "name": automation.name,
        "client_name": automation.client_name,
        "is_amocrm_enabled": automation.is_amocrm_enabled,
        "is_dmp_one_enabled": automation.is_dmp_one_enabled,
        "leads_total": total_leads or 0,
        "accounts_total": total_accounts or 0,
        "accounts_banned": banned_accounts or 0,
        "messages_total": total_messages or 0,
        "created_at": automation.created_at,
    }


async def get_admin_dashboard(session: AsyncSession) -> dict[str, Any]:
    total_automations = await session.scalar(select(func.count(CustomAutomation.id)))
    total_accounts = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        )
    )
    total_banned = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(SocialAccount.is_banned.is_(True))
    )
    total_leads = await session.scalar(select(func.count(CustomLead.id)))
    total_messages = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(AutomationActionLog.result == "success")
    )

    result = await session.execute(
        select(CustomAutomation).order_by(CustomAutomation.created_at.desc()).limit(50)
    )
    automations = result.scalars().all()
    summaries = []
    for automation in automations:
        summaries.append(await _automation_summary(session, automation))

    return {
        "total_automations": total_automations or 0,
        "total_accounts": total_accounts or 0,
        "total_banned_accounts": total_banned or 0,
        "total_leads": total_leads or 0,
        "total_messages": total_messages or 0,
        "automations": summaries,
        "updated_at": _utc_now().isoformat(),
    }
