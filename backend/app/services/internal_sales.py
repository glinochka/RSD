"""Логика внутреннего отдела продаж (не агентский sales FSM)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import SalesOutboundContact, SalesTeamMember

WORKFLOW_STATUSES = frozenset({"new", "in_progress", "demo", "closed", "rejected", "hesitating"})

FUNNEL_API_KEYS = ("in_base", "called", "demo", "closed", "rejected", "hesitating")


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def month_start_utc_naive(now: datetime | None = None) -> datetime:
    n = now or utc_now_naive()
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


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
) -> dict[str, int]:
    if assignee_ids is not None and len(assignee_ids) == 0:
        return {k: 0 for k in FUNNEL_API_KEYS}
    q: Select[tuple[str, int]] = (
        select(SalesOutboundContact.workflow_status, func.count(SalesOutboundContact.id))
        .group_by(SalesOutboundContact.workflow_status)
    )
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
    contact.workflow_status = new_status
    if new_status != "new" and contact.called_at is None:
        contact.called_at = now
    if new_status in ("demo", "closed") and contact.demo_at is None:
        contact.demo_at = now
    if new_status == "closed" and contact.closed_at is None:
        contact.closed_at = now
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
        "called_at": r.called_at.isoformat() if r.called_at else None,
        "demo_at": r.demo_at.isoformat() if r.demo_at else None,
        "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def import_contacts_from_excel(
    session: AsyncSession,
    *,
    assignee_id: int,
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
                assignee_id=assignee_id,
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
