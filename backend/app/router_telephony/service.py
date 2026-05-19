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
        "call.recording_ready": "active",
        "dtmf": "active",
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


async def resolve_telephony_channel(
    session: AsyncSession,
    *,
    connection_id: int,
    caller_e164: str,
) -> dict[str, Any]:
    connection = await load_active_telephony_connection(session, connection_id)
    agent = await session.scalar(select(Agent).where(Agent.id == connection.agent_id, Agent.is_active.is_(True)))
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

    return {
        "agent_id": int(agent.id),
        "connection_id": int(connection.id),
        "system_prompt": agent.system_prompt or "",
        "welcome_message": agent.welcome_message,
        "template_type": str(agent.template_type or "qa"),
        "template_config": template_config,
        "voice_id": creds.voice_id,
        "language": creds.language,
        "record_calls": bool(creds.record_calls),
        "disclaimer_played": bool(creds.disclaimer_played),
        "operator_transfer_e164": creds.operator_transfer_e164,
        "phone_number_e164": creds.phone_number_e164,
        "caller_e164": caller_e164.strip(),
    }


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
) -> tuple[AgentTelephonyCall, bool]:
    connection = await load_active_telephony_connection(session, connection_id)
    now = _utc_now()
    new_status = _event_to_status(event, status_override)

    event_id = (metadata or {}).get("event_id") if metadata else None

    existing = await session.scalar(
        select(AgentTelephonyCall).where(
            AgentTelephonyCall.connection_id == connection_id,
            AgentTelephonyCall.external_call_id == external_call_id,
        )
    )
    if existing is not None and event_id:
        prior_event_id = (existing.metadata_ or {}).get("last_event_id")
        if prior_event_id and str(prior_event_id) == str(event_id):
            return existing, False

    if existing is None:
        telephony_metrics.record_call_started()
        call = AgentTelephonyCall(
            connection_id=connection_id,
            agent_id=connection.agent_id,
            external_call_id=external_call_id,
            caller_e164=caller_e164.strip(),
            status=new_status,
            started_at=now,
            metadata_=metadata or {},
        )
        session.add(call)
        await session.flush()
        return call, True

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
