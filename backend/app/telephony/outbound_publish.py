"""Publish outbound agent audio / filler events to media gateway (stage 5)."""

from __future__ import annotations

import base64
from typing import Any

from .redis_store import publish_orch_reply


async def publish_agent_event(
    *,
    call_id: str,
    connection_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await publish_orch_reply(
        {
            "type": event_type,
            "call_id": call_id,
            "connection_id": connection_id,
            "payload": payload or {},
        }
    )


async def publish_agent_audio_start(*, call_id: str, connection_id: int, codec: str = "l16_8000") -> None:
    await publish_agent_event(
        call_id=call_id,
        connection_id=connection_id,
        event_type="agent.audio.start",
        payload={"codec": codec},
    )


async def publish_agent_audio_chunk(
    *,
    call_id: str,
    connection_id: int,
    sequence: int,
    audio_pcm16: bytes,
) -> None:
    await publish_agent_event(
        call_id=call_id,
        connection_id=connection_id,
        event_type="agent.audio.chunk",
        payload={
            "sequence": sequence,
            "audio_pcm16_b64": base64.b64encode(audio_pcm16).decode("ascii"),
        },
    )


async def publish_agent_audio_end(
    *,
    call_id: str,
    connection_id: int,
    reason: str = "complete",
) -> None:
    await publish_agent_event(
        call_id=call_id,
        connection_id=connection_id,
        event_type="agent.audio.end",
        payload={"reason": reason},
    )


async def publish_play_filler(
    *,
    call_id: str,
    connection_id: int,
    text: str,
    audio_pcm16: bytes | None = None,
) -> None:
    payload: dict[str, Any] = {"text": text}
    if audio_pcm16:
        payload["audio_pcm16_b64"] = base64.b64encode(audio_pcm16).decode("ascii")
    await publish_agent_event(
        call_id=call_id,
        connection_id=connection_id,
        event_type="agent.play_filler",
        payload=payload,
    )


async def publish_call_transfer(
    *,
    call_id: str,
    connection_id: int,
    e164: str,
) -> None:
    await publish_agent_event(
        call_id=call_id,
        connection_id=connection_id,
        event_type="call.transfer",
        payload={"e164": e164},
    )
