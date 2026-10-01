from types import SimpleNamespace

from app.services.custom.conversation_guard import (
    conversation_has_link,
    entity_matches_peer_keys,
    incoming_asks_for_link,
    offer_fields,
    peer_dialog_text_ok,
    peer_identity_keys,
    sanitize_dm_text,
    sanitize_public_text,
    text_contains_url,
)
from app.services.custom.telegram_error_handler import _classify_telegram_error


def test_links_are_stripped_unless_explicitly_asked():
    hello = "Хей, давно не писал. Как ты?"
    assert incoming_asks_for_link(hello) is False
    dumped = "Глянь SEO-Джарвис https://seo-jarvis.ru/?utm_source=telegram промокод JARVIS10"
    assert text_contains_url(dumped) is True
    assert "http" not in sanitize_dm_text(dumped, allow_link=False).lower()
    assert incoming_asks_for_link("Да, скинь ссылку, тоже хочу попробовать") is True
    url, promo = offer_fields(url="https://seo-jarvis.ru", promo="JARVIS10", allow_link=False)
    assert url == ""
    assert promo == ""
    url, promo = offer_fields(url="https://seo-jarvis.ru", promo="JARVIS10", allow_link=True)
    assert url.startswith("https://")
    assert conversation_has_link([hello, dumped]) is True


def test_pool_peers_match_username_and_display_name():
    keys = peer_identity_keys(username="MikhailKamen1", display_name="Mihail Kamen")
    keys.update(peer_identity_keys(username="MaksimToples", display_name="Maksim Toples🔞"))
    peer = SimpleNamespace(username="maksimtoples", first_name="Maksim", last_name="Toples🔞")
    stranger = SimpleNamespace(username="random_seo", first_name="Ivan", last_name="Petrov")
    assert entity_matches_peer_keys(peer, keys) is True
    assert entity_matches_peer_keys(stranger, keys) is False


def test_peer_dialog_rejects_product_pitch():
    assert peer_dialog_text_ok("Да норм, просто завал небольшой.") is True
    assert peer_dialog_text_ok("Заходи через https://seo-jarvis.ru по промокоду JARVIS") is False
    assert "http" not in sanitize_public_text("Лови seojarvis.ru и промо JARVIS10")


def test_expired_invite_does_not_park_the_account():
    class InviteHashExpiredError(Exception):
        pass

    InviteHashExpiredError.__name__ = "InviteHashExpiredError"
    kind = _classify_telegram_error(InviteHashExpiredError("invite hash expired"))["kind"]
    assert kind == "invite_invalid"


def test_join_module_catches_expired_invite_by_name():
    from app.services.custom.chat_join_service import InviteHashExpiredError, InviteHashInvalidError

    assert issubclass(InviteHashExpiredError, BaseException)
    assert issubclass(InviteHashInvalidError, BaseException)


async def test_leave_skips_frozen_account():
    from app.services.custom.chat_join_service import leave_chat_for_account

    account = SimpleNamespace(
        is_frozen=True,
        is_banned=False,
        is_active=True,
        session_file_path="sessions/x.session",
    )
    result = await leave_chat_for_account(None, SimpleNamespace(), account)
    assert result["status"] == "skipped"
    assert result["error"] == "account_unavailable"


def test_expired_invite_is_permanent_and_hidden():
    from app.services.custom.chat_join_service import _join_error_is_permanent
    from app.services.custom.telegram_error_handler import is_comments_unusable, is_operational_skip_error

    assert _join_error_is_permanent("Ссылка-приглашение истекла") is True
    assert _join_error_is_permanent("invite hash expired") is True
    assert is_operational_skip_error("Ссылка-приглашение истекла", {"blackbox": True}) is True
    class ChannelPrivateError(Exception):
        pass
    assert is_comments_unusable(ChannelPrivateError("The channel specified is private")) is True
    assert is_comments_unusable(Exception("You can't write in this chat (caused by SetTypingRequest)")) is True
