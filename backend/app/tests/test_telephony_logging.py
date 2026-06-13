from app.telephony.logging import redact_telephony_log_message


def test_redact_api_key_in_logs():
    raw = "failed api_key=supersecret1234567890 for caller +79001234567"
    out = redact_telephony_log_message(raw)
    assert "supersecret" not in out
    assert "REDACTED" in out
