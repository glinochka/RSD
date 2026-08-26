from app.services.custom.telegram_invite import (
    TelegramChatRefError,
    chat_entity_key,
    parse_telegram_chat_ref,
)
from app.services.custom.chat_scope import apply_entity_metadata, entity_chat_type, is_user_peer


class _Chat:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_parse_public_usernames_and_urls():
    expected = "https://t.me/seo_chat"
    samples = [
        "https://t.me/seo_chat",
        "http://t.me/seo_chat",
        "https://t.me/seo_chat/12",
        "t.me/seo_chat",
        "https://telegram.me/seo_chat",
        "@seo_chat",
        "seo_chat",
        "https://t.me/s/seo_chat",
        "tg://resolve?domain=seo_chat",
    ]
    for raw in samples:
        parsed = parse_telegram_chat_ref(raw)
        assert parsed.kind == "username"
        assert parsed.value == "seo_chat"
        assert parsed.canonical == expected
        assert parsed.is_private is False


def test_parse_private_invites():
    expected = "https://t.me/+AbCdEfGhIjKl"
    samples = [
        "https://t.me/+AbCdEfGhIjKl",
        "t.me/+AbCdEfGhIjKl",
        "+AbCdEfGhIjKl",
        "https://t.me/joinchat/AbCdEfGhIjKl",
        "t.me/joinchat/AbCdEfGhIjKl",
        "tg://join?invite=AbCdEfGhIjKl",
    ]
    for raw in samples:
        parsed = parse_telegram_chat_ref(raw)
        assert parsed.kind == "invite"
        assert parsed.value == "AbCdEfGhIjKl"
        assert parsed.canonical == expected
        assert parsed.is_private is True


def test_parse_channel_id_link():
    parsed = parse_telegram_chat_ref("https://t.me/c/1234567890/12")
    assert parsed.kind == "channel_id"
    assert parsed.value == "-1001234567890"
    assert parsed.canonical == "https://t.me/c/1234567890"
    assert parsed.lookup_value == -1001234567890


def test_parse_rejects_garbage_and_phones():
    for raw in ["", "  ", "https://google.com/x", "t.me/", "hi", "+79001234567", "https://t.me/share"]:
        try:
            parse_telegram_chat_ref(raw)
            raise AssertionError(raw)
        except TelegramChatRefError:
            pass


def test_chat_entity_key_prefers_numeric_id():
    chat = _Chat(external_chat_id="111", invite_link="https://t.me/+AbCdEfGhIjKl", title="X")
    assert chat_entity_key(chat) == 111
    chat.external_chat_id = None
    assert chat_entity_key(chat) == "https://t.me/+AbCdEfGhIjKl"


def test_apply_entity_metadata_channel_and_group():
    target = _Chat(title=None, chat_type=None, external_chat_id=None)
    channel = _Chat(id=42, title="News", broadcast=True, username="news")
    apply_entity_metadata(target, channel)
    assert target.title == "News"
    assert target.chat_type == "channel"
    assert target.external_chat_id == "42"

    group = _Chat(id=7, title="SEO", broadcast=False, megagroup=True)
    apply_entity_metadata(target, group)
    assert target.title == "SEO"
    assert target.chat_type == "chat"


def test_invite_preview_without_id_is_group():
    invite = _Chat(title="Private", broadcast=False, megagroup=True)
    assert entity_chat_type(invite) == "chat"
    assert is_user_peer(invite) is False


def test_user_peer_rejected():
    user = _Chat(id=1, first_name="Ivan")
    assert is_user_peer(user) is True
    assert entity_chat_type(user) is None
