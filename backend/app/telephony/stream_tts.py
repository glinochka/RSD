"""Streaming TTS -> PCM16 (8 kHz mono) frames for telephony pipeline."""

from __future__ import annotations

import audioop
import io
import logging
import wave
from collections.abc import AsyncIterator
import httpx

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


async def _stream_openai_pcm16(
    text: str,
    *,
    voice_id: str = "default",
    timeout: float = 10.0,
) -> AsyncIterator[bytes]:
    """Fallback OpenAI TTS streaming to PCM16 frames."""
    from openai import AsyncOpenAI
    import io
    import wave

    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("openai_api_key_missing")

    # Map voice_id to OpenAI voices
    valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    voice = voice_id if voice_id in valid_voices else "nova"

    client = AsyncOpenAI(api_key=api_key, timeout=timeout)

    logger.info("openai_tts_fallback: text_len=%d voice=%s", len(text), voice)

    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,  # type: ignore
        input=text,
        response_format="wav",  # WAV for easier PCM extraction
    )

    # Read audio content
    audio_bytes = b""
    if hasattr(response, "content"):
        audio_bytes = bytes(response.content)
    elif hasattr(response, "read"):
        audio_bytes = await response.read()

    if not audio_bytes:
        raise RuntimeError("openai_tts_empty_response")

        # Convert WAV to PCM16 8kHz mono
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                pcm = wf.readframes(wf.getnframes())
                # Convert to mono if needed
                if wf.getnchannels() > 1:
                    pcm = audioop.tomono(pcm, wf.getsampwidth(), 0.5, 0.5)
                # Resample to 8kHz if needed
                if wf.getframerate() != 8000:
                    pcm, _ = audioop.ratecv(pcm, wf.getsampwidth(), 1, wf.getframerate(), 8000, None)
                # Convert to 16-bit if needed
                if wf.getsampwidth() != 2:
                    pcm = audioop.lin2lin(pcm, wf.getsampwidth(), 2)

            # Yield frames
            for frame in _chunk_pcm16_frames(pcm):
                yield frame
        except Exception as e:
            logger.exception("openai_tts_wav_processing_failed")
            raise RuntimeError(f"openai_tts_processing_failed: {e}")


async def _stream_elevenlabs_pcm16(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    timeout: float = 10.0,
) -> AsyncIterator[bytes]:
    """ElevenLabs TTS streaming to PCM16 frames with optimized Russian voice mapping."""
    api_key = (settings.ELEVENLABS_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("elevenlabs_api_key_missing")

    # ElevenLabs voice - hardcoded default for all agents
    # Temporarily locked to AB9XsbSA4eLG12t2myjN (Mila - Russian voice)
    DEFAULT_ELEVENLABS_VOICE = "AB9XsbSA4eLG12t2myjN"

    # Legacy mapping (kept for compatibility, but all map to default)
    RUSSIAN_VOICES = {
        "default": DEFAULT_ELEVENLABS_VOICE,
        "alice": DEFAULT_ELEVENLABS_VOICE,
        "bella": DEFAULT_ELEVENLABS_VOICE,
        "matilda": DEFAULT_ELEVENLABS_VOICE,
        "nicole": DEFAULT_ELEVENLABS_VOICE,
        "glinda": DEFAULT_ELEVENLABS_VOICE,
        "antoni": DEFAULT_ELEVENLABS_VOICE,
        "callum": DEFAULT_ELEVENLABS_VOICE,
        "charlie": DEFAULT_ELEVENLABS_VOICE,
        "clyde": DEFAULT_ELEVENLABS_VOICE,
        "dave": DEFAULT_ELEVENLABS_VOICE,
        "fin": DEFAULT_ELEVENLABS_VOICE,
        "michael": DEFAULT_ELEVENLABS_VOICE,
        "patrick": DEFAULT_ELEVENLABS_VOICE,
        "richard": DEFAULT_ELEVENLABS_VOICE,
        "adam": DEFAULT_ELEVENLABS_VOICE,
        "daniel": DEFAULT_ELEVENLABS_VOICE,
        "josh": DEFAULT_ELEVENLABS_VOICE,
        "rachel": DEFAULT_ELEVENLABS_VOICE,
        "domi": DEFAULT_ELEVENLABS_VOICE,
        "elli": DEFAULT_ELEVENLABS_VOICE,
    }

    # Force default voice for all agents (temporary - single voice policy)
    # All voice_id values are overridden to DEFAULT_ELEVENLABS_VOICE
    raw_voice = (voice_id or "").strip()
    if raw_voice and len(raw_voice) >= 20 and raw_voice == DEFAULT_ELEVENLABS_VOICE:
        # Allow only the default voice ID
        voice = raw_voice
        logger.info("elevenlabs_tts: using default voice_id=%s", voice[:8] + "...")
    else:
        # Override any other voice with default
        voice = DEFAULT_ELEVENLABS_VOICE
        if raw_voice:
            logger.info("elevenlabs_tts: voice_id=%s overridden to default voice", raw_voice)
        else:
            logger.info("elevenlabs_tts: using default voice")

    # ElevenLabs стриминг: запрашиваем MP3 (наиболее совместимый формат),
    # декодируем в PCM и ресемплируем до 8kHz.
    # Параметр output_format=pcm_16000 не всегда работает для всех voice/model.
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "output_format": "mp3_22050",  # 22.05kHz MP3 - оптимальный баланс качества и задержки
    }

    logger.info("elevenlabs_tts: text_len=%d voice=%s format=mp3_22050", len(text), voice[:8])

    # Collect MP3 data
    mp3_data = b""

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=data, headers=headers) as response:
            if response.status_code >= 400:
                error_text = await response.aread()
                raise RuntimeError(f"elevenlabs_api_error: {response.status_code} {error_text[:200]}")

            async for chunk in response.aiter_bytes():
                mp3_data += chunk

    if not mp3_data:
        raise RuntimeError("elevenlabs_tts_empty_response")

    # Декодируем MP3 в PCM16 через pydub
    try:
        from pydub import AudioSegment
        import io

        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        # Конвертируем в mono 16-bit если нужно
        if audio.channels > 1:
            audio = audio.set_channels(1)
        if audio.sample_width != 2:
            audio = audio.set_sample_width(2)

        # Ресемплируем до 8kHz
        if audio.frame_rate != 8000:
            audio = audio.set_frame_rate(8000)

        pcm_8k = audio.raw_data
    except Exception as e:
        logger.exception("elevenlabs_tts_mp3_decode_failed")
        raise RuntimeError(f"elevenlabs_tts_mp3_decode_failed: {e}") from e

    # Yield frames
    for frame in _chunk_pcm16_frames(pcm_8k):
        yield frame


