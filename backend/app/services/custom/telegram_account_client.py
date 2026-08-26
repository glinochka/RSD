"""Telegram client wrapper for checking a single .session account."""
import asyncio
import io
import random
import re
from logging import getLogger
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import AuthKeyError, RPCError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoneContact

from .telegram_error_handler import SessionInvalidError, parse_spambot_reply
from ..telegram_userbot_auth import resolve_api_credentials

logger = getLogger(__name__)

_MAX_BIO_LENGTH = 160
_PHONE_DIGITS_RE = re.compile(r"\D+")
_SPAMBOT = "SpamBot"
_SPAMBOT_WAIT_SECONDS = 2.0
_session_locks: dict[str, asyncio.Lock] = {}
_session_locks_guard = asyncio.Lock()


async def _lock_for_session(session_path: str) -> asyncio.Lock:
    key = str(Path(session_path).resolve())
    async with _session_locks_guard:
        lock = _session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[key] = lock
        return lock


def normalize_telegram_phone(value: str | None) -> str | None:
    digits = _PHONE_DIGITS_RE.sub("", value or "")
    if len(digits) < 10:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) < 11:
        return None
    return f"+{digits}"


class TelegramAccountClient:
    """Connect to a saved Telethon .session and read public profile info.

    Uses the same API credential fallback chain as the rest of the platform
    (custom env -> global env -> opentele -> Telethon built-in).
    """

    def __init__(self, session_path: str, *, api_id: int | None = None, api_hash: str | None = None):
        self.session_path = session_path
        self.api_id, self.api_hash = resolve_api_credentials(api_id, api_hash, prefer_desktop=True)
        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        self._session_lock: asyncio.Lock | None = None

    async def __aenter__(self) -> "TelegramAccountClient":
        from .telegram_error_handler import _looks_like_session_error

        self._session_lock = await _lock_for_session(self.session_path)
        await self._session_lock.acquire()
        try:
            try:
                await self.client.connect()
            except Exception as exc:
                if isinstance(exc, AuthKeyError) or _looks_like_session_error(exc):
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                    raise SessionInvalidError(str(exc)) from exc
                raise
            try:
                authorized = await self.client.is_user_authorized()
            except Exception as exc:
                if isinstance(exc, AuthKeyError) or _looks_like_session_error(exc):
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                    raise SessionInvalidError(str(exc)) from exc
                raise
            if not authorized:
                await self.client.disconnect()
                raise SessionInvalidError("Session is not authorized")
            return self
        except Exception:
            self._session_lock.release()
            self._session_lock = None
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.client.disconnect()
        except Exception as exc_close:
            logger.debug("Error disconnecting Telegram client: %s", exc_close)
        if self._session_lock is not None:
            self._session_lock.release()
            self._session_lock = None

    async def get_info(self) -> dict[str, Any]:
        """Return public profile metadata without modifying the account."""
        me = await self.client.get_me()
        if not me:
            raise RuntimeError("Could not get own user")

        dialogs = await self._get_dialogs_count()
        bio = await self._get_bio(me)
        has_avatar = await self._has_avatar(me)

        return {
            "telegram_id": me.id,
            "username": me.username,
            "phone_number": me.phone,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "display_name": self._display_name(me),
            "dialogs_count": dialogs,
            "has_avatar": has_avatar,
            "bio": bio,
            "is_premium": getattr(me, "premium", False),
        }

    async def download_avatar(self, me=None) -> bytes | None:
        """Download the current profile photo as JPEG bytes."""
        target = me or await self.client.get_me()
        photos = await self.client.get_profile_photos(target, limit=1)
        if not photos:
            return None
        buf = io.BytesIO()
        try:
            await self.client.download_media(photos[0], file=buf)
        except AuthKeyError:
            logger.warning("Cannot download avatar: auth key error")
            return None
        return buf.getvalue()

    async def set_bio(self, bio: str) -> None:
        """Update account About text."""
        text = (bio or "").strip()[:_MAX_BIO_LENGTH]
        await self.client(UpdateProfileRequest(about=text))

    async def set_display_name(self, display_name: str) -> str:
        """Update Telegram first/last name. Returns the stored display name."""
        parts = (display_name or "").strip().split(None, 1)
        first = (parts[0] if parts else "User")[:64]
        last = (parts[1] if len(parts) > 1 else "")[:64]
        await self.client(UpdateProfileRequest(first_name=first, last_name=last))
        return f"{first} {last}".strip()

    async def set_avatar(self, avatar: str | bytes) -> None:
        """Upload a new profile photo from a file path or bytes."""
        if isinstance(avatar, str):
            uploaded = await self.client.upload_file(avatar)
        else:
            buf = io.BytesIO(avatar)
            buf.name = "avatar.jpg"
            uploaded = await self.client.upload_file(buf)
        await self.client(UploadProfilePhotoRequest(file=uploaded))

    async def send_message(self, recipient: str | int, text: str) -> None:
        """Send a private message to a user by username, id or phone."""
        entity = await self.resolve_peer(recipient)
        await self.client.send_message(entity, text)

    async def __call__(self, request: Any) -> Any:
        return await self.client(request)

    async def get_messages(self, *args: Any, **kwargs: Any) -> Any:
        return await self.client.get_messages(*args, **kwargs)

    async def get_entity(self, identifier: Any) -> Any:
        return await self.resolve_peer(identifier)

    async def resolve_peer(self, identifier: Any) -> Any:
        """Resolve a Telegram entity from username, t.me link, phone, numeric id or peer."""
        if identifier is None:
            raise ValueError("empty peer identifier")
        if not isinstance(identifier, str):
            return await self.client.get_entity(identifier)
        text = identifier.strip()
        if not text:
            raise ValueError("empty peer identifier")
        phone = normalize_telegram_phone(text)
        if phone and (text.startswith("+") or text.replace(" ", "").replace("-", "").isdigit()):
            return await self.resolve_phone(phone)
        if "t.me/" in text.lower():
            path = text.split("t.me/", 1)[-1].strip("/")
            if path.startswith("+") or path.lower().startswith("joinchat/"):
                phone_from_link = normalize_telegram_phone(path)
                if phone_from_link:
                    return await self.resolve_phone(phone_from_link)
                return await self.client.get_entity(text)
            username = path.split("/")[0].split("?")[0]
            return await self.client.get_entity(username)
        if text.lstrip("-").isdigit():
            return await self.client.get_entity(int(text))
        return await self.client.get_entity(text)

    async def resolve_phone(self, phone: str) -> Any:
        """Find a Telegram user by phone, same approach as ИИ МОП outreach (entity + ImportContacts)."""
        formatted = normalize_telegram_phone(phone) or phone
        try:
            return await self.client.get_entity(formatted)
        except Exception:
            logger.debug("Direct phone resolve failed for %s, trying ImportContacts", formatted)
        result = await self.client(
            ImportContactsRequest(
                [
                    InputPhoneContact(
                        client_id=random.randrange(10**6, 10**9),
                        phone=formatted,
                        first_name="Contact",
                        last_name="",
                    )
                ]
            )
        )
        users = list(getattr(result, "users", None) or [])
        if not users:
            raise ValueError(f"Telegram user not found for {formatted}")
        return users[0]

    @staticmethod
    def _display_name(me: Any) -> str:
        first = (me.first_name or "").strip()
        last = (me.last_name or "").strip()
        name = f"{first} {last}".strip()
        return name or (me.username or "").strip() or f"user_{me.id}"

    async def check_spamblock(self) -> dict[str, Any]:
        """Ask @SpamBot whether the account has a global DM spamblock.

        A ban in one chat is not a spamblock and is ignored here.
        """
        from telethon.errors import PeerFloodError

        try:
            await self.client.send_message(_SPAMBOT, "/start")
        except PeerFloodError:
            return {"spamblocked": True, "source": "peer_flood"}
        except Exception as exc:
            logger.warning("SpamBot /start failed: %s", exc)
            return {"spamblocked": None, "source": "error"}

        await asyncio.sleep(_SPAMBOT_WAIT_SECONDS)
        try:
            messages = await self.client.get_messages(_SPAMBOT, limit=5)
        except Exception as exc:
            logger.warning("SpamBot history failed: %s", exc)
            return {"spamblocked": None, "source": "error"}

        texts: list[str] = []
        for message in messages or []:
            text = str(getattr(message, "message", None) or getattr(message, "text", None) or "").strip()
            if text:
                texts.append(text)
        blob = "\n".join(texts)
        return {
            "spamblocked": parse_spambot_reply(blob),
            "source": "spambot",
            "raw": texts[0] if texts else "",
        }

    async def _get_dialogs_count(self, limit: int = 100) -> int:
        try:
            dialogs = await self.client.get_dialogs(limit=limit)
            return len(dialogs)
        except RPCError as exc:
            logger.warning("Could not fetch dialogs: %s", exc)
            return 0

    async def _get_bio(self, me: Any) -> str | None:
        try:
            full = await self.client(GetFullUserRequest(me))
            return getattr(full.full_user, "about", None)
        except RPCError as exc:
            logger.warning("Could not fetch bio: %s", exc)
            return None

    async def _has_avatar(self, me: Any) -> bool:
        try:
            photos = await self.client.get_profile_photos(me, limit=1)
            return len(photos) > 0
        except RPCError as exc:
            logger.warning("Could not check avatar: %s", exc)
            return False
