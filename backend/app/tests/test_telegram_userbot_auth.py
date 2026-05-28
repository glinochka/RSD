import pytest

from app.services.telegram_userbot_auth import (
    TelegramUserbotAuthError,
    _find_tdata_dir,
    opentele_available,
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
