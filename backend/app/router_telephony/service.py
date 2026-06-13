"""Telephony call persistence and channel resolution."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentChannelConnection, AgentTelephonyCall
from ..telephony import metrics as telephony_metrics
from ..telephony.constants import TELEPHONY_CALL_STATUSES
from ..telephony.credentials import TELEPHONY_CHANNEL_PROVIDER, parse_telephony_credentials
from ..telephony.logging import redact_telephony_log_message
from ..telephony.routing import (
    resolve_connection_by_called_number,
    routing_summary_for_call,
)
from ..telephony.session_cache import cache_call_mapping, cache_resolve_payload
from ..utils.crypto import decrypt_token

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _event_to_status(event: str, explicit: str | None) -> str:
    if explicit and explicit in TELEPHONY_CALL_STATUSES:
        return explicit
    mapping = {
        "call.inbound": "ringing",
        "call.answered": "active",
        "call.hangup": "completed",
    }
    return mapping.get(event, "active")


async def load_active_telephony_connection(
    session: AsyncSession,
    connection_id: int,
) -> AgentChannelConnection:
    row = await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.id == connection_id,
            AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
            AgentChannelConnection.is_active.is_(True),
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telephony channel not found")
    if not row.encrypted_credentials:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Telephony credentials missing")
    return row


async def get_webhook_auth(session: AsyncSession, connection_id: int) -> dict[str, Any]:
    connection = await load_active_telephony_connection(session, connection_id)
    try:
        creds = parse_telephony_credentials(decrypt_token(connection.encrypted_credentials))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid telephony credentials: {exc}",
        ) from exc
    return {
        "connection_id": int(connection.id),
        "webhook_secret": creds.webhook_secret,
        "phone_number_e164": creds.phone_number_e164,
        "is_active": bool(connection.is_active),
    }


async def resolve_inbound_connection(
    *,
    connection_id: int,
    called_e164: str | None = None,
    sip_from: str | None = None,
    sip_to: str | None = None,
) -> tuple[int, str]:
    """Map inbound SIP trunk (7C) or DID (B) to connection_id."""
    from ..telephony.routing import resolve_connection_by_sip_headers

    if sip_from or sip_to:
        routed = await resolve_connection_by_sip_headers(
            sip_from=sip_from,
            sip_to=sip_to,
            fallback_connection_id=connection_id,
        )
        if routed is not None:
            return routed, "sip"
    if called_e164:
        return await resolve_connection_by_called_number(
            called_e164,
            fallback_connection_id=connection_id,
        )
    return connection_id, "webhook"


async def resolve_telephony_channel(
    session: AsyncSession,
    *,
    connection_id: int,
    caller_e164: str,
    called_e164: str | None = None,
    routed_agent_id: int | None = None,
) -> dict[str, Any]:
    connection = await load_active_telephony_connection(session, connection_id)
    target_agent_id = int(routed_agent_id or connection.agent_id)
    agent = await session.scalar(select(Agent).where(Agent.id == target_agent_id, Agent.is_active.is_(True)))
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or inactive")

    try:
        creds = parse_telephony_credentials(decrypt_token(connection.encrypted_credentials))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid telephony credentials: {exc}",
        ) from exc

    template_config = None
    raw_cfg = agent.template_config
    if raw_cfg and str(raw_cfg).strip():
        try:
            loaded = json.loads(raw_cfg)
            if isinstance(loaded, dict):
                template_config = loaded
        except Exception:
            template_config = None

    _, inbound_routed_by = await resolve_inbound_connection(
        connection_id=connection_id,
        called_e164=called_e164,
    )
    if routed_agent_id:
        routed_by = "dtmf"
    elif inbound_routed_by == "sip":
        routed_by = "sip"
    elif inbound_routed_by == "did":
        routed_by = "did"
    else:
        routed_by = "webhook"
    # Locked to single voice: AB9XsbSA4eLG12t2myjN (ElevenLabs Mila)
    raw_voice = str(creds.voice_id or "").strip()
    voice_id = "AB9XsbSA4eLG12t2myjN"
    if raw_voice and raw_voice != voice_id:
        logger.info("telephony_channel: voice_id=%s overridden to default", raw_voice)
    payload = {
        "agent_id": int(agent.id),
        "connection_id": int(connection.id),
        "routed_by": routed_by,
        "system_prompt": agent.system_prompt or "",
        "welcome_message": agent.welcome_message,
        "template_type": str(agent.template_type or "qa"),
        "template_config": template_config,
        "voice_id": voice_id,
        "language": creds.language,
        "record_calls": bool(creds.record_calls),
        "disclaimer_played": bool(creds.disclaimer_played),
        "operator_transfer_e164": creds.operator_transfer_e164,
        "phone_number_e164": creds.phone_number_e164,
        "caller_e164": caller_e164.strip(),
    }
    logger.info(
        "resolve_telephony_channel: agent_id=%s connection_id=%s voice_id=%s lang=%s routed_by=%s",
        agent.id, connection.id, voice_id, creds.language, routed_by
    )
    await cache_resolve_payload(
        connection_id=int(connection.id),
        agent_id=int(agent.id),
        resolved=payload,
        caller_e164=caller_e164,
    )
    return payload


async def upsert_call_event(
    session: AsyncSession,
    *,
    connection_id: int,
    external_call_id: str,
    caller_e164: str,
    event: str,
    status_override: str | None,
    recording_url: str | None,
    duration_sec: int | None,
    metadata: dict[str, Any] | None,
    called_e164: str | None = None,
    routed_agent_id: int | None = None,
) -> tuple[AgentTelephonyCall, bool]:
    resolved_connection_id, routed_by = await resolve_inbound_connection(
        connection_id=connection_id,
        called_e164=called_e164,
    )
    connection = await load_active_telephony_connection(session, resolved_connection_id)
    target_agent_id = int(routed_agent_id or connection.agent_id)
    now = _utc_now()
    new_status = _event_to_status(event, status_override)

    event_id = (metadata or {}).get("event_id") if metadata else None

    existing = await session.scalar(
        select(AgentTelephonyCall).where(
            AgentTelephonyCall.connection_id == resolved_connection_id,
            AgentTelephonyCall.external_call_id == external_call_id,
        )
    )
    if existing is not None and event_id:
        prior_event_id = (existing.metadata_ or {}).get("last_event_id")
        if prior_event_id and str(prior_event_id) == str(event_id):
            return existing, False

    if existing is None:
        telephony_metrics.record_call_started()
        initial_meta = dict(metadata or {})
        if called_e164:
            initial_meta["routing"] = routing_summary_for_call(
                routed_by=routed_by,
                called_e164=called_e164,
            )
        call = AgentTelephonyCall(
            connection_id=resolved_connection_id,
            agent_id=target_agent_id,
            external_call_id=external_call_id,
            caller_e164=caller_e164.strip(),
            status=new_status,
            started_at=now,
            metadata_=initial_meta,
        )
        session.add(call)
        await session.flush()
        await cache_call_mapping(
            external_call_id=external_call_id,
            connection_id=resolved_connection_id,
            call_db_id=int(call.id),
            agent_id=target_agent_id,
            caller_e164=caller_e164,
        )
        return call, True

    if target_agent_id != int(existing.agent_id):
        existing.agent_id = target_agent_id
    existing.status = new_status
    if recording_url:
        existing.recording_url = recording_url
    if duration_sec is not None:
        existing.duration_sec = duration_sec
    if event == "call.hangup" and new_status in {"completed", "failed", "transferred"}:
        existing.ended_at = now
        if existing.started_at and duration_sec is None:
            delta = now - existing.started_at
            existing.duration_sec = max(0, int(delta.total_seconds()))
        telephony_metrics.record_call_completed(transferred=new_status == "transferred")
    merged_meta = dict(existing.metadata_ or {})
    if metadata:
        merged_meta.update(metadata)
    if called_e164:
        merged_meta["routing"] = routing_summary_for_call(
            routed_by=routed_by,
            called_e164=called_e164,
        )
    if event:
        merged_meta["last_event"] = event
    if event_id:
        merged_meta["last_event_id"] = event_id
    existing.metadata_ = merged_meta
    if recording_url:
        logger.info(
            "telephony recording ready call_id=%s url=%s",
            external_call_id,
            redact_telephony_log_message(str(recording_url)[:120]),
        )
    await session.flush()
    return existing, False
