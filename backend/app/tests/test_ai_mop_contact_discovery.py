"""Тесты OSINT-модуля поиска контактов ИИ МОП."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai_mop.contact_discovery import (
    build_merged_contact_bundle,
    collect_messenger_channels_from_bundle,
    normalize_org_name_key,
    outreach_target_dedup_key,
)


def test_normalize_org_name_key_collapses_spaces():
    assert normalize_org_name_key("  ООО  Тест  ") == "ооо тест"


def test_outreach_target_dedup_key_telegram_username_vs_phone():
    user_key = outreach_target_dedup_key(channel="telegram_userbot", target="somebrand")
    phone_key = outreach_target_dedup_key(channel="telegram_userbot", target="+79991234567")
    assert user_key != phone_key


def test_outreach_target_dedup_key_same_phone_different_format():
    a = outreach_target_dedup_key(channel="telegram_userbot", target="+79991234567")
    b = outreach_target_dedup_key(channel="telegram_userbot", target="79991234567")
    assert a == b


def test_build_merged_contact_bundle_mines_comment_text():
    lead = SimpleNamespace(
        org_name="ООО Кафе",
        lpr_name=None,
        phone="+74831234567",
        telegram=None,
        whatsapp=None,
        extra_json=(
            '{"comment": "пишите в t.me/cafe_owner или @cafe_owner, WA: https://wa.me/79998887766"}'
        ),
    )
    bundle = build_merged_contact_bundle(lead)
    assert "https://wa.me/79998887766" in bundle.whatsapp_links or any(
        "79998887766" in w for w in bundle.whatsapp_links
    )
    assert any("cafe_owner" in t for t in bundle.telegram_links)


def test_collect_messenger_channels_two_telegram_chats_not_merged():
    bundle = build_merged_contact_bundle(
        SimpleNamespace(
            org_name="ООО Тест",
            lpr_name=None,
            phone="+79991112233",
            telegram="https://t.me/brand_shop",
            whatsapp=None,
            extra_json='{"telegram": "@brand_owner"}',
        )
    )
    channels = collect_messenger_channels_from_bundle(
        bundle,
        whatsapp_available=False,
        telegram_available=True,
        max_available=False,
    )
    tg_targets = {t for c, t, _ in channels if c == "telegram_userbot"}
    assert "brand_shop" in tg_targets or any("brand_shop" in t for t in tg_targets)
    assert "brand_owner" in tg_targets or any("brand_owner" in t for t in tg_targets)
    assert len(tg_targets) >= 2


def test_collect_messenger_channels_no_duplicate_same_chat():
    bundle = build_merged_contact_bundle(
        SimpleNamespace(
            org_name="ООО Тест",
            lpr_name=None,
            phone="+79991234567",
            telegram="https://t.me/+79991234567",
            whatsapp="https://wa.me/79991234567",
            extra_json='{"org_mobile": "+7 999 123-45-67"}',
        )
    )
    channels = collect_messenger_channels_from_bundle(
        bundle,
        whatsapp_available=True,
        telegram_available=True,
        max_available=False,
    )
    keys = [outreach_target_dedup_key(channel=c, target=t) for c, t, _ in channels]
    assert len(keys) == len(set(keys))


def test_crm_row_enriches_phones():
    crm = SimpleNamespace(
        lpr_name="Иван",
        lpr_phone="+79990001122",
        org_phone=None,
        org_mobile=None,
        telegram="https://t.me/crm_contact",
        whatsapp=None,
        messenger_max=None,
        extra_json=None,
        comment=None,
        import_status=None,
    )
    lead = SimpleNamespace(
        org_name="ООО Кафе",
        lpr_name=None,
        phone=None,
        telegram=None,
        whatsapp=None,
        extra_json=None,
    )
    bundle = build_merged_contact_bundle(lead, crm_rows=[crm])
    assert bundle.lpr_phone == "+79990001122" or "+79990001122" in bundle.extra_phones
    assert any("crm_contact" in t for t in bundle.telegram_links)


@pytest.mark.asyncio
async def test_discover_ai_mop_outreach_targets_monkeypatch(monkeypatch):
    from app.services.ai_mop import contact_discovery as mod

    async def _avail(agent_id: int):
        del agent_id
        return mod.AgentMessengerAvailability(whatsapp=True, telegram=True, max_userbot=False)

    async def _crm(org_name: str, *, limit: int = 5):
        del org_name, limit
        return []

    async def _imp(agent_id: int, org_name: str, *, limit: int = 10):
        del agent_id, org_name, limit
        return []

    monkeypatch.setattr(mod, "get_agent_messenger_availability", _avail)
    monkeypatch.setattr(mod, "_fetch_crm_rows_for_org", _crm)
    monkeypatch.setattr(mod, "_fetch_agent_imported_rows", _imp)

    lead = SimpleNamespace(
        id=1,
        org_name="ООО Тест",
        lpr_name=None,
        phone="+79991234567",
        telegram="https://t.me/shop",
        whatsapp=None,
        extra_json=None,
    )
    result = await mod.discover_ai_mop_outreach_targets(agent_id=1, lead=lead)
    assert result.has_messenger_channel
    assert any(c == "telegram_userbot" for c, _, _ in result.messengers)
