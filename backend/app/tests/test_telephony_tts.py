import pytest

from app.telephony.tts_service import (
    map_voice_for_provider,
    resolve_preview_tts_provider,
    _strip_for_tts,
)
from app.telephony import stream_tts


def test_strip_for_tts_removes_ssml():
    assert _strip_for_tts('<speak><prosody rate="95%">Привет</prosody></speak>') == "Привет"


def test_map_voice_yandex_default():
    assert map_voice_for_provider("yandex", "default") == "alena"
    assert map_voice_for_provider("yandex", "filipp") == "filipp"


def test_map_voice_openai_default():
    assert map_voice_for_provider("openai", "default") == "nova"


def test_resolve_preview_tts_provider_yandex(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "TELEPHONY_TTS_PROVIDER", "yandex")
    monkeypatch.setattr(settings, "YANDEX_SPEECHKIT_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    assert resolve_preview_tts_provider() == "yandex"


def test_resolve_preview_tts_voximplant_fallback_openai(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "TELEPHONY_TTS_PROVIDER", "voximplant")
    monkeypatch.setattr(settings, "YANDEX_SPEECHKIT_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    assert resolve_preview_tts_provider() == "openai"


@pytest.mark.asyncio
async def test_elevenlabs_rejects_non_pcm_content_type(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "test-key")

    class _BadResponse:
        status_code = 200
        headers = {"content-type": "audio/mpeg"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aread(self):
            return b""

        async def aiter_bytes(self):
            if False:
                yield b""

    class _BadClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return _BadResponse()

    monkeypatch.setattr(stream_tts.httpx, "AsyncClient", _BadClient)

    with pytest.raises(RuntimeError, match="elevenlabs_unexpected_content_type"):
        async for _ in stream_tts._stream_elevenlabs_pcm16("Привет", voice_id="default", timeout=1.0):
            pass
