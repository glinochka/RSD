import pytest

from app.router_agents.telephony_preview import (
    BROWSER_PREVIEW_SOURCE,
    _compress_turn_history,
    _logic_preview_session_id,
    _preview_source_fields,
    _validate_logic_preview_session_id,
    strip_ssml_for_browser,
)
from app.services.telephony_orchestrator import DialogState


def test_preview_source_fields():
    assert _preview_source_fields() == {
        "source": BROWSER_PREVIEW_SOURCE,
        "channel": "browser_preview",
    }


def test_strip_ssml_for_browser():
    assert strip_ssml_for_browser("Привет") == "Привет"
    raw = '<speak><prosody rate="95%">Здравствуйте</prosody></speak>'
    assert strip_ssml_for_browser(raw) == "Здравствуйте"


def test_compress_turn_history():
    history = [
        {"role": "user", "text": "Хочу записаться"},
        {"role": "agent", "text": "На какое время?"},
    ]
    compressed = _compress_turn_history(history)
    assert "Абонент: Хочу записаться" in compressed
    assert "Оператор: На какое время?" in compressed


def test_logic_preview_session_id_prefix():
    sid = _logic_preview_session_id(42)
    assert sid.startswith("web-logic:42:")
    _validate_logic_preview_session_id(sid, 42)


def test_logic_preview_session_id_rejects_other_user():
    sid = _logic_preview_session_id(1)
    with pytest.raises(Exception):
        _validate_logic_preview_session_id(sid, 2)


def test_preview_isolated_from_media_gateway():
    from app.telephony.preview_guard import assert_preview_isolated

    assert_preview_isolated()


def test_shim_dialog_state_default():
    from app.router_agents.telephony_preview import _shim_from_dialog_state

    shim = _shim_from_dialog_state(owner_user_id=5, dialog_state=None)
    assert shim.metadata_["dialog_state"] == DialogState.GREET.value
