"""Админские эндпоинты отдела продаж: /api/admin/sales/*"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import SalesTeamMember
from ..router_sales.schemas import SalesTeamMemberCreate, SalesTeamMemberUpdate
from ..services.internal_sales import (
    add_contact_to_pool,
    apply_role_default_quota,
    apply_sales_team_member_update,
    clear_sales_crm_data,
    funnel_counts,
    funnel_counts_by_members,
    import_contacts_from_excel,
    member_public_dict,
    normalize_funnel_period,
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
    lpr_name: str | None = Field(None, max_length=256)
    lpr_phone: str | None = Field(None, max_length=256)
    org_phone: str | None = Field(None, max_length=256)
    org_mobile: str | None = Field(None, max_length=256)
    email: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=512)


async def _all_active_member_ids(session) -> list[int]:
    rows = (
        await session.scalars(select(SalesTeamMember.id).where(SalesTeamMember.is_active.is_(True)))
    ).all()
    return [int(r) for r in rows]


@router.get("/team-members")
async def admin_sales_list_team(
    _admin=Depends(get_current_admin),
    include_inactive: bool = Query(False),
):
    async with async_session_maker() as session:
        q = select(SalesTeamMember).order_by(SalesTeamMember.id)
        if not include_inactive:
            q = q.where(SalesTeamMember.is_active.is_(True))
        members = (await session.scalars(q)).all()
        member_ids = [m.id for m in members]
        funnels = await funnel_counts_by_members(session, member_ids, period="all")
        items = [
            member_public_dict(m, funnel=funnels.get(m.id))
            for m in members
        ]
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
            data["supervisor_id"] = new_sup
        try:
            await apply_sales_team_member_update(session, row, data, member_id=member_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        await session.commit()
    return JSONResponse(content={"status": "ok"})


@router.get("/funnel")
async def admin_sales_funnel(
    _admin=Depends(get_current_admin),
    period: str = Query("all", description="day | week | month | all"),
):
    try:
        funnel_period = normalize_funnel_period(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    async with async_session_maker() as session:
        mids = await _all_active_member_ids(session)
        total = await funnel_counts(session, mids if mids else None, period=funnel_period)
        pool_size = await pool_contacts_count(session)
        funnels = await funnel_counts_by_members(session, mids, period=funnel_period)
        by_member = []
        for mid in mids:
            m = await session.get(SalesTeamMember, mid)
            if not m:
                continue
            by_member.append({"member": member_public_dict(m), "funnel": funnels.get(mid)})
    return JSONResponse(
        content={
            "period": funnel_period,
            "total": total,
            "by_member": by_member,
            "crm_pool_available": pool_size,
        }
    )


@router.post(
    "/contacts/manual",
    dependencies=[Depends(rate_limit(max_requests=120, window_seconds=60, scope="admin_sales_contacts"))],
)
async def admin_sales_add_contact_manual(payload: SalesContactManualCreate, _admin=Depends(get_current_admin)):
    raw_name = (payload.org_name or payload.label or "").strip() or "Контакт без названия"

    def _opt(field: str | None) -> str | None:
        if field is None:
            return None
        s = field.strip()
        return s or None

    async with async_session_maker() as session:
        row, skipped = await add_contact_to_pool(
            session,
            org_name=raw_name,
            lpr_name=_opt(payload.lpr_name),
            lpr_phone=_opt(payload.lpr_phone),
            org_phone=_opt(payload.org_phone),
            org_mobile=_opt(payload.org_mobile),
            email=_opt(payload.email),
            website=_opt(payload.website),
        )
        if skipped:
            raise HTTPException(status_code=409, detail="Такой контакт уже есть в активной CRM")
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
            imported, skipped = await import_contacts_from_excel(session, file_bytes=raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        pool_size = await pool_contacts_count(session)
    msg = f"В общую базу добавлено: {imported}. Свободно в пуле: {pool_size}"
    if skipped:
        msg += f". Пропущено дублей: {skipped}"
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "imported": imported,
            "skipped_duplicates": skipped,
            "crm_pool_available": pool_size,
            "message": msg,
        },
    )
