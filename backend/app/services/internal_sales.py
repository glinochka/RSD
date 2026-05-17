"""Логика внутреннего отдела продаж (не агентский sales FSM)."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import SalesOutboundContact, SalesTeamMember
from ..config import settings

WORKFLOW_STATUSES = frozenset({"new", "in_progress", "demo", "closed", "rejected", "hesitating"})

FUNNEL_API_KEYS = ("in_base", "called", "demo", "closed", "rejected", "hesitating")

FUNNEL_PERIODS = frozenset({"day", "week", "month", "all"})

ALLOCATABLE_ROLES = frozenset({"trainee", "mop"})

MAX_DAILY_ALLOCATION_EVENTS = 2

_ws_re = re.compile(r"\s+")


def apply_role_default_quota(member: SalesTeamMember) -> None:
    if int(member.daily_contacts_quota or 0) > 0:
        return
    role = (member.role or "").strip().lower()
    if role == "trainee":
        member.daily_contacts_quota = max(0, int(settings.SALES_TRAINEE_DAILY_QUOTA))
    elif role == "mop":
        member.daily_contacts_quota = max(0, int(settings.SALES_MOP_DAILY_QUOTA))


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sales_timezone() -> ZoneInfo:
    name = (settings.SALES_DAY_TIMEZONE or "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def sales_today() -> date:
    """Календарный день отдела продаж (по умолчанию Europe/Moscow)."""
    return datetime.now(sales_timezone()).date()


def month_start_utc_naive(now: datetime | None = None) -> datetime:
    n = now or utc_now_naive()
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def effective_daily_quota(member: SalesTeamMember) -> int:
    custom = int(member.daily_contacts_quota or 0)
    if custom > 0:
        return custom
    role = (member.role or "").strip().lower()
    if role == "trainee":
        return max(0, int(settings.SALES_TRAINEE_DAILY_QUOTA))
    if role == "mop":
        return max(0, int(settings.SALES_MOP_DAILY_QUOTA))
    return 0


def _norm_org_name(name: str | None) -> str:
    s = _ws_re.sub(" ", (name or "").strip().casefold())
    return s[:120]


def _phone_tail_digits(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 10:
        return None
    return digits[-10:]


def build_contact_dedup_key(
    *,
    org_name: str | None = None,
    lpr_phone: str | None = None,
    org_phone: str | None = None,
    org_mobile: str | None = None,
) -> str | None:
    """Ключ для дедупликации активных контактов (пул + назначенные, не в архиве)."""
    tails: list[str] = []
    for raw in (lpr_phone, org_mobile, org_phone):
        tail = _phone_tail_digits(raw)
        if tail and tail not in tails:
            tails.append(tail)
    if tails:
        return f"tel:{min(tails)}"
    org = _norm_org_name(org_name)
    if org:
        return f"org:{org}"
    return None


async def clear_sales_crm_data(session: AsyncSession) -> None:
    """Удаляет все строки локальной outbound CRM и сбрасывает дневную выдачу у сотрудников отдела."""
    now = utc_now_naive()
    await session.execute(delete(SalesOutboundContact))
    await session.execute(
        update(SalesTeamMember).values(
            last_daily_allocation_date=None,
            daily_pool_alloc_total=0,
            daily_allocation_events=0,
            updated_at=now,
        )
    )


async def pool_contacts_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(
                SalesOutboundContact.assignee_id.is_(None),
                SalesOutboundContact.archived_at.is_(None),
                SalesOutboundContact.workflow_status == "new",
            )
        )
        or 0
    )


async def active_assigned_count(session: AsyncSession, member_id: int) -> int:
    """Назначенные контакты, ещё не в архиве."""
    return int(
        await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(
                SalesOutboundContact.assignee_id == member_id,
                SalesOutboundContact.archived_at.is_(None),
            )
        )
        or 0
    )


async def pending_new_count(session: AsyncSession, member_id: int) -> int:
    """Активные контакты со статусом «новый» у сотрудника."""
    return int(
        await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(
                SalesOutboundContact.assignee_id == member_id,
                SalesOutboundContact.archived_at.is_(None),
                SalesOutboundContact.workflow_status == "new",
            )
        )
        or 0
    )


async def dedup_key_exists_in_active_crm(session: AsyncSession, dedup_key: str | None) -> bool:
    if not dedup_key:
        return False
    found = await session.scalar(
        select(SalesOutboundContact.id)
        .where(
            SalesOutboundContact.dedup_key == dedup_key,
            SalesOutboundContact.archived_at.is_(None),
        )
        .limit(1)
    )
    return found is not None


async def allocate_from_pool(
    session: AsyncSession,
    *,
    member_id: int,
    limit: int,
    now: datetime | None = None,
) -> int:
    if limit <= 0:
        return 0
    n = now or utc_now_naive()
    rows = (
        await session.scalars(
            select(SalesOutboundContact)
            .where(
                SalesOutboundContact.assignee_id.is_(None),
                SalesOutboundContact.archived_at.is_(None),
                SalesOutboundContact.workflow_status == "new",
            )
            .order_by(SalesOutboundContact.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for row in rows:
        row.assignee_id = member_id
        row.assigned_at = n
        row.updated_at = n
    return len(rows)


async def archive_worked_contacts_for_assignee(
    session: AsyncSession,
    *,
    member_id: int,
    now: datetime | None = None,
) -> int:
    """В архив — назначенные контакты, по которым уже выставлен статус (не «новый»)."""
    ts = now or utc_now_naive()
    res = await session.execute(
        update(SalesOutboundContact)
        .where(
            SalesOutboundContact.assignee_id == member_id,
            SalesOutboundContact.archived_at.is_(None),
            SalesOutboundContact.workflow_status != "new",
        )
        .values(archived_at=ts, updated_at=ts)
    )
    return int(res.rowcount or 0)


async def release_active_contacts_to_pool(
    session: AsyncSession,
    *,
    member_id: int,
    now: datetime | None = None,
) -> int:
    """Вернуть активные контакты в общий пул при деактивации сотрудника."""
    ts = now or utc_now_naive()
    res = await session.execute(
        update(SalesOutboundContact)
        .where(
            SalesOutboundContact.assignee_id == member_id,
            SalesOutboundContact.archived_at.is_(None),
        )
        .values(
            assignee_id=None,
            assigned_at=None,
            updated_at=ts,
        )
    )
    return int(res.rowcount or 0)


def _reset_daily_counters(member: SalesTeamMember, today: date, now: datetime) -> None:
    member.last_daily_allocation_date = today
    member.daily_pool_alloc_total = 0
    member.daily_allocation_events = 0
    member.updated_at = now


async def _roll_sales_day_if_needed(session: AsyncSession, member: SalesTeamMember, now: datetime) -> None:
    today = sales_today()
    if member.last_daily_allocation_date == today:
        return
    await archive_worked_contacts_for_assignee(session, member_id=member.id, now=now)
    _reset_daily_counters(member, today, now)


async def ensure_daily_allocation(session: AsyncSession, member: SalesTeamMember) -> int:
    """
    Первая выдача за день: дозаполнить активную работу до дневной нормы из пула.
    Считается событием выдачи №1 (если из пула что-то назначено).
    """
    role = (member.role or "").strip().lower()
    if role not in ALLOCATABLE_ROLES:
        return 0
    now = utc_now_naive()
    quota = effective_daily_quota(member)
    if quota <= 0:
        return 0

    await _roll_sales_day_if_needed(session, member, now)

    events = int(member.daily_allocation_events or 0)
    if events >= MAX_DAILY_ALLOCATION_EVENTS:
        return 0
    if events >= 1:
        return 0

    active = await active_assigned_count(session, member.id)
    needed = max(0, quota - active)
    if needed <= 0:
        member.daily_allocation_events = max(events, 1)
        member.updated_at = now
        return 0

    allocated = await allocate_from_pool(session, member_id=member.id, limit=needed, now=now)
    if allocated > 0:
        member.daily_pool_alloc_total = int(member.daily_pool_alloc_total or 0) + allocated
        member.daily_allocation_events = 1
        member.updated_at = now
    elif active > 0:
        member.daily_allocation_events = 1
        member.updated_at = now
    return allocated


async def request_more_contacts(session: AsyncSession, member: SalesTeamMember) -> int:
    """Вторая выдача за день — до полной нормы контактов одной порцией."""
    role = (member.role or "").strip().lower()
    if role not in ALLOCATABLE_ROLES:
        return 0
    pending = await pending_new_count(session, member.id)
    if pending > 0:
        raise ValueError("Сначала проставьте статусы всем контактам в текущей работе")
    quota = effective_daily_quota(member)
    if quota <= 0:
        raise ValueError("Дневная норма контактов не настроена")
    events = int(member.daily_allocation_events or 0)
    if events >= MAX_DAILY_ALLOCATION_EVENTS:
        raise ValueError("Достигнут лимит: не более 2 выдач контактов в день")
    if events < 1:
        raise ValueError("Сначала получите первую выдачу за день (откройте рабочий стол)")
    pool_left = await pool_contacts_count(session)
    if pool_left <= 0:
        raise ValueError("В общей базе нет свободных контактов")
    now = utc_now_naive()
    await _roll_sales_day_if_needed(session, member, now)
    events = int(member.daily_allocation_events or 0)
    if events >= MAX_DAILY_ALLOCATION_EVENTS:
        raise ValueError("Достигнут лимит: не более 2 выдач контактов в день")

    n = await allocate_from_pool(session, member_id=member.id, limit=quota, now=now)
    if n <= 0:
        raise ValueError("В общей базе нет свободных контактов")
    member.daily_pool_alloc_total = int(member.daily_pool_alloc_total or 0) + n
    member.daily_allocation_events = 2
    member.updated_at = now
    return n


def can_request_more_contacts(
    member: SalesTeamMember,
    *,
    pending_new: int,
    pool_size: int,
) -> bool:
    role = (member.role or "").strip().lower()
    if role not in ALLOCATABLE_ROLES:
        return False
    if pending_new > 0 or pool_size <= 0:
        return False
    events = int(getattr(member, "daily_allocation_events", 0) or 0)
    return events == 1


async def subtree_member_ids(session: AsyncSession, root_id: int) -> set[int]:
    found: set[int] = {root_id}
    frontier: set[int] = {root_id}
    while frontier:
        q = select(SalesTeamMember.id).where(
            SalesTeamMember.supervisor_id.in_(frontier),
            SalesTeamMember.is_active.is_(True),
        )
        rows = (await session.scalars(q)).all()
        next_ids = {int(r) for r in rows} - found
        found |= next_ids
        frontier = next_ids
    return found


def normalize_funnel_period(period: str | None, *, default: str = "all") -> str:
    p = (period or default).strip().lower()
    if p not in FUNNEL_PERIODS:
        raise ValueError("Период воронки: day, week, month или all")
    return p


def funnel_period_range(period: str) -> tuple[datetime | None, datetime | None]:
    """
    Границы периода воронки (UTC naive, как в БД).
    day / week / month — календарные границы в SALES_DAY_TIMEZONE; all — без фильтра.
    """
    period = normalize_funnel_period(period)
    if period == "all":
        return None, None
    tz = sales_timezone()
    now_local = datetime.now(tz)
    today = now_local.date()
    if period == "day":
        start_local = datetime.combine(today, time.min, tzinfo=tz)
    elif period == "week":
        start_local = datetime.combine(today - timedelta(days=6), time.min, tzinfo=tz)
    else:
        start_local = datetime.combine(today.replace(day=1), time.min, tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = now_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def contact_funnel_activity_at() -> ColumnElement:
    """Момент последней значимой работы по контакту (для фильтра воронки по периоду)."""
    return func.coalesce(
        SalesOutboundContact.archived_at,
        SalesOutboundContact.called_at,
        SalesOutboundContact.updated_at,
        SalesOutboundContact.assigned_at,
        SalesOutboundContact.created_at,
    )


def _apply_funnel_period_filter(q: Select, period: str) -> Select:
    period = normalize_funnel_period(period)
    if period == "all":
        return q
    start, end = funnel_period_range(period)
    activity = contact_funnel_activity_at()
    if start is not None:
        q = q.where(activity >= start)
    if end is not None:
        q = q.where(activity <= end)
    return q


def _raw_status_counts_to_funnel(raw: dict[str, int]) -> dict[str, int]:
    return {
        "in_base": raw.get("new", 0),
        "called": raw.get("in_progress", 0),
        "demo": raw.get("demo", 0),
        "closed": raw.get("closed", 0),
        "rejected": raw.get("rejected", 0),
        "hesitating": raw.get("hesitating", 0),
    }


async def funnel_counts(
    session: AsyncSession,
    assignee_ids: list[int] | None,
    *,
    period: str = "all",
) -> dict[str, int]:
    if assignee_ids is not None and len(assignee_ids) == 0:
        return empty_funnel_dict()
    q: Select[tuple[str, int]] = (
        select(SalesOutboundContact.workflow_status, func.count(SalesOutboundContact.id))
        .where(SalesOutboundContact.assignee_id.is_not(None))
        .group_by(SalesOutboundContact.workflow_status)
    )
    q = _apply_funnel_period_filter(q, period)
    if assignee_ids is not None:
        q = q.where(SalesOutboundContact.assignee_id.in_(assignee_ids))
    rows = (await session.execute(q)).all()
    raw: dict[str, int] = {}
    for st, cnt in rows:
        raw[str(st)] = int(cnt)
    return _raw_status_counts_to_funnel(raw)


async def funnel_counts_by_members(
    session: AsyncSession,
    assignee_ids: list[int],
    *,
    period: str = "all",
) -> dict[int, dict[str, int]]:
    """Воронка по каждому сотруднику одним запросом."""
    if not assignee_ids:
        return {}
    q = (
        select(
            SalesOutboundContact.assignee_id,
            SalesOutboundContact.workflow_status,
            func.count(SalesOutboundContact.id),
        )
        .where(SalesOutboundContact.assignee_id.in_(assignee_ids))
        .group_by(SalesOutboundContact.assignee_id, SalesOutboundContact.workflow_status)
    )
    q = _apply_funnel_period_filter(q, period)
    rows = (await session.execute(q)).all()
    per_member_raw: dict[int, dict[str, int]] = {mid: {} for mid in assignee_ids}
    for assignee_id, status, cnt in rows:
        if assignee_id is None:
            continue
        per_member_raw[int(assignee_id)][str(status)] = int(cnt)

    result: dict[int, dict[str, int]] = {}
    for mid in assignee_ids:
        result[mid] = _raw_status_counts_to_funnel(per_member_raw.get(mid, {}))
    return result


async def monthly_done_counts(
    session: AsyncSession,
    member_id: int,
    month_start: datetime,
) -> dict[str, int]:
    calls = await session.scalar(
        select(func.count(SalesOutboundContact.id)).where(
            SalesOutboundContact.assignee_id == member_id,
            SalesOutboundContact.called_at.is_not(None),
            SalesOutboundContact.called_at >= month_start,
        )
    )
    demos = await session.scalar(
        select(func.count(SalesOutboundContact.id)).where(
            SalesOutboundContact.assignee_id == member_id,
            SalesOutboundContact.demo_at.is_not(None),
            SalesOutboundContact.demo_at >= month_start,
        )
    )
    closes = await session.scalar(
        select(func.count(SalesOutboundContact.id)).where(
            SalesOutboundContact.assignee_id == member_id,
            SalesOutboundContact.closed_at.is_not(None),
            SalesOutboundContact.closed_at >= month_start,
        )
    )
    return {
        "calls_done": int(calls or 0),
        "demos_done": int(demos or 0),
        "closes_done": int(closes or 0),
    }


def apply_workflow_timestamps(contact: SalesOutboundContact, new_status: str, now: datetime) -> None:
    contact.workflow_status = new_status
    if new_status in ("in_progress", "demo", "closed") and contact.called_at is None:
        contact.called_at = now
    if new_status in ("demo", "closed") and contact.demo_at is None:
        contact.demo_at = now
    if new_status == "closed" and contact.closed_at is None:
        contact.closed_at = now
    contact.updated_at = now


def empty_funnel_dict() -> dict[str, int]:
    return {k: 0 for k in FUNNEL_API_KEYS}


def member_public_dict(m: SalesTeamMember, funnel: dict[str, int] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": m.id,
        "login": m.login,
        "role": m.role,
        "supervisor_id": m.supervisor_id,
        "is_active": m.is_active,
        "plan_calls_monthly": m.plan_calls_monthly,
        "plan_demos_monthly": m.plan_demos_monthly,
        "plan_closes_monthly": m.plan_closes_monthly,
        "daily_contacts_quota": m.daily_contacts_quota,
        "effective_daily_quota": effective_daily_quota(m),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
    if funnel is not None:
        data["funnel"] = funnel
    return data


def contact_to_api_dict(r: SalesOutboundContact) -> dict[str, Any]:
    return {
        "id": r.id,
        "workflow_status": r.workflow_status,
        "org_name": r.org_name,
        "lpr_name": r.lpr_name,
        "lpr_phone": r.lpr_phone,
        "org_phone": r.org_phone,
        "org_mobile": r.org_mobile,
        "import_status": r.import_status,
        "comment": r.comment,
        "email": r.email,
        "website": r.website,
        "assigned_at": r.assigned_at.isoformat() if r.assigned_at else None,
        "archived_at": r.archived_at.isoformat() if r.archived_at else None,
        "called_at": r.called_at.isoformat() if r.called_at else None,
        "demo_at": r.demo_at.isoformat() if r.demo_at else None,
        "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def add_contact_to_pool(
    session: AsyncSession,
    *,
    org_name: str,
    lpr_name: str | None = None,
    lpr_phone: str | None = None,
    org_phone: str | None = None,
    org_mobile: str | None = None,
    import_status: str | None = None,
    email: str | None = None,
    website: str | None = None,
    extra_json: str | None = None,
    now: datetime | None = None,
) -> tuple[SalesOutboundContact | None, bool]:
    """Добавить контакт в пул. Второй элемент — True, если пропущен как дубликат."""
    ts = now or utc_now_naive()
    dedup = build_contact_dedup_key(
        org_name=org_name,
        lpr_phone=lpr_phone,
        org_phone=org_phone,
        org_mobile=org_mobile,
    )
    if await dedup_key_exists_in_active_crm(session, dedup):
        return None, True
    row = SalesOutboundContact(
        assignee_id=None,
        workflow_status="new",
        org_name=org_name[:512],
        lpr_name=lpr_name,
        lpr_phone=lpr_phone,
        org_phone=org_phone,
        org_mobile=org_mobile,
        import_status=import_status,
        email=email,
        website=website,
        extra_json=extra_json,
        dedup_key=dedup,
        created_at=ts,
        updated_at=ts,
    )
    session.add(row)
    return row, False


async def import_contacts_from_excel(
    session: AsyncSession,
    *,
    file_bytes: bytes,
) -> tuple[int, int]:
    from .sales_excel_import import extras_to_json, parse_sales_excel

    try:
        rows = parse_sales_excel(file_bytes)
    except Exception as e:
        raise ValueError(f"Не удалось разобрать файл Excel: {e}") from e
    imported = 0
    skipped = 0
    for r in rows:
        _, dup = await add_contact_to_pool(
            session,
            org_name=r["org_name"],
            lpr_name=r.get("lpr_name"),
            lpr_phone=r.get("lpr_phone"),
            org_phone=r.get("org_phone"),
            org_mobile=r.get("org_mobile"),
            import_status=r.get("import_status"),
            email=r.get("email"),
            website=r.get("website"),
            extra_json=extras_to_json(r.get("extras") or {}),
        )
        if dup:
            skipped += 1
        else:
            imported += 1
    await session.commit()
    return imported, skipped


async def apply_sales_team_member_update(
    session: AsyncSession,
    row: SalesTeamMember,
    data: dict[str, Any],
    *,
    member_id: int,
) -> None:
    """Общая логика PATCH сотрудника отдела продаж."""
    now = utc_now_naive()
    if "password" in data and data["password"]:
        from ..utils.security import get_password_hash

        row.password_hash = get_password_hash(data.pop("password"))
    if "supervisor_id" in data:
        row.supervisor_id = data.pop("supervisor_id")
    if "role" in data and data["role"] is not None:
        new_role = str(data.pop("role")).strip().lower()
        if new_role not in ("trainee", "mop", "rop"):
            raise ValueError("Некорректная роль")
        if new_role == "rop" and row.supervisor_id is not None:
            row.supervisor_id = None
        row.role = new_role
        if int(row.daily_contacts_quota or 0) <= 0:
            apply_role_default_quota(row)
    if "is_active" in data and data["is_active"] is not None:
        new_active = bool(data.pop("is_active"))
        if not new_active and row.is_active:
            await release_active_contacts_to_pool(session, member_id=member_id, now=now)
        row.is_active = new_active
    for field in (
        "plan_calls_monthly",
        "plan_demos_monthly",
        "plan_closes_monthly",
        "daily_contacts_quota",
    ):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])
    row.updated_at = now
