"""Async Redis access for telephony orchestrator (stage 4)."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from ..config import settings
from .redis_keys import (
    ORCH_EVENTS_CHANNEL,
    ORCH_REPLIES_CHANNEL,
    agent_prompt_key,
    agent_spoken_key,
    call_key,
    dialog_key,
    route_did_key,
    route_dtmf_key,
    route_dtmf_owner_key,
    session_key,
    tool_cache_key,
)

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def redis_enabled() -> bool:
    return bool((settings.REDIS_URL or "").strip())


async def get_redis() -> Redis:
    global _redis
    url = (settings.REDIS_URL or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL is required for telephony orchestrator")
    if _redis is None:
        _redis = Redis.from_url(url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def hgetall_session(connection_id: int) -> dict[str, str]:
    client = await get_redis()
    return await client.hgetall(session_key(connection_id))


async def hmset_session(connection_id: int, mapping: dict[str, Any], *, ttl_sec: int) -> None:
    if not mapping:
        return
    client = await get_redis()
    key = session_key(connection_id)
    flat = {k: str(v) if not isinstance(v, str) else v for k, v in mapping.items()}
    pipe = client.pipeline()
    await pipe.hset(key, mapping=flat)
    await pipe.expire(key, max(60, ttl_sec))
    await pipe.execute()


async def set_agent_prompt(agent_id: int, prompt: str, *, ttl_sec: int) -> None:
    client = await get_redis()
    key = agent_prompt_key(agent_id)
    await client.set(key, prompt, ex=max(60, ttl_sec))


async def get_agent_prompt(agent_id: int) -> str | None:
    client = await get_redis()
    return await client.get(agent_prompt_key(agent_id))


async def set_call_mapping(
    external_call_id: str,
    payload: dict[str, Any],
    *,
    ttl_sec: int,
) -> None:
    client = await get_redis()
    await client.set(call_key(external_call_id), _json_dumps(payload), ex=max(60, ttl_sec))


async def get_call_mapping(external_call_id: str) -> dict[str, Any] | None:
    client = await get_redis()
    raw = await client.get(call_key(external_call_id))
    data = _json_loads(raw)
    return data if isinstance(data, dict) else None


async def append_dialog_turn(
    call_id: str,
    *,
    role: str,
    text: str,
    max_turns: int,
    ttl_sec: int,
) -> None:
    entry = _json_dumps({"role": role, "text": text})
    client = await get_redis()
    key = dialog_key(call_id)
    pipe = client.pipeline()
    await pipe.lpush(key, entry)
    await pipe.ltrim(key, 0, max(1, max_turns) - 1)
    await pipe.expire(key, max(60, ttl_sec))
    await pipe.execute()


async def get_dialog_turns(call_id: str, *, max_turns: int) -> list[dict[str, str]]:
    client = await get_redis()
    rows = await client.lrange(dialog_key(call_id), 0, max(1, max_turns) - 1)
    out: list[dict[str, str]] = []
    for raw in reversed(rows):
        item = _json_loads(raw)
        if isinstance(item, dict) and item.get("text"):
            out.append({"role": str(item.get("role") or ""), "text": str(item["text"])})
    return out


async def set_dialog_meta(call_id: str, meta: dict[str, Any], *, ttl_sec: int) -> None:
    client = await get_redis()
    key = f"{dialog_key(call_id)}:meta"
    await client.set(key, _json_dumps(meta), ex=max(60, ttl_sec))


async def get_dialog_meta(call_id: str) -> dict[str, Any]:
    client = await get_redis()
    raw = await client.get(f"{dialog_key(call_id)}:meta")
    data = _json_loads(raw)
    return data if isinstance(data, dict) else {}


async def build_compressed_history(call_id: str, *, max_turns: int) -> str:
    turns = await get_dialog_turns(call_id, max_turns=max_turns)
    lines: list[str] = []
    for row in turns:
        label = "Абонент" if row.get("role") == "user" else "Оператор"
        text = (row.get("text") or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


async def set_route_dtmf(extension: str, agent_id: int) -> None:
    client = await get_redis()
    await client.set(route_dtmf_key(extension), str(agent_id))


async def get_route_dtmf(extension: str) -> int | None:
    client = await get_redis()
    raw = await client.get(route_dtmf_key(extension))
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def set_route_dtmf_owner(extension: str, connection_id: int) -> None:
    client = await get_redis()
    await client.set(route_dtmf_owner_key(extension), str(connection_id))


async def get_route_dtmf_owner(extension: str) -> int | None:
    client = await get_redis()
    raw = await client.get(route_dtmf_owner_key(extension))
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def delete_route_dtmf(extension: str) -> None:
    client = await get_redis()
    pipe = client.pipeline()
    await pipe.delete(route_dtmf_key(extension))
    await pipe.delete(route_dtmf_owner_key(extension))
    await pipe.execute()


async def set_route_did(e164: str, connection_id: int) -> None:
    client = await get_redis()
    await client.set(route_did_key(e164), str(connection_id))


async def get_route_did(e164: str) -> int | None:
    client = await get_redis()
    raw = await client.get(route_did_key(e164))
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def delete_route_did(e164: str) -> None:
    client = await get_redis()
    await client.delete(route_did_key(e164))


async def cache_tool_result(call_id: str, tool_id: str, result: Any, *, ttl_sec: int) -> None:
    client = await get_redis()
    key = tool_cache_key(call_id)
    await client.hset(key, tool_id, _json_dumps(result))
    await client.expire(key, max(60, ttl_sec))


async def get_tool_cache(call_id: str) -> dict[str, Any]:
    client = await get_redis()
    raw = await client.hgetall(tool_cache_key(call_id))
    out: dict[str, Any] = {}
    for k, v in raw.items():
        parsed = _json_loads(v)
        if parsed is not None:
            out[k] = parsed
    return out


async def set_agent_spoken_text(call_id: str, text: str, *, ttl_sec: int) -> None:
    key = agent_spoken_key(call_id)
    client = await get_redis()
    trimmed = (text or "").strip()
    if trimmed:
        await client.set(key, trimmed, ex=max(60, ttl_sec))
    else:
        await client.delete(key)


async def get_agent_spoken_text(call_id: str) -> str | None:
    client = await get_redis()
    raw = await client.get(agent_spoken_key(call_id))
    if not raw:
        return None
    return str(raw).strip() or None


async def clear_agent_spoken_text(call_id: str) -> None:
    client = await get_redis()
    await client.delete(agent_spoken_key(call_id))


async def purge_hot_dialog(call_id: str) -> None:
    """Remove hot dialog keys after hangup (turns remain in Postgres)."""
    if not call_id.strip():
        return
    client = await get_redis()
    pipe = client.pipeline()
    await pipe.delete(dialog_key(call_id))
    await pipe.delete(f"{dialog_key(call_id)}:meta")
    await pipe.delete(tool_cache_key(call_id))
    await pipe.delete(agent_spoken_key(call_id))
    await pipe.execute()


async def publish_orch_event(payload: dict[str, Any]) -> None:
    client = await get_redis()
    await client.publish(ORCH_EVENTS_CHANNEL, _json_dumps(payload))


async def publish_orch_reply(payload: dict[str, Any]) -> None:
    client = await get_redis()
    await client.publish(ORCH_REPLIES_CHANNEL, _json_dumps(payload))


async def subscribe_orch_events():
    client = await get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(ORCH_EVENTS_CHANNEL)
    return pubsub
