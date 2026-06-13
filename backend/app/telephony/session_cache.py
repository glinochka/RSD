"""Cache telephony resolve + call mapping in Redis (stage 4)."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import settings
from .redis_store import (
    hmset_session,
    redis_enabled,
    set_agent_prompt,
    set_call_mapping,
)

logger = logging.getLogger(__name__)


def _ttl_sec() -> int:
    return max(300, int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC))


def _template_config_json(template_config: dict[str, Any] | None) -> str:
    if not template_config:
        return ""
    return json.dumps(template_config, ensure_ascii=False, separators=(",", ":"))


async def cache_resolve_payload(
    *,
    connection_id: int,
    agent_id: int,
    resolved: dict[str, Any],
    external_call_id: str | None = None,
    caller_e164: str | None = None,
    call_db_id: int | None = None,
) -> None:
    if not redis_enabled():
        return

    ttl = _ttl_sec()
    # Locked to single voice: AB9XsbSA4eLG12t2myjN (ElevenLabs Mila)
    voice_id = "AB9XsbSA4eLG12t2myjN"
    language = resolved.get("language") or "ru-RU"
    logger.info(
        "cache_resolve_payload: connection_id=%s agent_id=%s voice_id=%s language=%s",
        connection_id, agent_id, voice_id, language
    )
    await hmset_session(
        connection_id,
        {
            "agent_id": agent_id,
            "connection_id": connection_id,
            "system_prompt": resolved.get("system_prompt") or "",
            "welcome_message": resolved.get("welcome_message") or "",
            "template_type": resolved.get("template_type") or "qa",
            "template_config": _template_config_json(resolved.get("template_config")),
            "voice_id": voice_id,
            "language": language,
            "record_calls": "1" if resolved.get("record_calls") else "0",
            "disclaimer_played": "1" if resolved.get("disclaimer_played") else "0",
            "operator_transfer_e164": resolved.get("operator_transfer_e164") or "",
            "phone_number_e164": resolved.get("phone_number_e164") or "",
        },
        ttl_sec=ttl,
    )
    await set_agent_prompt(agent_id, str(resolved.get("system_prompt") or ""), ttl_sec=ttl)

    # DID routes are synced on channel connect/update via telephony.routing.sync_channel_routes

    if external_call_id and call_db_id is not None:
        await cache_call_mapping(
            external_call_id=external_call_id,
            connection_id=connection_id,
            call_db_id=call_db_id,
            agent_id=agent_id,
            caller_e164=caller_e164 or "",
        )


async def cache_call_mapping(
    *,
    external_call_id: str,
    connection_id: int,
    call_db_id: int,
    agent_id: int,
    caller_e164: str,
) -> None:
    if not redis_enabled():
        return
    await set_call_mapping(
        external_call_id,
        {
            "call_db_id": call_db_id,
            "connection_id": connection_id,
            "agent_id": agent_id,
            "caller_e164": caller_e164.strip(),
        },
        ttl_sec=_ttl_sec(),
    )


async def register_did_route(e164: str, connection_id: int) -> None:
    if not redis_enabled():
        return
    await set_route_did(e164.strip(), connection_id)
