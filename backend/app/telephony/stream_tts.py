"""Streaming TTS -> PCM16 (8 kHz mono) frames for telephony pipeline."""

from __future__ import annotations

import audioop
import io
import logging
import wave
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
    voice_id: str = "default",
    timeout: float = 10.0,
) -> AsyncIterator[bytes]:
    """Fallback ElevenLabs TTS streaming to PCM16 frames."""
    import httpx

    api_key = (settings.ELEVENLABS_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("elevenlabs_api_key_missing")

    # Map voice_id to ElevenLabs voice IDs
    # Use Ru speaking voices for Russian text
    default_voices = {
        "alice": "Xb7hH8MSUJpSbSDYk0k2",  # Alice - expressive, multilingual
        "antoni": "ErXwobaYiN019PrySvdu",  # Antoni - male
        "bella": "MF3mGyEYCl7XYWbV9V6O",   # Bella - female
        "callum": "N2lVS1w4EtoT3dr4eOWO",  # Callum - male
        "charlie": "IKne3meq5aSn9XLyUdCD",  # Charlie - male
        "clyde": "2EiwWnXFnvU5JabPnv8Z",    # Clyde - male
        "dave": "CYw3kZ02Hs0563khs1Fj",      # Dave - male
        "fin": "D38z5RcWu1voky8WS1ja",      # Fin - male
        "glinda": "z9fAnlkpzviPz146aGWa",   # Glinda - female
        "matilda": "XrExE9yKIg1WbnnjSflH",  # Matilda - female
        "michael": "flq6f7yk4E4fJM5XTYuZ",  # Michael - male
        "nicole": "piTKgcLEGmPE4e6mEKli",   # Nicole - female
        "patrick": "przKpfM8PZDW5zJO8izB",  # Patrick - male
        "richard": "Yko7PKHZNXotIFUBG7I9",  # Richard - male
        "santa": "knrPHWnB5DHpoakj5Ztg",    # Santa - male
    }

    # Use provided voice_id if it looks like an ElevenLabs ID (22 chars)
    # Otherwise map from our names or use default
    if voice_id and len(voice_id) == 22:
        voice = voice_id
    elif voice_id in default_voices:
        voice = default_voices[voice_id]
    else:
        voice = default_voices["bella"]  # Default: Bella

    # ElevenLabs supports streaming with output_format=pcm_16000
    # We'll then resample to 8000 Hz
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/pcm",
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "output_format": "pcm_16000",
    }

    logger.info("elevenlabs_tts: text_len=%d voice=%s", len(text), voice[:8])

    # Collect all PCM data
    pcm_16k = b""

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=data, headers=headers) as response:
            if response.status_code >= 400:
                error_text = await response.aread()
                raise RuntimeError(f"elevenlabs_api_error: {response.status_code} {error_text[:200]}")

            async for chunk in response.aiter_bytes():
                pcm_16k += chunk

    if not pcm_16k:
        raise RuntimeError("elevenlabs_tts_empty_response")

    # Convert PCM 16-bit 16kHz mono to 8kHz mono
    # First ensure even length for 16-bit samples
    if len(pcm_16k) % 2 == 1:
        pcm_16k = pcm_16k[:-1]

    # Resample from 16000 to 8000 Hz
    pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)

    # Yield frames
    for frame in _chunk_pcm16_frames(pcm_8k):
        yield frame


async def stream_syntagma_pcm16(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> AsyncIterator[bytes]:
    """
    Yield PCM16 LE frames (~20 ms, 8 kHz mono) for one syntagma.
    Priority: Yandex > OpenAI > ElevenLabs.
    """
    plain = _strip_for_tts(text)
    if not plain:
        return
    timeout = max(1.0, float(settings.TELEPHONY_TTS_TIMEOUT_SECONDS or 10.0))

    # Try Yandex first
    yandex_key = (settings.YANDEX_SPEECHKIT_API_KEY or "").strip()
    if yandex_key:
        try:
            from .yandex_tts_stream import stream_yandex_v3_pcm16_frames

            async for frame in stream_yandex_v3_pcm16_frames(
                plain,
                voice_id=voice_id,
                lang=language,
                timeout=timeout,
            ):
                yield frame
            return  # Success, exit
        except Exception as e:
            logger.warning("yandex_tts_failed: %s, trying_openai_fallback", e)

    # Fallback 1: OpenAI TTS
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    if openai_key:
        try:
            async for frame in _stream_openai_pcm16(
                plain,
                voice_id=voice_id,
                timeout=timeout,
            ):
                yield frame
            return  # Success
        except Exception as e:
            logger.warning("openai_tts_failed: %s, trying_elevenlabs_fallback", e)

    # Fallback 2: ElevenLabs TTS
    elevenlabs_key = (settings.ELEVENLABS_API_KEY or "").strip()
    if elevenlabs_key:
        try:
            async for frame in _stream_elevenlabs_pcm16(
                plain,
                voice_id=voice_id,
                timeout=timeout,
            ):
                yield frame
            return  # Success
        except Exception as e:
            logger.error("elevenlabs_tts_failed: %s", e)
            raise RuntimeError(f"all_tts_providers_failed: {e}")

    raise RuntimeError("no_tts_provider_available")


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
