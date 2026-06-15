"""Админские эндпоинты ИИ МОП: /api/admin/ai-mop/*"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..alembic.database import async_session_maker
from ..services.ai_mop.lead_import import import_ai_mop_leads_from_excel
from ..services.ai_mop.service import (
    assign_agent_to_ai_mop,
    clear_ai_mop_leads,
    get_dashboard_stats,
    list_errors,
    list_leads,
    list_sales_manager_agents_with_assignment,
    set_agent_ai_mop_enabled,
    unassign_agent_from_ai_mop,
)
from ..utils.rate_limit import rate_limit
from .router import get_current_admin


router = APIRouter(prefix="/ai-mop", tags=["admin-ai-mop"])


class AiMopAssignRequest(BaseModel):
    enabled: bool = True


class AiMopEnableRequest(BaseModel):
    enabled: bool


@router.get("/dashboard")
async def ai_mop_dashboard(_admin=Depends(get_current_admin)):
    stats = await get_dashboard_stats()
    return JSONResponse(content=stats)


@router.get("/agents")
async def ai_mop_list_agents(_admin=Depends(get_current_admin)):
    items = await list_sales_manager_agents_with_assignment()
    return JSONResponse(content={"items": items})


@router.post(
    "/agents/{agent_id}/assign",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="admin_ai_mop"))],
)
async def ai_mop_assign_agent(
    agent_id: int,
    payload: AiMopAssignRequest,
    _admin=Depends(get_current_admin),
):
    try:
        result = await assign_agent_to_ai_mop(agent_id=agent_id, enabled=payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JSONResponse(content=result, status_code=status.HTTP_200_OK)


@router.delete(
    "/agents/{agent_id}/assign",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="admin_ai_mop"))],
)
async def ai_mop_unassign_agent(agent_id: int, _admin=Depends(get_current_admin)):
    await unassign_agent_from_ai_mop(agent_id=agent_id)
    return JSONResponse(content={"ok": True})


@router.patch(
    "/agents/{agent_id}",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="admin_ai_mop"))],
)
async def ai_mop_toggle_agent(agent_id: int, payload: AiMopEnableRequest, _admin=Depends(get_current_admin)):
    try:
        await set_agent_ai_mop_enabled(agent_id=agent_id, enabled=payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JSONResponse(content={"agent_id": agent_id, "enabled": payload.enabled})


@router.get("/errors")
async def ai_mop_list_errors(
    _admin=Depends(get_current_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stage: str | None = Query(None),
):
    data = await list_errors(page=page, page_size=page_size, stage=stage)
    return JSONResponse(content=data)


@router.get("/leads")
async def ai_mop_list_leads(
    _admin=Depends(get_current_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    data = await list_leads(page=page, page_size=page_size, status=status)
    return JSONResponse(content=data)


@router.post(
    "/leads/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="admin_ai_mop"))],
)
async def ai_mop_upload_leads(
    file: UploadFile = File(...),
    _admin=Depends(get_current_admin),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 15 МБ)")
    async with async_session_maker() as session:
        async with session.begin():
            result = await import_ai_mop_leads_from_excel(session, file_bytes=raw)
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.post(
    "/leads/clear",
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, scope="admin_ai_mop"))],
)
async def ai_mop_clear_leads(
    _admin=Depends(get_current_admin),
    only_pending: bool = Query(True),
):
    deleted = await clear_ai_mop_leads(only_pending=only_pending)
    return JSONResponse(content={"deleted": deleted})
