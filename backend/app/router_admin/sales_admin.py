"""Админские эндпоинты отдела продаж: /api/admin/sales/*"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import SalesOutboundContact, SalesTeamMember
from ..router_sales.schemas import SalesTeamMemberCreate, SalesTeamMemberUpdate
from ..services.internal_sales import (
    apply_role_default_quota,
    clear_sales_crm_data,
    funnel_counts,
    import_contacts_from_excel,
    member_public_dict,
    pool_contacts_count,
    utc_now_naive,
)
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash
from .router import get_current_admin


router = APIRouter(prefix="/sales", tags=["admin-sales"])


class SalesContactManualCreate(BaseModel):
    org_name: str = Field("", max_length=512)
    label: str = Field("", max_length=256)  # совместимость со старым полем «Подпись»


async def _all_active_member_ids(session) -> list[int]:
    rows = (
        await session.scalars(select(SalesTeamMember.id).where(SalesTeamMember.is_active.is_(True)))
    ).all()
    return [int(r) for r in rows]


@router.get("/team-members")
async def admin_sales_list_team(_admin=Depends(get_current_admin)):
    async with async_session_maker() as session:
        members = (
            await session.scalars(
                select(SalesTeamMember)
                .where(SalesTeamMember.is_active.is_(True))
                .order_by(SalesTeamMember.id)
            )
        ).all()
        items = []
        for m in members:
            fc = await funnel_counts(session, [m.id])
            items.append(member_public_dict(m, funnel=fc))
    return JSONResponse(content={"items": items})


@router.post("/team-members", dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="admin_sales"))])
async def admin_sales_create_member(payload: SalesTeamMemberCreate, _admin=Depends(get_current_admin)):
    login = payload.login.strip()
    if payload.role == "rop" and payload.supervisor_id is not None:
        raise HTTPException(status_code=400, detail="У руководителя отдела не должно быть руководителя")
    async with async_session_maker() as session:
        exists = await session.scalar(select(SalesTeamMember.id).where(SalesTeamMember.login == login))
        if exists:
            raise HTTPException(status_code=409, detail="Логин уже занят")
        if payload.supervisor_id is not None:
            sup = await session.get(SalesTeamMember, payload.supervisor_id)
            if not sup or not sup.is_active:
                raise HTTPException(status_code=400, detail="Руководитель не найден")
        row = SalesTeamMember(
            login=login,
            password_hash=get_password_hash(payload.password),
            role=payload.role,
            supervisor_id=payload.supervisor_id,
            is_active=True,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        apply_role_default_quota(row)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"id": row.id, "login": row.login, "role": row.role},
    )


@router.patch("/team-members/{member_id}", dependencies=[Depends(rate_limit(max_requests=60, window_seconds=60, scope="admin_sales"))])
async def admin_sales_update_member(
    member_id: int,
    payload: SalesTeamMemberUpdate,
    _admin=Depends(get_current_admin),
):
    async with async_session_maker() as session:
        row = await session.get(SalesTeamMember, member_id)
        if not row:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        data = payload.model_dump(exclude_unset=True)
        if "password" in data and data["password"]:
            row.password_hash = get_password_hash(data.pop("password"))
        if "supervisor_id" in data:
            new_sup = data["supervisor_id"]
            if row.role == "rop" and new_sup is not None:
                raise HTTPException(status_code=400, detail="РОП не может иметь руководителя")
            if new_sup is not None:
                if new_sup == member_id:
                    raise HTTPException(status_code=400, detail="Некорректный руководитель")
                sup = await session.get(SalesTeamMember, new_sup)
                if not sup or not sup.is_active:
                    raise HTTPException(status_code=400, detail="Руководитель не найден")
            row.supervisor_id = new_sup
            data.pop("supervisor_id", None)
        for field in ("is_active", "plan_calls_monthly", "plan_demos_monthly", "plan_closes_monthly", "daily_contacts_quota"):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])
        row.updated_at = utc_now_naive()
        await session.commit()
    return JSONResponse(content={"status": "ok"})


@router.get("/funnel")
async def admin_sales_funnel(_admin=Depends(get_current_admin)):
    async with async_session_maker() as session:
        mids = await _all_active_member_ids(session)
        total = await funnel_counts(session, mids if mids else None)
        pool_size = await pool_contacts_count(session)
        by_member = []
        for mid in mids:
            m = await session.get(SalesTeamMember, mid)
            if not m:
                continue
            fc = await funnel_counts(session, [mid])
            by_member.append({"member": member_public_dict(m), "funnel": fc})
    return JSONResponse(content={"total": total, "by_member": by_member, "crm_pool_available": pool_size})


@router.post(
    "/contacts/manual",
    dependencies=[Depends(rate_limit(max_requests=120, window_seconds=60, scope="admin_sales_contacts"))],
)
async def admin_sales_add_contact_manual(payload: SalesContactManualCreate, _admin=Depends(get_current_admin)):
    now = utc_now_naive()
    raw_name = (payload.org_name or payload.label or "").strip() or "Контакт без названия"
    async with async_session_maker() as session:
        row = SalesOutboundContact(
            assignee_id=None,
            workflow_status="new",
            org_name=raw_name[:512],
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        pool_size = await pool_contacts_count(session)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"id": row.id, "crm_pool_available": pool_size},
    )


@router.post(
    "/contacts/clear",
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, scope="admin_sales_clear"))],
)
async def admin_sales_clear_crm(_admin=Depends(get_current_admin)):
    async with async_session_maker() as session:
        async with session.begin():
            await clear_sales_crm_data(session)
        pool_size = await pool_contacts_count(session)
    return JSONResponse(
        content={
            "status": "ok",
            "message": "Локальная CRM очищена (контакты удалены, счётчики дневной выдачи сброшены).",
            "crm_pool_available": pool_size,
        },
    )


@router.post(
    "/contacts/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="admin_sales_upload"))],
)
async def admin_sales_excel_upload(
    _admin=Depends(get_current_admin),
    file: UploadFile = File(...),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    async with async_session_maker() as session:
        try:
            imported, _skipped = await import_contacts_from_excel(session, file_bytes=raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        pool_size = await pool_contacts_count(session)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "imported": imported,
            "crm_pool_available": pool_size,
            "message": f"В общую базу добавлено: {imported}. Свободно в пуле: {pool_size}",
        },
    )
