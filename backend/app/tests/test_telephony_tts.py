import pytest

from app.telephony.tts_service import (
    map_voice_for_provider,
    resolve_preview_tts_provider,
    _strip_for_tts,
)


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
