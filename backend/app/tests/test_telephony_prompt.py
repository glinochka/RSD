from app.telephony.compliance import recording_disclaimer_text
from app.telephony.prompt import apply_phone_style_instructions


def test_apply_phone_style_instructions_appends_voice_block():
    out = apply_phone_style_instructions("You are helpful.")
    assert "Голосовой канал" in out
    assert out.startswith("You are helpful.")


def test_recording_disclaimer_not_empty():
    assert "записан" in recording_disclaimer_text().lower()
