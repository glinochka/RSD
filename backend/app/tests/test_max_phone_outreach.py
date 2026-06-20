"""Тесты нормализации телефонов для MAX outreach."""

from app.services.max_userbot_session import (
    is_max_phone_target,
    normalize_max_phone_e164,
)


def test_normalize_max_phone_e164_ru_mobile() -> None:
    assert normalize_max_phone_e164("8 (999) 123-45-67") == "+79991234567"
    assert normalize_max_phone_e164("+79991234567") == "+79991234567"


def test_is_max_phone_target() -> None:
    assert is_max_phone_target("+79991234567") is True
    assert is_max_phone_target("123456789") is False
