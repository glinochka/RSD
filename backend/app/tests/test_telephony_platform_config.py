from __future__ import annotations

from app.telephony.platform_config import format_dial_with_extension, platform_telephony_public_fields


def test_format_dial_with_extension():
    assert format_dial_with_extension("+74951234567", "1234") == "+74951234567,1234"
    assert format_dial_with_extension("+74951234567", None) == "+74951234567"


def test_platform_public_fields_structure():
    public = platform_telephony_public_fields()
    assert "platform_ready" in public
    assert "shared_pool_e164" in public
    assert public["routing_mode"] == "dtmf_extension"
