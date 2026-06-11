"""RAM cache of filler phrases as PCM16 8k mono (stage 5)."""

from __future__ import annotations

import asyncio
import logging

from ..channels.telephony_dialogue import MSG_CRM_FILLER, MSG_RAG_FILLER
from .stream_tts import batch_fallback_pcm16, stream_syntagma_pcm16

logger = logging.getLogger(__name__)

_cache: dict[str, bytes] = {}
_lock = asyncio.Lock()


async def get_filler_pcm16(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    language: str = "ru-RU",
) -> bytes | None:
    key = f"{voice_id}:{language}:{text.strip()}"
    if key in _cache:
        return _cache[key]

    async with _lock:
        if key in _cache:
            return _cache[key]
        try:
            chunks: list[bytes] = []
            async for frame in stream_syntagma_pcm16(text, voice_id=voice_id, language=language):
                chunks.append(frame)
            pcm16 = b"".join(chunks)
            if not pcm16:
                pcm16 = await batch_fallback_pcm16(text, voice_id=voice_id, language=language)
            if pcm16:
                _cache[key] = pcm16
            return pcm16 or None
        except Exception:
            logger.exception("filler_audio synthesis failed text_len=%s", len(text))
            return None


async def warm_default_fillers(*, voice_id: str = "AB9XsbSA4eLG12t2myjN", language: str = "ru-RU") -> None:
    for text in (MSG_CRM_FILLER, MSG_RAG_FILLER):
        await get_filler_pcm16(text, voice_id=voice_id, language=language)


# Backward-compatible alias.
async def get_filler_ulaw(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    language: str = "ru-RU",
) -> bytes | None:
    from .ulaw import pcm16_to_ulaw

    pcm16 = await get_filler_pcm16(text, voice_id=voice_id, language=language)
    return pcm16_to_ulaw(pcm16) if pcm16 else None


def clear_filler_cache_for_tests() -> None:
    _cache.clear()
