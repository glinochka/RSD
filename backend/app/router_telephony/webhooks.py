"""Simplified telephony webhooks - integrates with Voximplant native TTS + ASR."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..alembic.database import async_session_maker
from ..alembic.models import AgentTelephonyCall
from ..config import settings
from ..telephony.simplified_orchestrator import get_simplified_orchestrator
from ..services.telephony_orchestrator import handle_orchestrator_event, OrchestratorEventType, CallDialogContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telephony-webhooks"])

# Secret validation
EXPECTED_SECRET = (getattr(settings, "RSD_WEBHOOK_SECRET", None) or "").strip()


def validate_webhook_secret(provided: str | None) -> None:
    """Validate webhook signature header."""
    if not EXPECTED_SECRET:
        logger.warning("telephony_webhook: RSD_WEBHOOK_SECRET not configured")
        return

    if not provided:
        raise HTTPException(status_code=401, detail="Missing webhook secret")

    if provided.strip() != EXPECTED_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


# Request/Response models
class CallInboundPayload(BaseModel):
    caller_e164: str = ""
    called_e164: str | None = None


class CallInboundRequest(BaseModel):
    call_id: str
    connection_id: int
    caller_e164: str
    called_e164: str | None = None
    event: str
    payload: CallInboundPayload = Field(default_factory=CallInboundPayload)


class CallAnsweredPayload(BaseModel):
    extension: str | None = None


class CallAnsweredRequest(BaseModel):
    call_id: str
    connection_id: int
    caller_e164: str
    event: str
    payload: CallAnsweredPayload = Field(default_factory=CallAnsweredPayload)


class AsrResultPayload(BaseModel):
    transcript: str
    confidence: float = 0.0


class AsrResultRequest(BaseModel):
    call_id: str
    connection_id: int
    caller_e164: str
    event: str
    payload: AsrResultPayload


class HangupPayload(BaseModel):
    reason: str = "completed"


class HangupRequest(BaseModel):
    call_id: str
    event: str
    payload: HangupPayload = Field(default_factory=lambda: HangupPayload(reason="completed"))


class WebhookResponse(BaseModel):
    """Response to Voximplant with next action."""

    action: str = "say"  # say, transfer, hangup, enable_dtmf
    text: str = ""
    voice_id: str = "Tatyana"
    destination: str | None = None  # For transfer action
    greeting_text: str | None = None  # For call.inbound response


# Endpoints

@router.post("/webhook/call.inbound", response_model=WebhookResponse)
async def webhook_call_inbound(
    request: Request,
    x_rsd_secret: str | None = Header(None, alias="X-RSD-Secret"),
) -> WebhookResponse:
    """Handle incoming call from Voximplant.

    Returns greeting configuration and routing info.
    """
    validate_webhook_secret(x_rsd_secret)

    try:
        data = await request.json()
        req = CallInboundRequest(**data)
    except Exception as e:
        logger.warning("webhook_call_inbound: invalid request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid request body")

    logger.info(
        "webhook_call_inbound: call_id=%s connection_id=%s caller=%s",
        req.call_id,
        req.connection_id,
        req.caller_e164,
    )

    orch = get_simplified_orchestrator()
    result = await orch.handle_inbound(
        call_id=req.call_id,
        connection_id=req.connection_id,
        caller_e164=req.caller_e164,
        called_e164=req.called_e164 or req.payload.called_e164,
    )

    return WebhookResponse(
        greeting_text=result.get("greeting_text"),
        voice_id=result.get("voice_id", "Tatyana"),
    )


@router.post("/webhook/call.answered", response_model=WebhookResponse)
async def webhook_call_answered(
    request: Request,
    x_rsd_secret: str | None = Header(None, alias="X-RSD-Secret"),
) -> WebhookResponse:
    """Handle call answered event from Voximplant.

    Called after Early Media / greeting. May include DTMF extension.
    """
    validate_webhook_secret(x_rsd_secret)

    try:
        data = await request.json()
        req = CallAnsweredRequest(**data)
    except Exception as e:
        logger.warning("webhook_call_answered: invalid request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid request body")

    logger.info(
        "webhook_call_answered: call_id=%s connection_id=%s extension=%s",
        req.call_id,
        req.connection_id,
        req.payload.extension,
    )

    orch = get_simplified_orchestrator()
    result = await orch.handle_call_answered(
        call_id=req.call_id,
        connection_id=req.connection_id,
        caller_e164=req.caller_e164,
        extension=req.payload.extension,
    )

    if result:
        return WebhookResponse(
            action=result.get("action", "say"),
            text=result.get("text", ""),
            voice_id=result.get("voice_id", "Tatyana"),
            destination=result.get("destination"),
        )

    # No immediate action needed - VoxEngine will start ASR
    return WebhookResponse(action="continue")


@router.post("/webhook/asr.result", response_model=WebhookResponse)
async def webhook_asr_result(
    request: Request,
    x_rsd_secret: str | None = Header(None, alias="X-RSD-Secret"),
) -> WebhookResponse:
    """Handle ASR result from Voximplant.

    Process user speech and return next action (say/transfer/hangup).
    """
    validate_webhook_secret(x_rsd_secret)

    try:
        data = await request.json()
        req = AsrResultRequest(**data)
    except Exception as e:
        logger.warning("webhook_asr_result: invalid request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid request body")

    transcript = req.payload.transcript.strip()
    if not transcript:
        logger.debug("webhook_asr_result: empty transcript for call_id=%s", req.call_id)
        return WebhookResponse(
            action="say",
            text="Прошу прощения, не расслышал. Повторите, пожалуйста.",
        )

    logger.info(
        "webhook_asr_result: call_id=%s transcript_len=%s",
        req.call_id,
        len(transcript),
    )

    orch = get_simplified_orchestrator()
    result = await orch.handle_asr_result(
        call_id=req.call_id,
        connection_id=req.connection_id,
        caller_e164=req.caller_e164,
        transcript=transcript,
        confidence=req.payload.confidence,
    )

    return WebhookResponse(
        action=result.get("action", "say"),
        text=result.get("text", ""),
        voice_id=result.get("voice_id", "Tatyana"),
        destination=result.get("destination"),
    )


@router.post("/webhook/call.hangup")
async def webhook_call_hangup(
    request: Request,
    x_rsd_secret: str | None = Header(None, alias="X-RSD-Secret"),
) -> dict[str, Any]:
    """Handle call hangup event from Voximplant."""
    validate_webhook_secret(x_rsd_secret)

    try:
        data = await request.json()
        req = HangupRequest(**data)
    except Exception as e:
        logger.warning("webhook_call_hangup: invalid request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid request body")

    logger.info(
        "webhook_call_hangup: call_id=%s reason=%s",
        req.call_id,
        req.payload.reason,
    )

    orch = get_simplified_orchestrator()
    await orch.handle_hangup(req.call_id)

    return {"ok": True}


@router.get("/response/next")
async def poll_next_response(
    call_id: str,
    connection_id: int,
    x_rsd_secret: str | None = Header(None, alias="X-RSD-Secret"),
) -> WebhookResponse:
    """Poll for next response (for future async support).

    Currently returns immediately if response is ready,
    or empty response if nothing pending.
    """
    validate_webhook_secret(x_rsd_secret)

    orch = get_simplified_orchestrator()
    result = await orch.get_next_response(call_id)

    if result:
        return WebhookResponse(
            action=result.get("action", "say"),
            text=result.get("text", ""),
            voice_id=result.get("voice_id", "Tatyana"),
            destination=result.get("destination"),
        )

    # No response ready - VoxEngine should continue with ASR
    raise HTTPException(status_code=204, detail="No response ready")
