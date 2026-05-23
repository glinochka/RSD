"""RAM cache of filler phrases as μ-law (stage 5)."""

from __future__ import annotations

import asyncio
import logging

from ..channels.telephony_dialogue import MSG_CRM_FILLER, MSG_RAG_FILLER
from .stream_tts import batch_fallback_ulaw, resolve_stream_tts_provider, stream_syntagma_ulaw

logger = logging.getLogger(__name__)

_cache: dict[str, bytes] = {}
_lock = asyncio.Lock()


async def get_filler_ulaw(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> bytes | None:
    key = f"{voice_id}:{language}:{text.strip()}"
    if key in _cache:
        return _cache[key]

    async with _lock:
        if key in _cache:
            return _cache[key]
        try:
            if resolve_stream_tts_provider():
                chunks: list[bytes] = []
                async for frame in stream_syntagma_ulaw(text, voice_id=voice_id, language=language):
                    chunks.append(frame)
                ulaw = b"".join(chunks)
            else:
                ulaw = await batch_fallback_ulaw(text, voice_id=voice_id, language=language)
            if ulaw:
                _cache[key] = ulaw
            return ulaw or None
        except Exception:
            logger.exception("filler_audio synthesis failed text_len=%s", len(text))
            return None


async def warm_default_fillers(*, voice_id: str = "default", language: str = "ru-RU") -> None:
    for text in (MSG_CRM_FILLER, MSG_RAG_FILLER):
        await get_filler_ulaw(text, voice_id=voice_id, language=language)


def clear_filler_cache_for_tests() -> None:
    _cache.clear()
