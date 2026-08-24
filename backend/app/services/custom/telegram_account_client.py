"""Telegram client wrapper for checking a single .session account."""
import io
from logging import getLogger
from typing import Any

from telethon import TelegramClient
from telethon.errors import AuthKeyError, RPCError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest

from ..telegram_userbot_auth import resolve_api_credentials

logger = getLogger(__name__)

_MAX_BIO_LENGTH = 160


class TelegramAccountClient:
    """Connect to a saved Telethon .session and read public profile info.

    Uses the same API credential fallback chain as the rest of the platform
    (custom env -> global env -> opentele -> Telethon built-in).
    """

    def __init__(self, session_path: str, *, api_id: int | None = None, api_hash: str | None = None):
        self.session_path = session_path
        self.api_id, self.api_hash = resolve_api_credentials(api_id, api_hash, prefer_desktop=True)
        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash)

    async def __aenter__(self) -> "TelegramAccountClient":
        await self.client.connect()
        if not await self.client.is_user_authorized():
            await self.client.disconnect()
            raise RuntimeError("Session is not authorized")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.client.disconnect()
        except Exception as exc_close:
            logger.debug("Error disconnecting Telegram client: %s", exc_close)

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

    async def set_avatar(self, avatar: str | bytes) -> None:
        """Upload a new profile photo from a file path or bytes."""
        if isinstance(avatar, str):
            uploaded = await self.client.upload_file(avatar)
        else:
            uploaded = await self.client.upload_file(io.BytesIO(avatar))
        await self.client(UploadProfilePhotoRequest(file=uploaded))

    async def send_message(self, recipient: str | int, text: str) -> None:
        """Send a private message to a user by username, id or peer."""
        await self.client.send_message(recipient, text)

    async def __call__(self, request: Any) -> Any:
        return await self.client(request)

    async def get_messages(self, *args: Any, **kwargs: Any) -> Any:
        return await self.client.get_messages(*args, **kwargs)

    async def get_entity(self, identifier: Any) -> Any:
        return await self.resolve_peer(identifier)

    async def resolve_peer(self, identifier: Any) -> Any:
        """Resolve a Telegram entity from username, t.me link, numeric id or peer."""
        if identifier is None:
            raise ValueError("empty peer identifier")
        if not isinstance(identifier, str):
            return await self.client.get_entity(identifier)
        text = identifier.strip()
        if not text:
            raise ValueError("empty peer identifier")
        if "t.me/" in text.lower():
            path = text.split("t.me/", 1)[-1].strip("/")
            if path.startswith("+") or path.lower().startswith("joinchat/"):
                return await self.client.get_entity(text)
            username = path.split("/")[0].split("?")[0]
            return await self.client.get_entity(username)
        if text.lstrip("-").isdigit():
            return await self.client.get_entity(int(text))
        return await self.client.get_entity(text)

    @staticmethod
    def _display_name(me: Any) -> str:
        first = (me.first_name or "").strip()
        last = (me.last_name or "").strip()
        name = f"{first} {last}".strip()
        return name or (me.username or "").strip() or f"user_{me.id}"

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
