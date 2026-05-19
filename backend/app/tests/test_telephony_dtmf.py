from app.telephony.dtmf import dtmf_menu_prompt, dtmf_transcript


def test_dtmf_transcript_digits():
    assert "запис" in dtmf_transcript("1").lower()
    assert "оператор" in dtmf_transcript("2").lower()
    assert dtmf_transcript("9") is None


def test_dtmf_menu_prompt():
    assert "1" in dtmf_menu_prompt() and "2" in dtmf_menu_prompt()