async def stream_syntagma_pcm16(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    language: str = "ru-RU",
) -> AsyncIterator[bytes]:
    """
    Yield PCM16 LE frames (~20 ms, 8 kHz mono) for one syntagma.
    Priority controlled by TELEPHONY_STREAM_TTS_PROVIDER setting.
    
    Provider priority:
    - elevenlabs: ElevenLabs -> Yandex -> OpenAI (Yandex fallback for Russian)
    - yandex: Yandex -> ElevenLabs -> OpenAI
    - openai: OpenAI -> ElevenLabs -> Yandex
    """
    plain = _strip_for_tts(text)
    if not plain:
        return
    timeout = max(1.0, float(settings.TELEPHONY_TTS_TIMEOUT_SECONDS or 10.0))

    # Determine provider order based on settings
    provider = (settings.TELEPHONY_STREAM_TTS_PROVIDER or "yandex").strip().lower()

    # Build provider list based on priority setting
    # ElevenLabs -> Yandex -> OpenAI (Russian-first priority)
    if provider == "elevenlabs":
        provider_order = [
            ("elevenlabs", _try_elevenlabs_tts),
            ("yandex", _try_yandex_tts),      # Fallback to Yandex for Russian
            ("openai", _try_openai_tts),
        ]
    elif provider == "openai":
        provider_order = [
            ("openai", _try_openai_tts),
            ("elevenlabs", _try_elevenlabs_tts),
            ("yandex", _try_yandex_tts),
        ]
    else:  # default yandex
        provider_order = [
            ("yandex", _try_yandex_tts),
            ("elevenlabs", _try_elevenlabs_tts),
            ("openai", _try_openai_tts),
        ]

    errors = []

    for name, try_fn in provider_order:
        try:
            async for frame in try_fn(plain, voice_id=voice_id, language=language, timeout=timeout):
                yield frame
            logger.info("tts_success: provider=%s text_len=%d", name, len(plain))
            return  # Success
        except Exception as e:
            logger.warning("tts_failed: provider=%s error=%s", name, e)
            errors.append(f"{name}: {e}")

    raise RuntimeError(f"all_tts_providers_failed: {'; '.join(errors)}")


async def _try_yandex_tts(
    plain: str,
    *,
    voice_id: str,
    language: str,
    timeout: float,
) -> AsyncIterator[bytes]:
    """Try Yandex SpeechKit TTS."""
    yandex_key = (settings.YANDEX_SPEECHKIT_API_KEY or "").strip()
    if not yandex_key:
        raise RuntimeError("yandex_api_key_missing")

    from .yandex_tts_stream import stream_yandex_v3_pcm16_frames

    async for frame in stream_yandex_v3_pcm16_frames(
        plain,
        voice_id=voice_id,
        lang=language,
        timeout=timeout,
    ):
        yield frame


async def _try_openai_tts(
    plain: str,
    *,
    voice_id: str,
    language: str,
    timeout: float,
) -> AsyncIterator[bytes]:
    """Try OpenAI TTS."""
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    if not openai_key:
        raise RuntimeError("openai_api_key_missing")

    async for frame in _stream_openai_pcm16(
        plain,
        voice_id=voice_id,
        timeout=timeout,
    ):
        yield frame


async def _try_elevenlabs_tts(
    plain: str,
    *,
    voice_id: str,
    language: str,
    timeout: float,
) -> AsyncIterator[bytes]:
    """Try ElevenLabs TTS."""
    elevenlabs_key = (settings.ELEVENLABS_API_KEY or "").strip()
    if not elevenlabs_key:
        raise RuntimeError("elevenlabs_api_key_missing")

    async for frame in _stream_elevenlabs_pcm16(
        plain,
        voice_id=voice_id,
        timeout=timeout,
    ):
        yield frame


async def batch_fallback_pcm16(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
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
        pcm = seg.raw_data
        return b"".join(_chunk_pcm16_frames(pcm))
    except Exception:
        logger.exception("batch_fallback_pcm16 failed")
        return b""


# Backward-compatible wrappers for callers not migrated yet.
async def stream_syntagma_ulaw(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    language: str = "ru-RU",
):
    from .ulaw import pcm16_to_ulaw

    async for pcm in stream_syntagma_pcm16(text, voice_id=voice_id, language=language):
        yield pcm16_to_ulaw(pcm)


async def batch_fallback_ulaw(
    text: str,
    *,
    voice_id: str = "AB9XsbSA4eLG12t2myjN",
    language: str = "ru-RU",
) -> bytes:
    from .ulaw import pcm16_to_ulaw

    pcm = await batch_fallback_pcm16(text, voice_id=voice_id, language=language)
    return pcm16_to_ulaw(pcm) if pcm else b""
