"""Портал отдела продаж: логин, рабочий стол, API для РОП."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select

from ..alembic.database import async_session_maker
from ..alembic.models import SalesOutboundContact, SalesTeamMember
from ..config import settings
from ..services.internal_sales import (
    contact_to_api_dict,
    funnel_counts,
    import_contacts_from_excel,
    member_public_dict,
    monthly_done_counts,
    month_start_utc_naive,
    subtree_member_ids,
    apply_workflow_timestamps,
    utc_now_naive,
    WORKFLOW_STATUSES,
)
from ..services.sales_invoice_docx import build_contact_invoice_docx
from ..utils.JWT import create_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash, verify_password
from .deps import SalesAuthContext, get_sales_auth, require_sales_rop
from .schemas import SalesContactUpdate, SalesLoginRequest, SalesTeamMemberCreate, SalesTeamMemberUpdate


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
        member = await session.get(SalesTeamMember, auth.staff_id)
        if not member or not member.is_active:
            raise HTTPException(status_code=401, detail="Не авторизован")
        done = await monthly_done_counts(session, member.id, ms)
        funnel = await funnel_counts(session, [member.id])
        backlog = await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(
                SalesOutboundContact.assignee_id == member.id,
                SalesOutboundContact.workflow_status == "new",
            )
        )
    return JSONResponse(
        content={
            "member": member_public_dict(member),
            "plan": {
                "calls_monthly": member.plan_calls_monthly,
                "demos_monthly": member.plan_demos_monthly,
                "closes_monthly": member.plan_closes_monthly,
                "daily_contacts_quota": member.daily_contacts_quota,
            },
            "achievement_month": done,
            "funnel_assigned": funnel,
            "backlog_in_base": int(backlog or 0),
        }
    )


@router.get("/contacts")
async def sales_list_contacts(
    auth: SalesAuthContext = Depends(get_sales_auth),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with async_session_maker() as session:
        total = await session.scalar(
            select(func.count(SalesOutboundContact.id)).where(SalesOutboundContact.assignee_id == auth.staff_id)
        )
        q = (
            select(SalesOutboundContact)
            .where(SalesOutboundContact.assignee_id == auth.staff_id)
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
        if not contact or contact.assignee_id != auth.staff_id:
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
    return JSONResponse(content={"status": "ok"})


@router.get("/contacts/{contact_id}/invoice")
async def sales_download_invoice(
    contact_id: int,
    auth: SalesAuthContext = Depends(get_sales_auth),
):
    async with async_session_maker() as session:
        contact = await session.get(SalesOutboundContact, contact_id)
        if not contact or contact.assignee_id != auth.staff_id:
            raise HTTPException(status_code=404, detail="Контакт не найден")
        data = build_contact_invoice_docx(contact)
    filename = f"schet_{contact_id}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        total = await funnel_counts(session, visible)
        by_member = []
        for mid in sorted(visible):
            m = await session.get(SalesTeamMember, mid)
            if not m or not m.is_active:
                continue
            fc = await funnel_counts(session, [mid])
            by_member.append({"member": member_public_dict(m), "funnel": fc})
    return JSONResponse(content={"total": total, "by_member": by_member})


@management_router.post(
    "/contacts/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="rop_sales_upload"))],
)
async def rop_sales_excel_upload(
    auth: SalesAuthContext = Depends(require_sales_rop),
    assignee_id: int = Form(...),
    file: UploadFile = File(...),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    async with async_session_maker() as session:
        visible = await _rop_visible_member_ids(session, auth.staff_id)
        if assignee_id not in visible:
            raise HTTPException(status_code=400, detail="Некорректный сотрудник")
        assignee = await session.get(SalesTeamMember, assignee_id)
        if not assignee or not assignee.is_active:
            raise HTTPException(status_code=400, detail="Сотрудник не найден")
        try:
            imported, _skipped = await import_contacts_from_excel(session, assignee_id=assignee_id, file_bytes=raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"imported": imported, "message": f"Импортировано строк: {imported}"},
    )
