"""Speech-to-text for voice messages (DeepSeek has no audio input).

Primary engine: faster-whisper (local). Optional fallback: OpenAI Whisper API.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
from io import BytesIO

from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)

# Serialize transcriptions: model inference is CPU/GPU-heavy.
_stt_sem = asyncio.Semaphore(1)

_whisper_model = None
_whisper_model_lock = threading.Lock()


def _faster_whisper_import():
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415

        return WhisperModel
    except ImportError:
        return None


def faster_whisper_runtime_available() -> bool:
    return _faster_whisper_import() is not None


def is_voice_stt_configured() -> bool:
    """Whether we will attempt to transcribe voice (any backend)."""
    backend = (settings.VOICE_STT_BACKEND or "auto").strip().lower()
    openai_ok = bool((settings.OPENAI_API_KEY or "").strip())
    if backend == "openai":
        return openai_ok
    if backend == "faster_whisper":
        return faster_whisper_runtime_available()
    # auto
    return faster_whisper_runtime_available() or openai_ok


def _get_whisper_model():
    global _whisper_model
    WhisperModel = _faster_whisper_import()
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed")
    with _whisper_model_lock:
        if _whisper_model is None:
            _whisper_model = WhisperModel(
                settings.FASTER_WHISPER_MODEL,
                device=settings.FASTER_WHISPER_DEVICE,
                compute_type=settings.FASTER_WHISPER_COMPUTE_TYPE,
            )
        return _whisper_model


def _extension_for_mime(mime_type: str) -> str:
    lower_mime = (mime_type or "").lower()
    if "mpeg" in lower_mime or "mp3" in lower_mime:
        return ".mp3"
    if "wav" in lower_mime:
        return ".wav"
    if "m4a" in lower_mime or "mp4" in lower_mime:
        return ".m4a"
    if "ogg" in lower_mime or "opus" in lower_mime:
        return ".ogg"
    if "webm" in lower_mime:
        return ".webm"
    return ".ogg"


def _transcribe_faster_whisper_file(path: str, *, vad_filter: bool | None = None) -> str:
    model = _get_whisper_model()
    lang = (settings.FASTER_WHISPER_LANGUAGE or "").strip() or None
    use_vad = (
        bool(settings.FASTER_WHISPER_VAD_FILTER)
        if vad_filter is None
        else bool(vad_filter)
    )
    segments, info = model.transcribe(
        path,
        language=lang,
        vad_filter=use_vad,
        beam_size=1,
        condition_on_previous_text=False,
    )
    parts = [s.text for s in segments]
    text = "".join(parts).strip()
    if not text and use_vad:
        duration = getattr(info, "duration", None)
        logger.info(
            "faster-whisper empty with vad_filter=True (duration=%s), retrying without VAD",
            duration,
        )
        segments, _info = model.transcribe(
            path,
            language=lang,
            vad_filter=False,
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = "".join(s.text for s in segments).strip()
    return text


def _transcribe_faster_whisper_sync(
    audio_bytes: bytes,
    mime_type: str,
    *,
    vad_filter: bool | None = None,
) -> str:
    ext = _extension_for_mime(mime_type)
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        return _transcribe_faster_whisper_file(path, vad_filter=vad_filter)
    except Exception:
        logger.exception("faster-whisper transcription failed")
        return ""
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


async def _transcribe_openai_api(audio_bytes: bytes, mime_type: str) -> str:
    key = (settings.OPENAI_API_KEY or "").strip()
    if not key:
        return ""

    ext = _extension_for_mime(mime_type)
    client = AsyncOpenAI(api_key=key)
    buf = BytesIO(audio_bytes)
    buf.name = f"voice{ext}"
    try:
        result = await client.audio.transcriptions.create(model="whisper-1", file=buf)
    except Exception:
        logger.exception("OpenAI Whisper transcription failed")
        return ""
    return (getattr(result, "text", None) or "").strip()


async def transcribe_voice_bytes(
    audio_bytes: bytes,
    *,
    mime_type: str = "audio/ogg",
    vad_filter: bool | None = None,
) -> str:
    """
    Transcribe voice audio: faster-whisper and/or OpenAI, depending on VOICE_STT_BACKEND.
    """
    if not audio_bytes:
        return ""

    max_b = int(getattr(settings, "VOICE_MAX_BYTES", 0) or 0)
    if max_b > 0 and len(audio_bytes) > max_b:
        logger.warning(
            "Rejected voice payload: size %s exceeds VOICE_MAX_BYTES=%s",
            len(audio_bytes),
            max_b,
        )
        return ""

    backend = (settings.VOICE_STT_BACKEND or "auto").strip().lower()
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    timeout = float(getattr(settings, "VOICE_TRANSCRIPTION_TIMEOUT_SECONDS", 120.0) or 120.0)

    async def _transcribe() -> str:
        async with _stt_sem:
            if backend == "openai":
                return await _transcribe_openai_api(audio_bytes, mime_type)

            if backend == "faster_whisper":
                if not faster_whisper_runtime_available():
                    logger.warning("VOICE_STT_BACKEND=faster_whisper but faster-whisper is not installed")
                    return ""
                return await asyncio.to_thread(
                    _transcribe_faster_whisper_sync,
                    audio_bytes,
                    mime_type,
                    vad_filter=vad_filter,
                )

            # auto: prefer local, then OpenAI
            if faster_whisper_runtime_available():
                text = await asyncio.to_thread(
                    _transcribe_faster_whisper_sync,
                    audio_bytes,
                    mime_type,
                    vad_filter=vad_filter,
                )
                if text:
                    return text
                if openai_key:
                    return await _transcribe_openai_api(audio_bytes, mime_type)
                return ""

            if openai_key:
                return await _transcribe_openai_api(audio_bytes, mime_type)
            return ""

    try:
        return await asyncio.wait_for(_transcribe(), timeout=timeout)
    except TimeoutError:
        logger.warning(
            "Voice transcription timed out after %.1fs (payload %s bytes)",
            timeout,
            len(audio_bytes),
        )
        return ""
