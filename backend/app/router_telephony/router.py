from __future__ import annotations



import logging



from fastapi import APIRouter, Depends, HTTPException, Request, status



from ..alembic.database import async_session_maker

from ..config import settings

from ..telephony.internal_auth import is_telephony_internal_request, require_telephony_internal

from ..telephony.metrics import snapshot as metrics_snapshot

from ..telephony.retention import purge_old_telephony_turns

from .schemas import (
    TelephonyCallEventRequest,
    TelephonyCallEventResponse,
    TelephonyCancelRequest,
    TelephonyCancelResponse,
    TelephonyMetricsResponse,
    TelephonyPartialRequest,
    TelephonyPartialResponse,
    TelephonyResolveRequest,
    TelephonyResolveResponse,
    TelephonyRetentionPurgeResponse,
    TelephonyTurnRequest,
    TelephonyTurnResponse,
    TelephonyWebhookAuthRequest,
    TelephonyWebhookAuthResponse,
)

from .cancel_handler import handle_telephony_cancel
from .partial_handler import handle_telephony_partial
from .service import get_webhook_auth, resolve_telephony_channel, upsert_call_event
from .turn_handler import handle_telephony_turn



logger = logging.getLogger(__name__)



router = APIRouter(prefix="/api/internal/telephony", tags=["telephony-internal"])





def _assert_telephony_enabled() -> None:

    if not settings.TELEPHONY_ENABLED:

        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail="Telephony is not enabled",

        )





@router.post("/webhook-auth", response_model=TelephonyWebhookAuthResponse)

async def telephony_webhook_auth(

    request: Request,

    payload: TelephonyWebhookAuthRequest,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)



    async with async_session_maker() as session:

        async with session.begin():

            data = await get_webhook_auth(session, payload.connection_id)

    return TelephonyWebhookAuthResponse(**data)





@router.post("/resolve", response_model=TelephonyResolveResponse)

async def telephony_resolve(

    request: Request,

    payload: TelephonyResolveRequest,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)



    async with async_session_maker() as session:

        async with session.begin():

            data = await resolve_telephony_channel(

                session,

                connection_id=payload.connection_id,

                caller_e164=payload.caller_e164,

            )

    return TelephonyResolveResponse(**data)





@router.post("/call-event", response_model=TelephonyCallEventResponse)

async def telephony_call_event(

    request: Request,

    payload: TelephonyCallEventRequest,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)



    async with async_session_maker() as session:

        async with session.begin():

            call, created = await upsert_call_event(

                session,

                connection_id=payload.connection_id,

                external_call_id=payload.external_call_id,

                caller_e164=payload.caller_e164,

                event=payload.event,

                status_override=payload.status,

                recording_url=payload.recording_url,

                duration_sec=payload.duration_sec,

                metadata=payload.metadata,

            )

    return TelephonyCallEventResponse(call_db_id=int(call.id), status=str(call.status), created=created)





@router.post("/cancel", response_model=TelephonyCancelResponse)
async def telephony_cancel(
    request: Request,
    payload: TelephonyCancelRequest,
    internal: bool = Depends(is_telephony_internal_request),
):
    _assert_telephony_enabled()
    await require_telephony_internal(request, internal)

    async with async_session_maker() as session:
        async with session.begin():
            return await handle_telephony_cancel(session, payload)


@router.post("/partial", response_model=TelephonyPartialResponse)
async def telephony_partial(
    request: Request,
    payload: TelephonyPartialRequest,
    internal: bool = Depends(is_telephony_internal_request),
):
    _assert_telephony_enabled()
    await require_telephony_internal(request, internal)

    async with async_session_maker() as session:
        async with session.begin():
            return await handle_telephony_partial(session, payload)


@router.post("/turn", response_model=TelephonyTurnResponse)

async def telephony_turn(

    request: Request,

    payload: TelephonyTurnRequest,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)



    async with async_session_maker() as session:

        async with session.begin():

            return await handle_telephony_turn(session, payload)





@router.get("/metrics", response_model=TelephonyMetricsResponse)

async def telephony_metrics(

    request: Request,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)

    data = metrics_snapshot(alert_p95_ms=int(settings.TELEPHONY_TURN_LATENCY_ALERT_P95_MS))

    return TelephonyMetricsResponse(**data)





@router.post("/retention/purge", response_model=TelephonyRetentionPurgeResponse)

async def telephony_retention_purge(

    request: Request,

    internal: bool = Depends(is_telephony_internal_request),

):

    _assert_telephony_enabled()

    await require_telephony_internal(request, internal)



    async with async_session_maker() as session:

        async with session.begin():

            result = await purge_old_telephony_turns(session)

    return TelephonyRetentionPurgeResponse(**result)


