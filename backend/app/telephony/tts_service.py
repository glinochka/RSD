"""External TTS for browser telephony preview (Yandex SpeechKit / OpenAI)."""

from __future__ import annotations

import logging
import re
from typing import Literal

import httpx
from openai import AsyncOpenAI

from ..config import settings
from ..telephony.prosody import format_spoken_numbers

logger = logging.getLogger(__name__)

TtsProvider = Literal["yandex", "openai"]

_SSML_TAG_RE = re.compile(r"<[^>]+>")

# Yandex SpeechKit voices (ru-RU). Voximplant voice_id often differs — map default.
_YANDEX_VOICES = frozenset(
    {
        "alena",
        "filipp",
        "ermil",
        "jane",
        "omazh",
        "zahar",
        "dasha",
        "marina",
        "alexander",
        "anton",
        "kirill",
        "madi",
    }
)
_YANDEX_DEFAULT_VOICE = "alena"

_OPENAI_VOICES = frozenset({"alloy", "echo", "fable", "onyx", "nova", "shimmer"})
_OPENAI_DEFAULT_VOICE = "nova"

_YANDEX_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
_MAX_TTS_CHARS = 4000


def _strip_for_tts(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if raw.startswith("<speak"):
        raw = _SSML_TAG_RE.sub("", raw)
    return format_spoken_numbers(re.sub(r"\s+", " ", raw).strip())


def is_preview_tts_configured() -> bool:
    return resolve_preview_tts_provider() is not None


def resolve_preview_tts_provider() -> TtsProvider | None:
    """Provider for browser preview. Real PSTN still uses Voximplant on the bridge."""
    preferred = (settings.TELEPHONY_TTS_PROVIDER or "voximplant").strip().lower()
    has_yandex = bool((settings.YANDEX_SPEECHKIT_API_KEY or "").strip())
    has_openai = bool((settings.OPENAI_API_KEY or "").strip())

    if preferred == "yandex" and has_yandex:
        return "yandex"
    if preferred == "openai" and has_openai:
        return "openai"
    if preferred == "voximplant":
        if has_yandex:
            return "yandex"
        if has_openai:
            return "openai"
        return None
    if has_yandex:
        return "yandex"
    if has_openai:
        return "openai"
    return None


def map_voice_for_provider(provider: TtsProvider, voice_id: str) -> str:
    raw = (voice_id or "default").strip().lower()
    if provider == "yandex":
        if raw in _YANDEX_VOICES:
            return raw
        if raw in {"default", "neutral", "neutral-friendly", "female", "woman"}:
            return _YANDEX_DEFAULT_VOICE
        if raw in {"male", "man"}:
            return "filipp"
        return _YANDEX_DEFAULT_VOICE
    mapped = raw if raw in _OPENAI_VOICES else _OPENAI_DEFAULT_VOICE
    return mapped


async def synthesize_preview_speech(
    text: str,
    *,
    voice_id: str = "default",
    language: str = "ru-RU",
) -> tuple[bytes, str, TtsProvider]:
    """
    Synthesize speech for browser preview.
    Returns (audio_bytes, mime_type, provider_used).
    """
    plain = _strip_for_tts(text)
    if not plain:
        raise ValueError("empty_text")
    if len(plain) > _MAX_TTS_CHARS:
        plain = plain[:_MAX_TTS_CHARS]

    provider = resolve_preview_tts_provider()
    if not provider:
        raise RuntimeError("preview_tts_not_configured")

    timeout = max(5.0, float(getattr(settings, "TELEPHONY_TTS_TIMEOUT_SECONDS", 20.0) or 20.0))
    mapped_voice = map_voice_for_provider(provider, voice_id)

    if provider == "yandex":
        audio, mime = await _synthesize_yandex(
            plain,
            voice=mapped_voice,
            lang=(language or "ru-RU").strip() or "ru-RU",
            timeout=timeout,
        )
        return audio, mime, "yandex"

    audio = await _synthesize_openai(plain, voice=mapped_voice, timeout=timeout)
    return audio, "audio/mpeg", "openai"


async def _synthesize_yandex(
    text: str,
    *,
    voice: str,
    lang: str,
    timeout: float,
) -> tuple[bytes, str]:
    api_key = (settings.YANDEX_SPEECHKIT_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("yandex_speechkit_key_missing")

    folder_id = (settings.YANDEX_SPEECHKIT_FOLDER_ID or "").strip()
    # mp3 — лучше воспроизводится в мобильных браузерах, чем oggopus.
    data = {
        "text": text,
        "lang": lang,
        "voice": voice,
        "format": "mp3",
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
        logger.warning("yandex tts failed status=%s body=%s", response.status_code, response.text[:200])
        response.raise_for_status()
    if not response.content:
        raise RuntimeError("yandex_tts_empty_response")
    logger.info(
        "yandex tts ok voice=%s chars=%s bytes=%s folder=%s",
        voice,
        len(text),
        len(response.content),
        folder_id or "-",
    )
    return response.content, "audio/mpeg"


async def _synthesize_openai(text: str, *, voice: str, timeout: float) -> bytes:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("openai_api_key_missing")

    client = AsyncOpenAI(api_key=api_key, timeout=timeout)
    try:
        result = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
    except Exception:
        logger.exception("openai tts failed")
        raise
    content = getattr(result, "content", None)
    if content:
        return bytes(content)
    if hasattr(result, "read"):
        return await result.read()
    raise RuntimeError("openai_tts_empty_response")
