from app.telephony.prosody import format_spoken_numbers, wrap_ssml_prosody


def test_format_time_colon():
    out = format_spoken_numbers("Запись на 15:00")
    assert "пятнадцать" in out.lower()
    assert "15:00" not in out


def test_wrap_ssml_prosody():
    out = wrap_ssml_prosody("Добрый день")
    assert out.startswith("<speak>")
    assert "prosody" in out
