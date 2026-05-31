"""Streaming TTS → μ-law chunks for media gateway (stage 5)."""



from __future__ import annotations



import logging

from collections.abc import AsyncIterator

from typing import Literal



import audioop

import httpx



from ..config import settings

from .tts_service import _strip_for_tts, map_voice_for_provider

from .ulaw import chunk_ulaw_frames, pcm16_to_ulaw



logger = logging.getLogger(__name__)



StreamTtsProvider = Literal["yandex", "elevenlabs", "batch"]



_YANDEX_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

_ELEVEN_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

_ELEVEN_MODEL = "eleven_flash_v2_5"

_ULAW_FRAME_BYTES = 160  # 20 ms @ 8 kHz μ-law





def resolve_stream_tts_provider() -> StreamTtsProvider | None:

    preferred = (getattr(settings, "TELEPHONY_STREAM_TTS_PROVIDER", None) or settings.TELEPHONY_TTS_PROVIDER or "").strip().lower()

    has_yandex = bool((settings.YANDEX_SPEECHKIT_API_KEY or "").strip())

    has_eleven = bool((getattr(settings, "ELEVENLABS_API_KEY", None) or "").strip())



    if preferred == "elevenlabs" and has_eleven:

        return "elevenlabs"

    if preferred == "yandex" and has_yandex:

        return "yandex"

    if preferred in ("voximplant", "batch", ""):

        if has_yandex:

            return "yandex"

        if has_eleven:

            return "elevenlabs"

    if has_yandex:

        return "yandex"

    if has_eleven:

        return "elevenlabs"

    return None





def stream_tts_enabled() -> bool:

    return resolve_stream_tts_provider() is not None





def assert_stream_tts_configured() -> None:

    if not stream_tts_enabled():

        raise RuntimeError(

            "Stream TTS is required for telephony orchestrator. "

            "Set YANDEX_SPEECHKIT_API_KEY or ELEVENLABS_API_KEY and TELEPHONY_STREAM_TTS_PROVIDER."

        )





async def stream_syntagma_ulaw(

    text: str,

    *,

    voice_id: str = "default",

    language: str = "ru-RU",

    provider: StreamTtsProvider | None = None,

) -> AsyncIterator[bytes]:

    """Yield μ-law frames (~20 ms) for one syntagma."""

    plain = _strip_for_tts(text)

    if not plain:

        return



    resolved = provider or resolve_stream_tts_provider()

    if resolved is None:

        return



    timeout = max(5.0, float(settings.TELEPHONY_TTS_TIMEOUT_SECONDS or 20.0))



    if resolved == "yandex":

        async for frame in _yandex_ulaw_stream(plain, voice_id=voice_id, lang=language, timeout=timeout):

            yield frame

    elif resolved == "elevenlabs":

        async for frame in _elevenlabs_ulaw_stream(plain, voice_id=voice_id, timeout=timeout):

            yield frame





async def _yandex_ulaw_stream(

    text: str,

    *,

    voice_id: str,

    lang: str,

    timeout: float,

) -> AsyncIterator[bytes]:

    """Prefer REST synthesis for stable PSTN; keep v3 as fallback."""

    try:
        ulaw = await _yandex_ulaw_rest(text, voice_id=voice_id, lang=lang, timeout=timeout)
        if ulaw:
            for frame in chunk_ulaw_frames(ulaw):
                yield frame
            return
    except Exception as exc:
        logger.warning("yandex REST tts failed, trying v3 stream fallback: %s", exc)

    try:
        from .yandex_tts_stream import stream_yandex_v3_ulaw_frames

        async for frame in stream_yandex_v3_ulaw_frames(
            text,
            voice_id=voice_id,
            lang=lang,
            timeout=timeout,
        ):
            yield frame
    except ImportError:
        return
    except Exception as exc:
        logger.warning("yandex v3 tts stream failed: %s", exc)





async def _yandex_ulaw_rest(

    text: str,

    *,

    voice_id: str,

    lang: str,

    timeout: float,

) -> bytes:

    api_key = (settings.YANDEX_SPEECHKIT_API_KEY or "").strip()

    if not api_key:

        raise RuntimeError("yandex_speechkit_key_missing")



    voice = map_voice_for_provider("yandex", voice_id)

    folder_id = (settings.YANDEX_SPEECHKIT_FOLDER_ID or "").strip()

    data = {

        "text": text,

        "lang": lang,

        "voice": voice,

        "format": "lpcm",

        "sampleRateHertz": "8000",

        "speed": "1.0",

    }

    if voice in {"alena", "jane", "omazh", "dasha", "marina"}:

        data["emotion"] = "good"

    headers = {"Authorization": f"Api-Key {api_key}"}

    if folder_id:

        headers["x-folder-id"] = folder_id



    async with httpx.AsyncClient(timeout=timeout) as client:

        response = await client.post(_YANDEX_TTS_URL, data=data, headers=headers)

    if response.status_code >= 400:

        logger.warning(
            "yandex stream tts failed status=%s body=%s",
            response.status_code,
            (response.text or "")[:200],
        )

        return b""

    return pcm16_to_ulaw(response.content)





async def _elevenlabs_ulaw_stream(

    text: str,

    *,

    voice_id: str,

    timeout: float,

) -> AsyncIterator[bytes]:

    """Stream ElevenLabs Flash v2.5 — emit μ-law frames as HTTP chunks arrive."""

    api_key = (getattr(settings, "ELEVENLABS_API_KEY", None) or "").strip()

    if not api_key:

        raise RuntimeError("elevenlabs_api_key_missing")



    voice = (voice_id or "default").strip()

    if voice in {"default", "neutral", "female", "woman"}:

        voice = "21m00Tcm4TlvDq8ikWAM"

    url = _ELEVEN_STREAM_URL.format(voice_id=voice)

    headers = {

        "xi-api-key": api_key,

        "Content-Type": "application/json",

        "Accept": "audio/basic",

    }

    body = {

        "text": text,

        "model_id": _ELEVEN_MODEL,

        "output_format": "ulaw_8000",

        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},

    }



    buffer = bytearray()

    async with httpx.AsyncClient(timeout=timeout) as client:

        async with client.stream("POST", url, headers=headers, json=body) as response:

            if response.status_code >= 400:

                raw = await response.aread()

                logger.warning("elevenlabs stream tts failed status=%s body=%s", response.status_code, raw[:200])

                response.raise_for_status()

            async for chunk in response.aiter_bytes():

                if not chunk:

                    continue

                buffer.extend(chunk)

                while len(buffer) >= _ULAW_FRAME_BYTES:

                    frame = bytes(buffer[:_ULAW_FRAME_BYTES])

                    del buffer[:_ULAW_FRAME_BYTES]

                    yield frame



    if buffer:

        padded = bytes(buffer) + b"\xff" * max(0, _ULAW_FRAME_BYTES - len(buffer))

        yield padded[:_ULAW_FRAME_BYTES]





async def batch_fallback_ulaw(

    text: str,

    *,

    voice_id: str = "default",

    language: str = "ru-RU",

) -> bytes:

    """Non-streaming fallback using preview TTS service."""

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

            return pcm16_to_ulaw(pcm)

    try:

        from pydub import AudioSegment

        import io



        seg = AudioSegment.from_file(io.BytesIO(audio))

        seg = seg.set_frame_rate(8000).set_channels(1)

        return pcm16_to_ulaw(seg.raw_data)

    except Exception:

        return b""


