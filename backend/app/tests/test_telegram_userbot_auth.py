import pytest

from types import SimpleNamespace

from app.services.telegram_userbot_auth import (
    DEVICE_MODEL_MAIN,
    FAMILY_ANDROID,
    FAMILY_DESKTOP,
    FAMILY_IOS,
    TelegramUserbotAuthError,
    _TELEGRAM_ANDROID_API_ID,
    _TELEGRAM_DESKTOP_API_ID,
    _TELEGRAM_IOS_API_ID,
    _find_tdata_dir,
    create_telegram_client,
    device_family_of,
    ensure_account_device,
    family_for_api_id,
    lang_pack_for_family,
    locale_for_phone,
    opentele_available,
    pick_device_profile,
    qr_url_to_data_url,
    resolve_api_credentials,
    tz_offset_seconds,
)


def test_qr_url_to_data_url():
    data_url = qr_url_to_data_url("tg://login?token=test")
    assert data_url.startswith("data:image/png;base64,")


def test_find_tdata_dir_nested():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tdata = root / "tdata"
        tdata.mkdir()
        (tdata / "key_datas").write_bytes(b"x")
        assert _find_tdata_dir(root) == tdata


def test_resolve_api_credentials_custom():
    api_id, api_hash = resolve_api_credentials(12345, "a" * 32)
    assert api_id == 12345
    assert api_hash == "a" * 32


def test_resolve_api_credentials_builtin_fallback():
    api_id, api_hash = resolve_api_credentials(None, None, prefer_desktop=True)
    assert api_id == 2040
    assert api_hash == "b18441a1ff607e10a989891a5462e627"


def test_resolve_api_credentials_ios_family():
    api_id, api_hash = resolve_api_credentials(None, None, family="ios")
    assert api_id == _TELEGRAM_IOS_API_ID
    assert len(api_hash) >= 16


def test_device_family_matches_official_api():
    from app.services.telegram_userbot_auth import _DEVICE_PROFILES

    assert family_for_api_id(_TELEGRAM_DESKTOP_API_ID) == FAMILY_DESKTOP
    assert family_for_api_id(_TELEGRAM_ANDROID_API_ID) == FAMILY_ANDROID
    assert family_for_api_id(_TELEGRAM_IOS_API_ID) == FAMILY_IOS
    models = {item["device_model"] for item in _DEVICE_PROFILES}
    assert "iPhone 16 Pro" in models
    assert "iPhone 17 Pro" in models
    assert "Samsung SM-S941B" in models
    iphone = pick_device_profile(seed="phone-a", family=FAMILY_IOS)
    assert iphone["family"] == FAMILY_IOS
    assert "iPhone" in iphone["device_model"]
    samsung = pick_device_profile(seed="phone-b", family=FAMILY_ANDROID)
    assert samsung["family"] == FAMILY_ANDROID
    assert "iPhone" not in samsung["device_model"]
    mixed = {pick_device_profile(seed=f"mix-{i}", mix=True)["family"] for i in range(80)}
    assert {FAMILY_DESKTOP, FAMILY_ANDROID, FAMILY_IOS} <= mixed


def test_ensure_account_device_keeps_existing_and_migrates_legacy():
    kept = SimpleNamespace(
        id=1,
        phone_number="+7999",
        telegram_device={"device_model": "MacBook Pro", "system_version": "macOS 15.0", "app_version": "5.8.1 x64", "lang_code": "ru", "system_lang_code": "ru-RU"},
    )
    profile = ensure_account_device(kept)
    assert profile["device_model"] == "MacBook Pro"
    assert profile["family"] == FAMILY_DESKTOP
    legacy = SimpleNamespace(id=2, phone_number="+7000", telegram_device={"device_model": DEVICE_MODEL_MAIN})
    migrated = ensure_account_device(legacy, api_id=_TELEGRAM_DESKTOP_API_ID)
    assert migrated["device_model"] != DEVICE_MODEL_MAIN
    assert migrated["family"] == FAMILY_DESKTOP
    android_session = SimpleNamespace(id=3, phone_number="+7111", telegram_device=None)
    android = ensure_account_device(android_session, api_id=_TELEGRAM_ANDROID_API_ID)
    assert android["family"] == FAMILY_ANDROID
    assert device_family_of(android) == FAMILY_ANDROID


