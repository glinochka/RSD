"""Redis key patterns for telephony orchestrator (stage 4)."""

from __future__ import annotations

SESSION_PREFIX = "telephony:session:"
AGENT_PROMPT_PREFIX = "telephony:agent:"
DIALOG_PREFIX = "telephony:dialog:"
CALL_PREFIX = "telephony:call:"
ROUTE_DTMF_PREFIX = "telephony:route:dtmf:"
ROUTE_DTMF_OWNER_PREFIX = "telephony:route:dtmf:owner:"
ROUTE_DID_PREFIX = "telephony:route:did:"
TOOL_CACHE_PREFIX = "telephony:toolcache:"
SPOKEN_PREFIX = "telephony:spoken:"

ORCH_EVENTS_CHANNEL = "telephony:orch:events"
ORCH_REPLIES_CHANNEL = "telephony:orch:replies"


def session_key(connection_id: int) -> str:
    return f"{SESSION_PREFIX}{connection_id}"


def agent_prompt_key(agent_id: int) -> str:
    return f"{AGENT_PROMPT_PREFIX}{agent_id}:prompt"


def dialog_key(call_id: str) -> str:
    return f"{DIALOG_PREFIX}{call_id}"


def call_key(external_call_id: str) -> str:
    return f"{CALL_PREFIX}{external_call_id}"


def route_dtmf_key(extension: str) -> str:
    return f"{ROUTE_DTMF_PREFIX}{extension}"


def route_dtmf_owner_key(extension: str) -> str:
    return f"{ROUTE_DTMF_OWNER_PREFIX}{extension}"


def route_did_key(e164: str) -> str:
    return f"{ROUTE_DID_PREFIX}{e164}"


def tool_cache_key(call_id: str) -> str:
    return f"{TOOL_CACHE_PREFIX}{call_id}"


def agent_spoken_key(call_id: str) -> str:
    return f"{SPOKEN_PREFIX}{call_id}"
