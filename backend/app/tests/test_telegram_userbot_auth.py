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
    device_family_of,
    ensure_account_device,
    family_for_api_id,
    opentele_available,
    pick_device_profile,
    qr_url_to_data_url,
    resolve_api_credentials,
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
