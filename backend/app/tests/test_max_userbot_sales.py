"""Tests for sales_manager integration with MAX userbot channel."""

from app.services.sales.dm_outreach_worker import _provider_for_channel
from app.services.template_runtime import TemplateRuntimeService


def test_provider_for_channel_includes_max_userbot():
    assert _provider_for_channel("max_userbot") == "max_userbot"
    assert _provider_for_channel("telegram_userbot") == "telegram_userbot"
    assert _provider_for_channel("whatsapp_userbot") == "whatsapp_userbot"


def test_template_runtime_treats_max_userbot_as_userbot():
    assert TemplateRuntimeService._is_userbot_channel("max_userbot") is True
    assert TemplateRuntimeService._is_userbot_channel("telegram_userbot") is True
    assert TemplateRuntimeService._is_userbot_channel("telegram") is False
