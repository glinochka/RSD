"""Портал отдела продаж: логин, рабочий стол, API для РОП."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select

from ..alembic.database import async_session_maker
from ..alembic.models import SalesOutboundContact, SalesTeamMember
from ..config import settings
from ..services.internal_sales import (
    apply_role_default_quota,
    contact_to_api_dict,
    effective_daily_quota,
    ensure_daily_allocation,
    funnel_counts,
    import_contacts_from_excel,
    member_public_dict,
    monthly_done_counts,
    month_start_utc_naive,
    pending_new_count,
    pool_contacts_count,
    request_more_contacts,
    subtree_member_ids,
    apply_workflow_timestamps,
    utc_now_naive,
    WORKFLOW_STATUSES,
    ALLOCATABLE_ROLES,
)
from ..services.sales_moy_nalog_invoice import (
    create_contact_receipt_pdf,
    moy_nalog_configured,
    persist_receipt_metadata,
)
from ..utils.JWT import create_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash, verify_password
from .deps import SalesAuthContext, get_sales_auth, require_sales_rop
from .schemas import (
    SalesContactUpdate,
    SalesInvoiceCreate,
    SalesLoginRequest,
    SalesTeamMemberCreate,
    SalesTeamMemberUpdate,
)


router = APIRouter(tags=["sales-portal"])
management_router = APIRouter(tags=["sales-management"])


@router.post("/login", dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, scope="sales_login"))])
async def sales_login(payload: SalesLoginRequest):
    login = payload.login.strip()
    async with async_session_maker() as session:
        member = await session.scalar(select(SalesTeamMember).where(SalesTeamMember.login == login))
        if not member or not member.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
        if not member.password_hash or not verify_password(payload.password, member.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
        token = create_access_token(
            {"sales_staff_id": member.id, "role": member.role},
            token_kind="sales_staff",
        )
    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "bearer",
            "expires_in_hours": settings.SALES_STAFF_TOKEN_EXPIRE_HOURS,
        }
    )


@router.get("/me")
async def sales_me(auth: SalesAuthContext = Depends(get_sales_auth)):
    ms = month_start_utc_naive()
    async with async_session_maker() as session:
        async with session.begin():
            member = await session.get(SalesTeamMember, auth.staff_id)
            if not member or not member.is_active:
                raise HTTPException(status_code=401, detail="Не авторизован")
            daily_allocated = 0
            if (member.role or "").strip().lower() in ALLOCATABLE_ROLES:
                daily_allocated = await ensure_daily_allocation(session, member)
            done = await monthly_done_counts(session, member.id, ms)
            funnel = await funnel_counts(session, [member.id])
            pending = await pending_new_count(session, member.id)
            pool_size = await pool_contacts_count(session)
        backlog = pending
    role = (member.role or "").strip().lower()
    return JSONResponse(
        content={
            "member": member_public_dict(member),
            "plan": {
                "calls_monthly": member.plan_calls_monthly,
                "demos_monthly": member.plan_demos_monthly,
                "closes_monthly": member.plan_closes_monthly,
                "daily_contacts_quota": member.daily_contacts_quota,
                "effective_daily_quota": effective_daily_quota(member),
            },
            "achievement_month": done,
            "funnel_assigned": funnel,
            "backlog_in_base": backlog,
            "crm_pool_available": pool_size,
            "pending_new_contacts": pending,
            "can_request_more": role in ALLOCATABLE_ROLES and pending == 0 and pool_size > 0,
            "daily_allocated_now": daily_allocated,
        }
    )


@router.get("/contacts")
async def sales_list_contacts(
    auth: SalesAuthContext = Depends(get_sales_auth),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with async_session_maker() as session:
        async with session.begin():
            member = await session.get(SalesTeamMember, auth.staff_id)
            if not member or not member.is_active:
                raise HTTPException(status_code=401, detail="Не авторизован")
            if (member.role or "").strip().lower() in ALLOCATABLE_ROLES:
                await ensure_daily_allocation(session, member)
        base_filter = (
            SalesOutboundContact.assignee_id == auth.staff_id,
            SalesOutboundContact.archived_at.is_(None),
        )
        total = await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(*base_filter)
        )
        q = (
            select(SalesOutboundContact)
            .where(*base_filter)
            .order_by(SalesOutboundContact.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.scalars(q)).all()
        items = [contact_to_api_dict(r) for r in rows]
    pages = max(1, (int(total or 0) + page_size - 1) // page_size)
    return JSONResponse(
        content={"items": items, "page": page, "page_size": page_size, "total": int(total or 0), "total_pages": pages}
    )


@router.post(
    "/contacts/request-more",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="sales_request_more"))],
)
async def sales_request_more_contacts(auth: SalesAuthContext = Depends(get_sales_auth)):
    async with async_session_maker() as session:
        async with session.begin():
            member = await session.get(SalesTeamMember, auth.staff_id)
            if not member or not member.is_active:
                raise HTTPException(status_code=401, detail="Не авторизован")
            try:
                allocated = await request_more_contacts(session, member)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            await session.flush()
    return JSONResponse(
        content={
            "allocated": allocated,
            "message": f"Назначено контактов: {allocated}",
        }
    )


@router.patch("/contacts/{contact_id}")
async def sales_update_contact(
    contact_id: int,
    payload: SalesContactUpdate,
    auth: SalesAuthContext = Depends(get_sales_auth),
):
    now = utc_now_naive()
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    if "workflow_status" in data and data["workflow_status"] not in WORKFLOW_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус")
    async with async_session_maker() as session:
        contact = await session.get(SalesOutboundContact, contact_id)
        if (
            not contact
            or contact.assignee_id != auth.staff_id
            or contact.archived_at is not None
        ):
            raise HTTPException(status_code=404, detail="Контакт не найден")
        if "lpr_name" in data:
            v = data["lpr_name"]
            contact.lpr_name = (v.strip() if isinstance(v, str) else None) or None
        if "lpr_phone" in data:
            v = data["lpr_phone"]
            contact.lpr_phone = (v.strip() if isinstance(v, str) else None) or None
        if "comment" in data:
            v = data["comment"]
            contact.comment = v.strip() if isinstance(v, str) and v.strip() else None
        if "workflow_status" in data and data["workflow_status"] is not None:
            apply_workflow_timestamps(contact, data["workflow_status"], now)
        else:
            contact.updated_at = now
        await session.commit()
    return JSONResponse(content={"status": "ok", "archived": contact.archived_at is not None})


@router.post("/contacts/{contact_id}/invoice")
async def sales_create_invoice(
    contact_id: int,
    payload: SalesInvoiceCreate,
    auth: SalesAuthContext = Depends(get_sales_auth),
):
    if not moy_nalog_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Интеграция с «Мой налог» не настроена (MOY_NALOG_REFRESH_TOKEN или MOY_NALOG_INN + MOY_NALOG_PASSWORD)",
        )

    async with async_session_maker() as session:
        contact = await session.get(SalesOutboundContact, contact_id)
        if not contact or contact.assignee_id != auth.staff_id:
            raise HTTPException(status_code=404, detail="Контакт не найден")

        try:
            result = await asyncio.to_thread(
                create_contact_receipt_pdf,
                contact,
                amount_rub=payload.amount_rub,
                service_name=payload.service_name,
                client_inn=payload.client_inn,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        persist_receipt_metadata(contact, result)
        contact.updated_at = utc_now_naive()
        await session.commit()

    filename = f"chek_{contact_id}_{result.receipt_uuid[:8]}.pdf"
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Receipt-Uuid": result.receipt_uuid,
            "X-Receipt-Print-Url": result.print_url,
        },
    )


async def _rop_visible_member_ids(session, rop_id: int) -> set[int]:
    return await subtree_member_ids(session, rop_id)


@management_router.get("/team-members")
async def rop_sales_list_team(_auth: SalesAuthContext = Depends(require_sales_rop)):
    async with async_session_maker() as session:
        visible = await _rop_visible_member_ids(session, _auth.staff_id)
        if not visible:
            return JSONResponse(content={"items": []})
        members = (
            await session.scalars(
                select(SalesTeamMember)
                .where(SalesTeamMember.id.in_(visible), SalesTeamMember.is_active.is_(True))
                .order_by(SalesTeamMember.id)
            )
        ).all()
        items = []
        for m in members:
            fc = await funnel_counts(session, [m.id])
            items.append(member_public_dict(m, funnel=fc))
    return JSONResponse(content={"items": items})


@management_router.post(
    "/team-members",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="rop_sales"))],
)
async def rop_sales_create_member(payload: SalesTeamMemberCreate, auth: SalesAuthContext = Depends(require_sales_rop)):
    if payload.role == "rop":
        raise HTTPException(status_code=403, detail="РОП не может создавать других РОП")
    login = payload.login.strip()
    sup_id = payload.supervisor_id if payload.supervisor_id is not None else auth.staff_id
    async with async_session_maker() as session:
        visible = await _rop_visible_member_ids(session, auth.staff_id)
        if sup_id not in visible:
            raise HTTPException(status_code=400, detail="Некорректный руководитель")
        exists = await session.scalar(select(SalesTeamMember.id).where(SalesTeamMember.login == login))
        if exists:
            raise HTTPException(status_code=409, detail="Логин уже занят")
        row = SalesTeamMember(
            login=login,
            password_hash=get_password_hash(payload.password),
            role=payload.role,
            supervisor_id=sup_id,
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


@management_router.patch(
    "/team-members/{member_id}",
    dependencies=[Depends(rate_limit(max_requests=60, window_seconds=60, scope="rop_sales"))],
)
async def rop_sales_update_member(
    member_id: int,
    payload: SalesTeamMemberUpdate,
    auth: SalesAuthContext = Depends(require_sales_rop),
):
    if member_id == auth.staff_id:
        if payload.supervisor_id is not None or payload.is_active is False:
            raise HTTPException(status_code=400, detail="Нельзя отключить себя или назначить себе руководителя")
    async with async_session_maker() as session:
        visible = await _rop_visible_member_ids(session, auth.staff_id)
        if member_id not in visible:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        row = await session.get(SalesTeamMember, member_id)
        if not row:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")
        if row.role == "rop" and member_id != auth.staff_id:
            raise HTTPException(status_code=403, detail="Нельзя редактировать другого РОП")
        data = payload.model_dump(exclude_unset=True)
        if "password" in data and data["password"]:
            row.password_hash = get_password_hash(data.pop("password"))
        if "supervisor_id" in data:
            new_sup = data["supervisor_id"]
            if new_sup is not None:
                candidates = await _rop_visible_member_ids(session, auth.staff_id)
                if new_sup not in candidates:
                    raise HTTPException(status_code=400, detail="Некорректный руководитель")
                row.supervisor_id = new_sup
            else:
                row.supervisor_id = None
            data.pop("supervisor_id")
        for field in ("is_active", "plan_calls_monthly", "plan_demos_monthly", "plan_closes_monthly", "daily_contacts_quota"):
            if field in data and data[field] is not None:
                setattr(row, field, data[field])
        row.updated_at = utc_now_naive()
        await session.commit()
    return JSONResponse(content={"status": "ok"})


@management_router.get("/funnel")
async def rop_sales_funnel(auth: SalesAuthContext = Depends(require_sales_rop)):
    async with async_session_maker() as session:
        visible = list(await _rop_visible_member_ids(session, auth.staff_id))
        total = await funnel_counts(session, visible if visible else None)
        pool_size = await pool_contacts_count(session)
        by_member = []
        for mid in sorted(visible):
            m = await session.get(SalesTeamMember, mid)
            if not m or not m.is_active:
                continue
            fc = await funnel_counts(session, [mid])
            by_member.append({"member": member_public_dict(m), "funnel": fc})
    return JSONResponse(content={"total": total, "by_member": by_member, "crm_pool_available": pool_size})


@management_router.post(
    "/contacts/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="rop_sales_upload"))],
)
async def rop_sales_excel_upload(
    auth: SalesAuthContext = Depends(require_sales_rop),
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
