"""Тесты нормализации контактов Excel для sales_manager outreach."""

from app.services.sales.contact_target_resolver import (
    build_import_dedup_key,
    normalize_telegram_target,
    normalize_whatsapp_target,
    pick_outreach_channel,
)


def test_normalize_whatsapp_from_wa_me() -> None:
    target, _hint = normalize_whatsapp_target(whatsapp="https://wa.me/79395030304")
    assert target == "79395030304"


def test_normalize_telegram_from_t_me_phone() -> None:
    target, hint = normalize_telegram_target(telegram="https://t.me/89770890409")
    assert target == "+79770890409"
    assert hint.get("source") == "telegram_link"


def test_normalize_telegram_username() -> None:
    target, _ = normalize_telegram_target(telegram="https://t.me/somebrand")
    assert target == "somebrand"


def test_pick_outreach_prefers_whatsapp_column() -> None:
    row = {
        "org_name": "ООО Тест",
        "whatsapp": "https://wa.me/79001234567",
        "telegram": "https://t.me/somebrand",
        "lpr_phone": "+7 900 123-45-67",
    }
    channel, target, _ = pick_outreach_channel(
        row,
        whatsapp_available=True,
        telegram_available=True,
    )
    assert channel == "whatsapp_userbot"
    assert target == "79001234567"


def test_pick_outreach_telegram_when_only_tg_column() -> None:
    row = {
        "org_name": "ООО Тест",
        "telegram": "https://t.me/somebrand",
    }
    channel, target, _ = pick_outreach_channel(
        row,
        whatsapp_available=True,
        telegram_available=True,
    )
    assert channel == "telegram_userbot"
    assert target == "somebrand"


def test_build_import_dedup_key_stable() -> None:
    k1 = build_import_dedup_key(
        org_name="  ООО Ромашка ",
        channel="whatsapp_userbot",
        target_external_id="79001234567",
    )
    k2 = build_import_dedup_key(
        org_name="ооо ромашка",
        channel="whatsapp_userbot",
        target_external_id="79001234567",
    )
    assert k1 == k2
