"""Sasha AI autodial routes for /custom automations."""
import json
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from .dependencies import get_current_custom_automation
from .schemas import (
    SashaAiCallListResponse,
    SashaAiCallResponse,
    SashaAiConnectionResponse,
    SashaAiConnectionUpdate,
    SashaAiPushResponse,
    SashaAiWebhookResponse,
)
from ..alembic.database import async_session_maker
from ..alembic.models import CustomAutomation, CustomLead
from ..services.custom.sasha_ai_service import (
    apply_sasha_settings,
    ensure_sasha_webhook_secret,
    handle_sasha_webhook,
    list_sasha_calls,
    push_lead_to_sasha,
    push_pending_leads,
    rotate_sasha_webhook_secret,
    sasha_settings_payload,
    sasha_stats,
    sasha_webhook_secret_ok,
    serialize_sasha_call,
    verify_sasha_hmac,
)

router = APIRouter()


def _connection_response(automation: CustomAutomation) -> SashaAiConnectionResponse:
    return SashaAiConnectionResponse(**sasha_settings_payload(automation))


@router.get("/automations/{automation_id}/sasha", response_model=SashaAiCallListResponse)
async def list_automation_sasha_calls(
    automation_id: int,
    outcome: Optional[str] = None,
    lead_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        items, total = await list_sasha_calls(
            session,
            automation_id,
            outcome=outcome,
            lead_id=lead_id,
            limit=limit,
            offset=offset,
        )
        stats = await sasha_stats(session, automation_id)
        return SashaAiCallListResponse(
            items=[SashaAiCallResponse(**serialize_sasha_call(row)) for row in items],
            total=total,
            stats=stats,
        )


@router.get("/automations/{automation_id}/sasha/connection", response_model=SashaAiConnectionResponse)
async def get_sasha_connection(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        if db_automation.is_sasha_ai_enabled or db_automation.sasha_upload_url:
            ensure_sasha_webhook_secret(db_automation)
            await session.commit()
            await session.refresh(db_automation)
        return _connection_response(db_automation)


@router.put("/automations/{automation_id}/sasha/connection", response_model=SashaAiConnectionResponse)
async def save_sasha_connection(
    automation_id: int,
    payload: SashaAiConnectionUpdate,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        try:
            apply_sasha_settings(db_automation, payload.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        await session.commit()
        await session.refresh(db_automation)
        return _connection_response(db_automation)


@router.post("/automations/{automation_id}/sasha/webhook-secret/rotate", response_model=SashaAiConnectionResponse)
async def rotate_sasha_secret(
    automation_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        if not db_automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        rotate_sasha_webhook_secret(db_automation)
        await session.commit()
        await session.refresh(db_automation)
        return _connection_response(db_automation)


@router.post("/automations/{automation_id}/sasha/push", response_model=SashaAiPushResponse)
async def push_pending_to_sasha(
    automation_id: int,
    background_tasks: BackgroundTasks,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    background_tasks.add_task(push_pending_leads, automation_id)
    return SashaAiPushResponse(status="started")


@router.post("/automations/{automation_id}/leads/{lead_id}/sasha/push", response_model=SashaAiPushResponse)
async def push_lead_to_sasha_now(
    automation_id: int,
    lead_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        db_automation = await session.get(CustomAutomation, automation_id)
        lead = await session.get(CustomLead, lead_id)
        if not db_automation or not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        if lead.sasha_status in {"uploaded", "called", "connected", "committed"}:
            lead.sasha_status = "queued"
            await session.commit()
        result = await push_lead_to_sasha(session, db_automation, lead)
        return SashaAiPushResponse(
            status=str(result.get("status") or "ok"),
            lead_id=lead_id,
            error=result.get("error"),
            message=result.get("message") or result.get("skipped_reason"),
        )


@router.get("/automations/{automation_id}/leads/{lead_id}/sasha", response_model=SashaAiCallListResponse)
async def list_lead_sasha_calls(
    automation_id: int,
    lead_id: int,
    automation: CustomAutomation = Depends(get_current_custom_automation),
):
    async with async_session_maker() as session:
        lead = await session.get(CustomLead, lead_id)
        if not lead or lead.custom_automation_id != automation_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        items, total = await list_sasha_calls(session, automation_id, lead_id=lead_id, limit=100, offset=0)
        return SashaAiCallListResponse(
            items=[SashaAiCallResponse(**serialize_sasha_call(row)) for row in items],
            total=total,
            stats={},
        )


async def _accept_sasha_webhook(automation_id: int, request: Request, path_secret: str) -> SashaAiWebhookResponse:
    raw = await request.body()
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
        if not sasha_webhook_secret_ok(automation, path_secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Sasha webhook secret")
        hmac_secret = (automation.sasha_hmac_secret or "").strip()
        if hmac_secret:
            signature = request.headers.get("X-Webhook-Signature") or request.headers.get("x-webhook-signature")
            if not verify_sasha_hmac(raw, signature, hmac_secret):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Sasha HMAC signature")
        try:
            payload: Any = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expected a JSON object")
        result = await handle_sasha_webhook(session, automation, payload)
        return SashaAiWebhookResponse(**result)


@router.post("/webhooks/sasha/{automation_id}/{secret}", response_model=SashaAiWebhookResponse)
async def sasha_public_webhook(automation_id: int, secret: str, request: Request):
    return await _accept_sasha_webhook(automation_id, request, secret)
