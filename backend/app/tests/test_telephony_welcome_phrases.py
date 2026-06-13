"""Telephony welcome / routing phrase helpers."""

from app.telephony.orchestrator_worker import (
    DEFAULT_TELEPHONY_WELCOME,
    resolve_telephony_welcome_text,
)


def test_resolve_telephony_welcome_text_uses_default_when_empty():
    assert resolve_telephony_welcome_text(None) == DEFAULT_TELEPHONY_WELCOME
    assert resolve_telephony_welcome_text("   ") == DEFAULT_TELEPHONY_WELCOME


def test_resolve_telephony_welcome_text_keeps_agent_message():
    custom = "Добрый день, клиника на Ленина."
    assert resolve_telephony_welcome_text(custom) == custom
