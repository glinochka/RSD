"""Analytics aggregation for /custom dashboards."""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatDiscoveryTask,
    ChatImportJob,
    ChatTarget,
    CustomAutomation,
    CustomJob,
    CustomLead,
    DmpOneImport,
    PoolAccount,
    SocialAccount,
)

# Product actions for the dashboard «Активность» widget — not system jobs.
DASHBOARD_ACTIVITY_TYPES = (
    "dm",
    "chat_monitoring",
    "neurocommenting",
    "shilling_chat",
    "shilling_post",
    "unsubscribe",
)

DASHBOARD_ACTIVITY_GROUP = {
    "dm": "chat_monitoring",
    "chat_monitoring": "chat_monitoring",
    "neurocommenting": "neurocommenting",
    "shilling_chat": "shilling",
    "shilling_post": "shilling",
    "unsubscribe": "unsubscribe",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _group_activity_counts(raw: dict[str, int]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for action_type, count in raw.items():
        key = DASHBOARD_ACTIVITY_GROUP.get(action_type)
        if not key or not count:
            continue
        grouped[key] = grouped.get(key, 0) + int(count)
    return grouped


async def _count_actions_by_type(
    session: AsyncSession,
    automation_id: int,
    *,
    since: datetime | None = None,
) -> dict[str, int]:
    stmt = select(AutomationActionLog.action_type, func.count(AutomationActionLog.id)).where(
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.result == "success",
        AutomationActionLog.action_type.in_(DASHBOARD_ACTIVITY_TYPES),
    )
    if since is not None:
        stmt = stmt.where(AutomationActionLog.created_at >= since)
    result = await session.execute(stmt.group_by(AutomationActionLog.action_type))
    return {action_type: count for action_type, count in result.all()}


async def _count_amocrm_transfers(
    session: AsyncSession,
    automation_id: int,
    *,
    since: datetime | None = None,
) -> int:
    stmt = select(func.count(CustomLead.id)).where(
        CustomLead.custom_automation_id == automation_id,
        CustomLead.amocrm_lead_id.isnot(None),
        CustomLead.transferred_at.isnot(None),
    )
    if since is not None:
        stmt = stmt.where(CustomLead.transferred_at >= since)
    return int(await session.scalar(stmt) or 0)


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
            SocialAccount.is_frozen.is_(False),
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
    revoked = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(False),
            SocialAccount.is_banned.is_(False),
            SocialAccount.session_file_path.isnot(None),
        )
    )
    spamblocked = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_spamblocked.is_(True),
        )
    )
    frozen = await session.scalar(
        select(func.count(SocialAccount.id)).join(
            PoolAccount, PoolAccount.social_account_id == SocialAccount.id
        ).where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_frozen.is_(True),
        )
    )

    return {
        "total": total or 0,
        "active": active or 0,
        "banned": banned or 0,
        "revoked": revoked or 0,
        "spamblocked": spamblocked or 0,
        "frozen": frozen or 0,
        "by_class": {},
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

    counts_24h = _group_activity_counts(
        await _count_actions_by_type(session, automation_id, since=since_24h)
    )
    counts_7d = _group_activity_counts(
        await _count_actions_by_type(session, automation_id, since=since_7d)
    )

    amo_24h = await _count_amocrm_transfers(session, automation_id, since=since_24h)
    if amo_24h:
        counts_24h["amocrm_transfer"] = amo_24h
    amo_7d = await _count_amocrm_transfers(session, automation_id, since=since_7d)
    if amo_7d:
        counts_7d["amocrm_transfer"] = amo_7d

    total = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.result == "success",
            AutomationActionLog.action_type.in_(DASHBOARD_ACTIVITY_TYPES),
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


def _period_since(period: str) -> datetime | None:
    now = _utc_now()
    key = (period or "all").strip().lower()
    if key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if key == "week":
        return now - timedelta(days=7)
    if key == "month":
        return now - timedelta(days=30)
    return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(float(ordered[mid]), 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _age_days(account: SocialAccount, now: datetime) -> float:
    if account.account_age_days:
        return float(account.account_age_days)
    created = account.created_at or now
    return max(0.0, (now - created).total_seconds() / 86400)


def _chat_id_from_log(log: AutomationActionLog, payload: dict[str, Any]) -> int | None:
    raw = payload.get("chat_target_id")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    target = str(log.target_id or "")
    head = target.split(":", 1)[0] if target else ""
    try:
        return int(head) if head else None
    except ValueError:
        return None


def _account_label(account: SocialAccount | None) -> str:
    if not account:
        return "—"
    return account.display_name or account.username or account.phone_number or f"#{account.id}"


def _chat_label(chat: ChatTarget | None, payload: dict[str, Any], chat_id: int | None) -> str:
    if chat and chat.title:
        return chat.title
    title = payload.get("chat_title")
    if title:
        return str(title)
    if chat and chat.invite_link:
        return chat.invite_link
    if chat_id:
        return f"#{chat_id}"
    return "—"


HISTORY_TYPES = {
    "neurocommenting": ("neurocommenting",),
    "shilling": ("shilling_chat", "shilling_post"),
    "discussion": ("discussion",),
    "masslooking": ("masslooking",),
    "chat_broadcast": ("chat_broadcast",),
    "intercept": ("dm", "chat_monitoring"),
    "dmp": ("dmp", "dmp_outreach"),
    "warmup": ("account_warmup", "peer_dialog", "comment_contact"),
    "masspriming": ("masspriming",),
    "parser": ("parser",),
}


async def _log_counts(
    session: AsyncSession,
    automation_id: int,
    types: tuple[str, ...],
    *,
    since: datetime | None = None,
) -> dict[str, int]:
    stmt = select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.action_type.in_(types),
    )
    if since is not None:
        stmt = stmt.where(AutomationActionLog.created_at >= since)
    rows = await session.execute(stmt.group_by(AutomationActionLog.result))
    data = {str(result or ""): int(count) for result, count in rows.all()}
    success = data.get("success", 0)
    error = data.get("error", 0)
    attempts = sum(data.values())
    deleted_stmt = select(func.count(AutomationActionLog.id)).where(
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.action_type.in_(types),
        AutomationActionLog.result == "error",
        AutomationActionLog.error_message.ilike("%удален%"),
    )
    if since is not None:
        deleted_stmt = deleted_stmt.where(AutomationActionLog.created_at >= since)
    deleted = int(await session.scalar(deleted_stmt) or 0)
    return {
        "attempts": attempts,
        "success": success,
        "failed": error,
        "deleted": deleted,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
    }


async def _daily_series(
    session: AsyncSession,
    automation_id: int,
    *,
    since: datetime | None,
    types: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    start = since or (_utc_now() - timedelta(days=30))
    stmt = select(
        func.date(AutomationActionLog.created_at),
        AutomationActionLog.action_type,
        func.count(AutomationActionLog.id),
    ).where(
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.result == "success",
        AutomationActionLog.created_at >= start,
    )
    if types:
        stmt = stmt.where(AutomationActionLog.action_type.in_(types))
    rows = await session.execute(stmt.group_by(func.date(AutomationActionLog.created_at), AutomationActionLog.action_type))
    by_day: dict[str, dict[str, int]] = {}
    for day, action_type, count in rows.all():
        key = str(day)
        bucket = by_day.setdefault(key, {})
        grouped = DASHBOARD_ACTIVITY_GROUP.get(action_type, action_type)
        bucket[grouped] = bucket.get(grouped, 0) + int(count)
    return [{"date": day, **counts} for day, counts in sorted(by_day.items())]


async def _channel_lists(
    session: AsyncSession,
    automation_id: int,
    types: tuple[str, ...],
    *,
    since: datetime | None,
    threshold: float,
    min_attempts: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stmt = select(AutomationActionLog).where(
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.action_type.in_(types),
    )
    if since is not None:
        stmt = stmt.where(AutomationActionLog.created_at >= since)
    logs = (await session.execute(stmt)).scalars().all()
    by_chat: dict[int, dict[str, Any]] = {}
    chat_ids: set[int] = set()
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        chat_id = _chat_id_from_log(log, payload)
        if not chat_id:
            continue
        chat_ids.add(chat_id)
        bucket = by_chat.setdefault(
            chat_id,
            {"attempts": 0, "success": 0, "failed": 0, "title": payload.get("chat_title")},
        )
        bucket["attempts"] += 1
        if log.result == "success":
            bucket["success"] += 1
        else:
            bucket["failed"] += 1
    chats: dict[int, ChatTarget] = {}
    if chat_ids:
        rows = (await session.execute(select(ChatTarget).where(ChatTarget.id.in_(chat_ids)))).scalars().all()
        chats = {chat.id: chat for chat in rows}
    white: list[dict[str, Any]] = []
    black: list[dict[str, Any]] = []
    for chat_id, stats in by_chat.items():
        if stats["attempts"] < min_attempts:
            continue
        pct = round((stats["success"] / stats["attempts"]) * 100, 1) if stats["attempts"] else 0.0
        chat = chats.get(chat_id)
        row = {
            "id": chat_id,
            "title": (chat.title if chat else None) or stats["title"] or f"#{chat_id}",
            "attempts": stats["attempts"],
            "success": stats["success"],
            "success_pct": pct,
        }
        if pct >= threshold:
            white.append(row)
        else:
            black.append(row)
    white.sort(key=lambda item: (-item["success_pct"], -item["attempts"]))
    black.sort(key=lambda item: (item["success_pct"], -item["attempts"]))
    return white, black


async def get_ubt_stats(
    session: AsyncSession,
    automation_id: int,
    *,
    period: str = "all",
    history_type: str = "neurocommenting",
    search: str | None = None,
    status: str | None = None,
    visibility: str | None = None,
    threshold: float = 50.0,
    min_attempts: int = 3,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    since = _period_since(period)
    now = _utc_now()
    accounts = await _account_stats(session, automation_id)
    chats = await _chat_target_stats(session, automation_id)

    extra_account = await session.execute(
        select(SocialAccount, PoolAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(PoolAccount.custom_automation_id == automation_id)
    )
    pairs = extra_account.all()
    pool_accounts = [account for account, _pool in pairs]
    channel_banned = sum(1 for item in pool_accounts if item.is_channel_banned)
    with_proxy = sum(1 for account, pool in pairs if account.telegram_proxy or pool.proxy_id)
    empty = sum(1 for item in pool_accounts if not item.session_file_path)
    in_work = sum(1 for item in pool_accounts if item.is_active and (item.daily_messages_sent or 0) > 0)
    quarantine = sum(1 for _account, pool in pairs if pool.warmup_status in {"rest", "warming"})
    ages = [_age_days(item, now) for item in pool_accounts]
    valid_ages = [
        _age_days(item, now)
        for item in pool_accounts
        if item.is_active and not item.is_banned and not item.is_frozen
    ]
    dead_ages = []
    for item in pool_accounts:
        if item.is_banned and item.banned_at and item.created_at:
            dead_ages.append(max(0.0, (item.banned_at - item.created_at).total_seconds() / 86400))

    jobs_total = int(
        await session.scalar(select(func.count(CustomJob.id)).where(CustomJob.custom_automation_id == automation_id)) or 0
    )
    jobs_total += int(
        await session.scalar(
            select(func.count(ChatDiscoveryTask.id)).where(ChatDiscoveryTask.custom_automation_id == automation_id)
        )
        or 0
    )
    jobs_total += int(
        await session.scalar(
            select(func.count(ChatImportJob.id)).where(ChatImportJob.custom_automation_id == automation_id)
        )
        or 0
    )

    comments = await _log_counts(session, automation_id, HISTORY_TYPES["neurocommenting"], since=since)
    shilling = await _log_counts(session, automation_id, HISTORY_TYPES["shilling"], since=since)
    discussion = await _log_counts(session, automation_id, HISTORY_TYPES["discussion"], since=since)
    intercept = await _log_counts(session, automation_id, HISTORY_TYPES["intercept"], since=since)
    dmp = await _log_counts(session, automation_id, HISTORY_TYPES["dmp"], since=since)
    masslooking = await _log_counts(session, automation_id, HISTORY_TYPES["masslooking"], since=since)
    chat_broadcast = await _log_counts(session, automation_id, HISTORY_TYPES["chat_broadcast"], since=since)
    warmup = await _log_counts(session, automation_id, HISTORY_TYPES["warmup"], since=since)
    masspriming = await _log_counts(session, automation_id, HISTORY_TYPES["masspriming"], since=since)
    parser = await _log_counts(session, automation_id, HISTORY_TYPES["parser"], since=since)
    success_all = comments["success"] + shilling["success"] + discussion["success"] + intercept["success"] + dmp["success"] + masslooking["success"] + chat_broadcast["success"] + warmup["success"] + masspriming["success"] + parser["success"]
    attempts_all = comments["attempts"] + shilling["attempts"] + discussion["attempts"] + intercept["attempts"] + dmp["attempts"] + masslooking["attempts"] + chat_broadcast["attempts"] + warmup["attempts"] + masspriming["attempts"] + parser["attempts"]

    wanted = HISTORY_TYPES.get(history_type) or HISTORY_TYPES["neurocommenting"]
    history_stmt = (
        select(AutomationActionLog, SocialAccount)
        .join(SocialAccount, SocialAccount.id == AutomationActionLog.social_account_id, isouter=True)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type.in_(wanted),
        )
        .order_by(AutomationActionLog.created_at.desc())
    )
    if since is not None:
        history_stmt = history_stmt.where(AutomationActionLog.created_at >= since)
    rows = (await session.execute(history_stmt.limit(500))).all()

    chat_ids = set()
    parsed_rows: list[tuple[AutomationActionLog, SocialAccount | None, dict[str, Any], int | None]] = []
    for log, account in rows:
        payload = log.payload if isinstance(log.payload, dict) else {}
        chat_id = _chat_id_from_log(log, payload)
        if chat_id:
            chat_ids.add(chat_id)
        parsed_rows.append((log, account, payload, chat_id))
    chat_map: dict[int, ChatTarget] = {}
    if chat_ids:
        chat_rows = (await session.execute(select(ChatTarget).where(ChatTarget.id.in_(chat_ids)))).scalars().all()
        chat_map = {chat.id: chat for chat in chat_rows}

    needle = (search or "").strip().lower()
    items: list[dict[str, Any]] = []
    for log, account, payload, chat_id in parsed_rows:
        chat = chat_map.get(chat_id) if chat_id else None
        if status and log.result != status:
            continue
        if visibility == "open" and not (chat and chat.comments_open is True):
            continue
        if visibility == "closed" and not (chat and chat.comments_open is False):
            continue
        channel = _chat_label(chat, payload, chat_id)
        text = payload.get("text") or payload.get("reply") or payload.get("setup") or payload.get("source_text") or ""
        if needle:
            blob = " ".join(
                [
                    str(text),
                    channel,
                    _account_label(account),
                    str(payload.get("prompt") or ""),
                ]
            ).lower()
            if needle not in blob:
                continue
        visibility_value = "unknown"
        if chat and chat.comments_open is True:
            visibility_value = "open"
        elif chat and chat.comments_open is False:
            visibility_value = "closed"
        items.append(
            {
                "id": log.id,
                "account": _account_label(account),
                "account_id": account.id if account else None,
                "channel": channel,
                "chat_id": chat_id,
                "text": text,
                "prompt": payload.get("prompt") or payload.get("prompt_name") or "—",
                "status": log.result,
                "visibility": visibility_value,
                "action_type": log.action_type,
                "created_at": log.created_at,
            }
        )
    total_items = len(items)
    page = items[offset : offset + max(1, min(limit, 100))]

    black = (
        await session.execute(
            select(ChatTarget)
            .where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.black_boxed_at.isnot(None),
            )
            .order_by(ChatTarget.black_boxed_at.desc())
        )
    ).scalars().all()
    white_list, generated_black = await _channel_lists(
        session,
        automation_id,
        wanted,
        since=since,
        threshold=threshold,
        min_attempts=min_attempts,
    )

    incidents: dict[str, dict[str, int]] = {}
    status_changes: list[dict[str, Any]] = []
    for account, _pool in pairs:
        label = _account_label(account)
        for field, key, from_status in (
            ("banned_at", "banned", "valid"),
            ("frozen_at", "frozen", "valid"),
            ("spamblocked_at", "spamblock", "valid"),
        ):
            stamp = getattr(account, field, None)
            if not stamp or (since and stamp < since):
                continue
            day = stamp.date().isoformat()
            bucket = incidents.setdefault(day, {})
            bucket[key] = bucket.get(key, 0) + 1
            status_changes.append(
                {
                    "at": stamp,
                    "account": label,
                    "account_id": account.id,
                    "from": from_status,
                    "to": key,
                }
            )
        if not account.is_active and account.session_file_path and (not since or (account.updated_at and account.updated_at >= since)):
            status_changes.append(
                {
                    "at": account.updated_at,
                    "account": label,
                    "account_id": account.id,
                    "from": "valid",
                    "to": "revoked",
                }
            )
    status_changes.sort(key=lambda item: item.get("at") or now, reverse=True)

    return {
        "period": period or "all",
        "dashboard": {
            "accounts": accounts["total"],
            "chats": chats["total"],
            "jobs": jobs_total,
            "messages": discussion["success"],
            "comments": comments["success"],
            "intercept": intercept["success"],
            "success_pct": round((success_all / attempts_all) * 100, 1) if attempts_all else 0.0,
            "series": await _daily_series(session, automation_id, since=since),
            "by_module": {
                "neurocommenting": comments["success"],
                "shilling": shilling["success"],
                "discussion": discussion["success"],
                "intercept": intercept["success"],
                "dmp": dmp["success"],
                "masslooking": masslooking["success"],
                "chat_broadcast": chat_broadcast["success"],
                "warmup": warmup["success"],
                "masspriming": masspriming["success"],
                "parser": parser["success"],
            },
        },
        "accounts": {
            **accounts,
            "channel_banned": channel_banned,
            "with_proxy": with_proxy,
            "empty": empty,
            "in_work": in_work,
            "quarantine": quarantine,
            "invalid": accounts["revoked"] + empty,
            "avg_age_days": round(sum(ages) / len(ages), 1) if ages else 0.0,
            "median_age_days": _median(ages),
            "valid_age_days": round(sum(valid_ages) / len(valid_ages), 1) if valid_ages else 0.0,
            "lifespan_days": round(sum(dead_ages) / len(dead_ages), 1) if dead_ages else 0.0,
            "incidents": [{"date": day, **counts} for day, counts in sorted(incidents.items())],
            "status_changes": status_changes[:50],
            "distribution": {
                "valid": accounts["active"],
                "frozen": accounts["frozen"],
                "spamblock": accounts["spamblocked"],
                "banned": accounts["banned"],
                "revoked": accounts["revoked"],
                "channel_banned": channel_banned,
                "quarantine": quarantine,
            },
        },
        "history": {
            "type": history_type,
            "threshold": threshold,
            "min_attempts": min_attempts,
            "summary": {
                "neurocommenting": comments,
                "shilling": shilling,
                "discussion": discussion,
                "intercept": intercept,
                "dmp": dmp,
                "masslooking": masslooking,
                "chat_broadcast": chat_broadcast,
                "warmup": warmup,
                "masspriming": masspriming,
                "parser": parser,
            },
            "items": page,
            "total": total_items,
            "whitelist": white_list,
            "generated_blacklist": generated_black,
            "blacklist": [
                {
                    "id": chat.id,
                    "title": chat.title or chat.invite_link or f"#{chat.id}",
                    "username": chat.invite_link,
                    "black_boxed_at": chat.black_boxed_at,
                    "reason": chat.last_join_error or chat.comments_check_error,
                }
                for chat in black
            ],
        },
    }


async def blackbox_stats_chat(
    session: AsyncSession,
    automation_id: int,
    *,
    chat_id: int | None = None,
    query: str | None = None,
    reason: str = "manual",
) -> ChatTarget:
    stmt = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
    if chat_id:
        stmt = stmt.where(ChatTarget.id == chat_id)
    elif query and query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(or_(ChatTarget.title.ilike(needle), ChatTarget.invite_link.ilike(needle)))
    else:
        raise ValueError("Укажите канал")
    chat = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if not chat:
        raise ValueError("Канал не найден в списке чатов")
    from .chat_membership_service import blackbox_unusable_chat

    await blackbox_unusable_chat(session, chat, reason=reason or "manual")
    await session.commit()
    await session.refresh(chat)
    return chat


