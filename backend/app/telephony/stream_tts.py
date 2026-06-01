"""Streaming TTS -> PCM16 (8 kHz mono) frames for telephony pipeline."""

from __future__ import annotations

import audioop
import logging
from collections.abc import AsyncIterator

from ..config import settings
from .tts_service import _strip_for_tts

logger = logging.getLogger(__name__)

_PCM16_FRAME_BYTES = 320  # 20 ms @ 8 kHz mono LINEAR16


def stream_tts_enabled() -> bool:
    # Canonical production path: Yandex SpeechKit v3 stream only.
    return bool((settings.YANDEX_SPEECHKIT_API_KEY or "").strip())


def assert_stream_tts_configured() -> None:
    if not stream_tts_enabled():
        raise RuntimeError("Stream TTS requires YANDEX_SPEECHKIT_API_KEY")


def _chunk_pcm16_frames(pcm16: bytes, *, frame_bytes: int = _PCM16_FRAME_BYTES) -> list[bytes]:
    if not pcm16:
        return []
    even_len = (len(pcm16) // 2) * 2
    if even_len <= 0:
        return []
    pcm = pcm16[:even_len]
    out = [pcm[i : i + frame_bytes] for i in range(0, len(pcm), frame_bytes) if pcm[i : i + frame_bytes]]
    if not out:
        return []
    tail = out[-1]
    if len(tail) < frame_bytes:
        out[-1] = tail + (b"\x00" * (frame_bytes - len(tail)))
    return out


async def stream_syntagma_pcm16(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> AsyncIterator[bytes]:
    """
    Yield PCM16 LE frames (~20 ms, 8 kHz mono) for one syntagma.
    Canonical telephony path: Yandex v3 stream.
    """
    plain = _strip_for_tts(text)
    if not plain:
        return
    timeout = max(1.0, float(settings.TELEPHONY_TTS_TIMEOUT_SECONDS or 10.0))
    from .yandex_tts_stream import stream_yandex_v3_pcm16_frames

    async for frame in stream_yandex_v3_pcm16_frames(
        plain,
        voice_id=voice_id,
        lang=language,
        timeout=timeout,
    ):
        yield frame


async def batch_fallback_pcm16(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> bytes:
    """
    Non-streaming fallback: preview TTS audio transcoded to PCM16 mono 8k.
    Used only as emergency fallback for fixed phrases/fillers.
    """
    from .tts_service import synthesize_preview_speech

    audio, _mime, _provider = await synthesize_preview_speech(text, voice_id=voice_id, language=language)
    if audio[:4] == b"RIFF":
        import io
        import wave

        with wave.open(io.BytesIO(audio), "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
            if wf.getnchannels() > 1:
                pcm = audioop.tomono(pcm, wf.getsampwidth(), 0.5, 0.5)
            if wf.getframerate() != 8000:
                pcm, _ = audioop.ratecv(pcm, wf.getsampwidth(), 1, wf.getframerate(), 8000, None)
            if wf.getsampwidth() != 2:
                pcm = audioop.lin2lin(pcm, wf.getsampwidth(), 2)
            return b"".join(_chunk_pcm16_frames(pcm))

    try:
        import io
        from pydub import AudioSegment

        seg = AudioSegment.from_file(io.BytesIO(audio))
        seg = seg.set_frame_rate(8000).set_channels(1).set_sample_width(2)
        return b"".join(_chunk_pcm16_frames(seg.raw_data))
    except Exception:
        logger.exception("batch_fallback_pcm16 failed")
        return b""


# Backward-compatible wrappers for callers not migrated yet.
async def stream_syntagma_ulaw(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
):
    from .ulaw import pcm16_to_ulaw

    async for pcm in stream_syntagma_pcm16(text, voice_id=voice_id, language=language):
        yield pcm16_to_ulaw(pcm)


async def batch_fallback_ulaw(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> bytes:
    from .ulaw import pcm16_to_ulaw

    pcm = await batch_fallback_pcm16(text, voice_id=voice_id, language=language)
    return pcm16_to_ulaw(pcm) if pcm else b""
