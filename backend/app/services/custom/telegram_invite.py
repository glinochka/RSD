"""Parse and normalize Telegram chat/channel links, usernames and invite hashes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse

TelegramChatKind = Literal["username", "invite", "channel_id"]

TELEGRAM_HOSTS = {
    "t.me",
    "www.t.me",
    "telegram.me",
    "www.telegram.me",
    "telegram.dog",
    "www.telegram.dog",
}

_RESERVED_PATHS = {
    "addstickers",
    "addemoji",
    "addtheme",
    "share",
    "proxy",
    "socks",
    "setlanguage",
    "iv",
    "login",
    "confirmphone",
    "invoice",
    "giftcode",
    "nft",
    "boost",
    "boosts",
    "addlist",
    "contact",
    "joinchat",
    "a",
    "k",
    "m",
}

_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_INVITE_HASH_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_CHANNEL_ID_RE = re.compile(r"^-100\d{6,}$")
_DIGITS_RE = re.compile(r"^\d{6,}$")
_BARE_HOST_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/",
    re.IGNORECASE,
)


class TelegramChatRefError(ValueError):
    """Raised when the value is not a Telegram chat, channel or invite."""


@dataclass(frozen=True)
class TelegramChatRef:
    kind: TelegramChatKind
    value: str
    canonical: str
    is_private: bool

    @property
    def lookup_value(self) -> str | int:
        if self.kind == "channel_id":
            return int(self.value)
        if self.kind == "username":
            return self.value
        return self.canonical


def parse_telegram_chat_ref(raw: str | None) -> TelegramChatRef:
    """Accept https/t.me/@username/invite forms and return a canonical ref."""
    if raw is None:
        raise TelegramChatRefError("Укажите ссылку, @username или имя канала")
    text = str(raw).strip().strip("\"'")
    if not text:
        raise TelegramChatRefError("Укажите ссылку, @username или имя канала")

    lower = text.lower()
    if lower.startswith("tg://") or lower.startswith("tg:"):
        return _from_tg_scheme(text)
    if _BARE_HOST_RE.match(text) and "://" not in text:
        text = f"https://{text}"
        lower = text.lower()
    if "://" in text:
        return _from_url(text)

    if text.startswith("@"):
        return _username_ref(text[1:])
    if text.startswith("+"):
        return _invite_ref(text[1:])
    if lower.startswith("joinchat/"):
        return _invite_ref(text.split("/", 1)[1])
    if _CHANNEL_ID_RE.fullmatch(text) or _DIGITS_RE.fullmatch(text):
        return _channel_id_ref(text)
    if _USERNAME_RE.fullmatch(text):
        return _username_ref(text)
    raise TelegramChatRefError(
        "Некорректная ссылка. Можно: https://t.me/name, t.me/name, @name или name"
    )


def chat_entity_key(chat_target: Any) -> str | int:
    """Best Telethon get_entity argument for a saved ChatTarget."""
    link = getattr(chat_target, "invite_link", None)
    if link:
        try:
            parsed = parse_telegram_chat_ref(str(link))
            if parsed.kind == "username":
                return parsed.lookup_value
        except TelegramChatRefError:
            pass
    ext = getattr(chat_target, "external_chat_id", None)
    if ext:
        text = str(ext).strip()
        if text.lstrip("-").isdigit():
            return int(text)
        try:
            return parse_telegram_chat_ref(text).lookup_value
        except TelegramChatRefError:
            return text
    link = getattr(chat_target, "invite_link", None)
    if link:
        parsed = parse_telegram_chat_ref(str(link))
        if parsed.kind == "invite":
            return parsed.canonical
        return parsed.lookup_value
    title = getattr(chat_target, "title", None)
    if title and str(title).strip():
        return str(title).strip()
    raise TelegramChatRefError("Нет идентификатора чата")


def _username_ref(username: str) -> TelegramChatRef:
    name = (username or "").strip().lstrip("@")
    if name.endswith("/"):
        name = name.rstrip("/")
    if not _USERNAME_RE.fullmatch(name):
        raise TelegramChatRefError("Некорректное имя канала или чата")
    slug = name.lower()
    return TelegramChatRef(
        kind="username",
        value=slug,
        canonical=f"https://t.me/{slug}",
        is_private=False,
    )


def _invite_ref(hash_value: str) -> TelegramChatRef:
    invite_hash = unquote((hash_value or "").strip()).lstrip("+")
    if invite_hash.lower().startswith("joinchat/"):
        invite_hash = invite_hash.split("/", 1)[-1]
    if invite_hash.isdigit():
        raise TelegramChatRefError("Это похоже на номер телефона. Нужна ссылка на чат или канал")
    if not _INVITE_HASH_RE.fullmatch(invite_hash):
        raise TelegramChatRefError("Некорректная ссылка-приглашение")
    return TelegramChatRef(
        kind="invite",
        value=invite_hash,
        canonical=f"https://t.me/+{invite_hash}",
        is_private=True,
    )


def _channel_id_ref(raw_id: str) -> TelegramChatRef:
    digits = str(raw_id).strip()
    if digits.startswith("-100"):
        internal = digits[4:]
        full = digits
    else:
        internal = digits
        full = f"-100{digits}"
    if not internal.isdigit() or len(internal) < 6:
        raise TelegramChatRefError("Некорректный id канала")
    return TelegramChatRef(
        kind="channel_id",
        value=full,
        canonical=f"https://t.me/c/{internal}",
        is_private=True,
    )


def _from_tg_scheme(text: str) -> TelegramChatRef:
    parsed = urlparse(text)
    query = parse_qs(parsed.query)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip("/").lower()
    if host == "join" or path == "join":
        invite = (query.get("invite") or [""])[0]
        return _invite_ref(invite)
    domain = (query.get("domain") or [""])[0]
    if domain:
        return _username_ref(domain)
    raise TelegramChatRefError("Некорректная Telegram-ссылка")


def _from_url(text: str) -> TelegramChatRef:
    parsed = urlparse(text.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise TelegramChatRefError("Некорректная ссылка. Можно: https://t.me/name, t.me/name, @name или name")
    host = (parsed.netloc or "").lower().split("@")[-1].split(":")[0]
    if host not in TELEGRAM_HOSTS:
        raise TelegramChatRefError("Нужна ссылка t.me, @username или имя канала")
    path = unquote(parsed.path or "").strip("/")
    if not path:
        raise TelegramChatRefError("В ссылке нет имени чата или канала")
    parts = [part for part in path.split("/") if part]
    first = parts[0]
    first_lower = first.lower()
    if first.startswith("+"):
        return _invite_ref(first[1:])
    if first_lower == "joinchat":
        if len(parts) < 2:
            raise TelegramChatRefError("Некорректная ссылка-приглашение")
        return _invite_ref(parts[1])
    if first_lower == "s" and len(parts) >= 2:
        return _username_ref(parts[1].split("?")[0])
    if first_lower == "c" and len(parts) >= 2:
        return _channel_id_ref(parts[1].split("?")[0])
    if first_lower in _RESERVED_PATHS:
        raise TelegramChatRefError("Это не ссылка на чат или канал")
    return _username_ref(first.split("?")[0])