def test_locale_follows_phone_country_not_forced_russian():
    assert locale_for_phone("+79991234567") == ("ru", "ru-RU", "Europe/Moscow")
    assert locale_for_phone("+380671234567")[:2] == ("uk", "uk-UA")
    assert locale_for_phone("+491511234567")[:2] == ("de", "de-DE")
    assert locale_for_phone("+12025550123")[:2] == ("en", "en-US")
    ua = pick_device_profile(seed="ua-1", mix=True, phone="+380671234567")
    assert ua["lang_code"] == "uk"
    assert ua["system_lang_code"] == "uk-UA"
    assert ua["lang_pack"] in {"tdesktop", "android", "ios"}
    assert ua["tz_name"] == "Europe/Kyiv"
    de = pick_device_profile(seed="de-1", family=FAMILY_ANDROID, phone="+491511234567")
    assert de["lang_code"] == "de"
    assert de["lang_pack"] == "android"
    ru = pick_device_profile(seed="ru-1", family=FAMILY_IOS, phone="+79990001122")
    assert ru["lang_code"] == "ru"
    assert ru["system_lang_code"] == "ru-RU"
    assert ru["lang_pack"] == "ios"


def test_ensure_account_device_rewrites_forced_ru_for_foreign_numbers():
    ua = SimpleNamespace(
        id=9,
        phone_number="+380671111111",
        telegram_device={
            "device_model": "Google Pixel 9",
            "system_version": "SDK 35",
            "app_version": "11.12.3",
            "lang_code": "ru",
            "system_lang_code": "ru-RU",
        },
    )
    profile = ensure_account_device(ua)
    assert profile["lang_code"] == "uk"
    assert profile["system_lang_code"] == "uk-UA"
    assert profile["device_model"] == "Google Pixel 9"
    assert profile["lang_pack"] == "android"
    ru = SimpleNamespace(
        id=10,
        phone_number="+79990000000",
        telegram_device={
            "device_model": "Google Pixel 9",
            "system_version": "SDK 35",
            "app_version": "11.12.3",
            "lang_code": "ru",
            "system_lang_code": "ru-RU",
        },
    )
    kept = ensure_account_device(ru)
    assert kept["lang_code"] == "ru"
    assert kept["system_lang_code"] == "ru-RU"


def test_create_telegram_client_stamps_official_lang_pack():
    profile = pick_device_profile(seed="stamp-1", family=FAMILY_ANDROID, phone="+491511234567")
    client, api_id, _hash = create_telegram_client(
        family=FAMILY_ANDROID,
        device_profile=profile,
        session_string="",
    )
    req = client._init_request
    assert api_id == _TELEGRAM_ANDROID_API_ID
    assert req.lang_pack == "android"
    assert req.lang_code == "de"
    assert req.system_lang_code == "de-DE"
    assert req.params is not None
    assert "tz_offset" in [item.key for item in req.params.value]
    assert tz_offset_seconds("Europe/Moscow") == 3 * 3600
    assert lang_pack_for_family(FAMILY_DESKTOP) == "tdesktop"
    assert lang_pack_for_family(FAMILY_IOS) == "ios"
    closer = getattr(getattr(client, "session", None), "close", None)
    if callable(closer):
        closer()


@pytest.mark.skipif(not opentele_available(), reason="opentele not installed")
def test_resolve_api_credentials_opentele_default():
    api_id, api_hash = resolve_api_credentials(None, None)
    assert api_id > 0
    assert len(api_hash) >= 16


@pytest.mark.asyncio
async def test_import_session_file_rejects_empty():
    from app.services.telegram_userbot_auth import import_session_file

    with pytest.raises(TelegramUserbotAuthError):
        await import_session_file(
            api_id=1,
            api_hash="a" * 32,
            filename="empty.txt",
            content=b"   ",
        )
