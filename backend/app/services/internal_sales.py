"""Логика внутреннего отдела продаж (не агентский sales FSM)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import SalesOutboundContact, SalesTeamMember
from ..config import settings

WORKFLOW_STATUSES = frozenset({"new", "in_progress", "demo", "closed", "rejected", "hesitating"})

FUNNEL_API_KEYS = ("in_base", "called", "demo", "closed", "rejected", "hesitating")

ALLOCATABLE_ROLES = frozenset({"trainee", "mop"})


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


def utc_today() -> date:
    return utc_now_naive().date()


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


async def ensure_daily_allocation(session: AsyncSession, member: SalesTeamMember) -> int:
    """Выдача дневной нормы из общего пула (раз в календарный день UTC)."""
    role = (member.role or "").strip().lower()
    if role not in ALLOCATABLE_ROLES:
        return 0
    today = utc_today()
    if member.last_daily_allocation_date == today:
        return 0
    quota = effective_daily_quota(member)
    if quota <= 0:
        return 0
    allocated = await allocate_from_pool(session, member_id=member.id, limit=quota)
    if allocated > 0 or await pool_contacts_count(session) == 0:
        member.last_daily_allocation_date = today
        member.updated_at = utc_now_naive()
    elif quota > 0:
        member.last_daily_allocation_date = today
        member.updated_at = utc_now_naive()
    return allocated


async def request_more_contacts(session: AsyncSession, member: SalesTeamMember) -> int:
    """Дополнительная порция из пула, если нет необработанных (status=new) контактов."""
    role = (member.role or "").strip().lower()
    if role not in ALLOCATABLE_ROLES:
        return 0
    pending = await pending_new_count(session, member.id)
    if pending > 0:
        raise ValueError("Сначала проставьте статусы всем контактам в текущей работе")
    quota = effective_daily_quota(member)
    if quota <= 0:
        raise ValueError("Дневная норма контактов не настроена")
    pool_left = await pool_contacts_count(session)
    if pool_left <= 0:
        raise ValueError("В общей базе нет свободных контактов")
    return await allocate_from_pool(session, member_id=member.id, limit=quota)


def archive_if_worked(contact: SalesOutboundContact, *, previous_status: str, now: datetime) -> None:
    prev = (previous_status or "new").strip().lower()
    cur = (contact.workflow_status or "new").strip().lower()
    if prev == "new" and cur != "new" and contact.archived_at is None:
        contact.archived_at = now


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


async def funnel_counts(
    session: AsyncSession,
    assignee_ids: list[int] | None,
    *,
    include_archived: bool = True,
) -> dict[str, int]:
    if assignee_ids is not None and len(assignee_ids) == 0:
        return {k: 0 for k in FUNNEL_API_KEYS}
    q: Select[tuple[str, int]] = (
        select(SalesOutboundContact.workflow_status, func.count(SalesOutboundContact.id))
        .where(SalesOutboundContact.assignee_id.is_not(None))
        .group_by(SalesOutboundContact.workflow_status)
    )
    if not include_archived:
        q = q.where(SalesOutboundContact.archived_at.is_(None))
    if assignee_ids is not None:
        q = q.where(SalesOutboundContact.assignee_id.in_(assignee_ids))
    rows = (await session.execute(q)).all()
    raw: dict[str, int] = {}
    for st, cnt in rows:
        raw[str(st)] = int(cnt)
    return {
        "in_base": raw.get("new", 0),
        "called": raw.get("in_progress", 0),
        "demo": raw.get("demo", 0),
        "closed": raw.get("closed", 0),
        "rejected": raw.get("rejected", 0),
        "hesitating": raw.get("hesitating", 0),
    }


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
    previous = (contact.workflow_status or "new").strip().lower()
    contact.workflow_status = new_status
    if new_status != "new" and contact.called_at is None:
        contact.called_at = now
    if new_status in ("demo", "closed") and contact.demo_at is None:
        contact.demo_at = now
    if new_status == "closed" and contact.closed_at is None:
        contact.closed_at = now
    archive_if_worked(contact, previous_status=previous, now=now)
    contact.updated_at = now


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
    now = utc_now_naive()
    imported = 0
    for r in rows:
        session.add(
            SalesOutboundContact(
                assignee_id=None,
                workflow_status="new",
                org_name=r["org_name"][:512],
                lpr_name=r.get("lpr_name"),
                lpr_phone=r.get("lpr_phone"),
                org_phone=r.get("org_phone"),
                org_mobile=r.get("org_mobile"),
                import_status=r.get("import_status"),
                email=r.get("email"),
                website=r.get("website"),
                extra_json=extras_to_json(r.get("extras") or {}),
                created_at=now,
                updated_at=now,
            )
        )
        imported += 1
    await session.commit()
    return imported, 0
