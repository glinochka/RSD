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
    assert hint.get("source") == "telegram_link_phone"


def test_normalize_telegram_username() -> None:
    target, _ = normalize_telegram_target(telegram="https://t.me/somebrand")
    assert target == "somebrand"


def test_normalize_telegram_bot_link_uses_mobile() -> None:
    from app.services.sales.contact_target_resolver import collect_all_telegram_outreach_targets

    targets = collect_all_telegram_outreach_targets(
        telegram="https://t.me/somechannel_bot",
        org_mobile="+79991234567",
    )
    assert "+79991234567" in {t for t, _ in targets}


def test_collect_all_messenger_includes_link_and_phones() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {
        "telegram": "https://t.me/somebrand",
        "whatsapp": "https://wa.me/79001234567",
        "org_mobile": "+79998887766",
        "org_phone": "+74831234567",
        "lpr_phone": "+79991112233",
    }
    channels = collect_all_messenger_channels(row, whatsapp_available=True, telegram_available=True)
    keys = {(c, t) for c, t, _ in channels}
    assert ("telegram_userbot", "somebrand") in keys
    assert ("telegram_userbot", "+79998887766") in keys
    assert ("whatsapp_userbot", "79001234567") in keys
    assert ("whatsapp_userbot", "79998887766") in keys
    # без дублей wa.me и того же мобильного
    assert len(channels) == len({f"{c}:{t}" for c, t, _ in channels})


def test_collect_all_messenger_cross_channel_from_wa_link_only() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {"whatsapp": "https://wa.me/79001234567"}
    channels = collect_all_messenger_channels(row, whatsapp_available=True, telegram_available=True)
    keys = {(c, t) for c, t, _ in channels}
    assert ("whatsapp_userbot", "79001234567") in keys
    assert ("telegram_userbot", "+79001234567") in keys


def test_collect_all_messenger_cross_channel_from_tg_phone_link() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {"telegram": "https://t.me/89770890409"}
    channels = collect_all_messenger_channels(row, whatsapp_available=True, telegram_available=True)
    keys = {(c, t) for c, t, _ in channels}
    assert ("telegram_userbot", "+79770890409") in keys
    assert ("whatsapp_userbot", "79770890409") in keys


def test_collect_all_messenger_no_cross_from_tg_username_only() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {"telegram": "https://t.me/somebrand"}
    channels = collect_all_messenger_channels(row, whatsapp_available=True, telegram_available=True)
    wa_targets = [t for c, t, _ in channels if c == "whatsapp_userbot"]
    assert wa_targets == []


def test_attach_target_hint_to_dm_meta_flattens_fallbacks() -> None:
    from app.services.sales.contact_target_resolver import attach_target_hint_to_dm_meta

    meta = attach_target_hint_to_dm_meta(
        {"channel": "whatsapp_userbot"},
        {"source": "whatsapp", "fallback_targets": ["79991234567", "+79997654321"]},
    )
    assert meta["fallback_targets"] == ["79991234567", "+79997654321"]
    assert meta["target_resolve_hint"]["source"] == "whatsapp"


def test_normalize_telegram_username_keeps_phone_fallbacks() -> None:
    _target, hint = normalize_telegram_target(
        telegram="https://t.me/somebrand",
        org_mobile="+79991234567",
        org_phone="+74831234567",
    )
    assert "+79991234567" in (hint.get("fallback_targets") or [])


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


def test_normalize_max_target_from_messenger_max_column() -> None:
    from app.services.sales.contact_target_resolver import normalize_max_target

    target, hint = normalize_max_target(messenger_max="8 (999) 111-22-33")
    assert target == "+79991112233"
    assert hint.get("source") == "messenger_max"


def test_collect_all_messenger_includes_max_when_available() -> None:
    from app.services.sales.contact_target_resolver import collect_all_messenger_channels

    row = {
        "org_mobile": "+79991234567",
        "messenger_max": "+79998887766",
    }
    channels = collect_all_messenger_channels(
        row,
        whatsapp_available=False,
        telegram_available=False,
        max_available=True,
    )
    assert ("max_userbot", "+79998887766") in [(c, t) for c, t, _ in channels]
    assert ("max_userbot", "+79991234567") in [(c, t) for c, t, _ in channels]


def test_normalize_max_target_from_phones() -> None:
    from app.services.sales.contact_target_resolver import normalize_max_target

    target, hint = normalize_max_target(
        org_mobile="+7 999 888-77-66",
        lpr_phone="+79991112233",
    )
    assert target == "+79998887766"
    assert "+79991112233" in (hint.get("fallback_targets") or [])


def test_pick_outreach_max_when_only_max_channel() -> None:
    row = {
        "org_name": "ООО Тест",
        "org_mobile": "+79991234567",
        "lpr_phone": "+74831234567",
    }
    channel, target, hint = pick_outreach_channel(
        row,
        whatsapp_available=False,
        telegram_available=False,
        max_available=True,
    )
    assert channel == "max_userbot"
    assert target == "+79991234567"
    assert hint.get("source") == "phone"


def test_pick_outreach_max_phones_when_no_messenger_links() -> None:
    row = {
        "org_name": "ООО Тест",
        "org_mobile": "89991234567",
    }
    channel, target, _ = pick_outreach_channel(
        row,
        whatsapp_available=True,
        telegram_available=True,
        max_available=True,
    )
    # При подключённых WA/TG телефоны идут туда раньше MAX
    assert channel == "whatsapp_userbot"
    assert target == "79991234567"


def test_pick_outreach_max_only_phones_no_wa_tg() -> None:
    row = {"org_name": "ООО", "lpr_phone": "89001234567"}
    channel, target, _ = pick_outreach_channel(
        row,
        whatsapp_available=False,
        telegram_available=False,
        max_available=True,
    )
    assert channel == "max_userbot"
    assert target == "+79001234567"


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
