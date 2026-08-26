"""Telegram client wrapper for checking a single .session account."""
import asyncio
import io
import random
import re
import shutil
import tempfile
from logging import getLogger
from pathlib import Path
from typing import Any

from telethon.errors import AuthKeyError, RPCError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoneContact

from .telegram_error_handler import SessionInvalidError, parse_spambot_reply
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ..telegram_userbot_auth import create_telegram_client

logger = getLogger(__name__)

_MAX_BIO_LENGTH = 160
_PHONE_DIGITS_RE = re.compile(r"\D+")
_SPAMBOT = "SpamBot"
_SPAMBOT_WAIT_SECONDS = 2.0
SESSION_RECONNECT_HINT = "Нет входа в Telegram. Подключите аккаунт заново по QR или SMS."
_session_locks: dict[str, asyncio.Lock] = {}
_session_locks_guard = asyncio.Lock()
_SESSION_SIDECARS = ("-journal", "-wal", "-shm")


async def _lock_for_session(session_path: str) -> asyncio.Lock:
    key = str(Path(session_path).resolve())
    async with _session_locks_guard:
        lock = _session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[key] = lock
        return lock


def _session_stem(path: Path) -> str:
    text = str(path)
    return text[:-8] if text.endswith(".session") else text


def session_file_has_auth_key(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 16:
        return False
    try:
        from telethon.sessions import SQLiteSession

        sess = SQLiteSession(_session_stem(path))
        try:
            key = sess.auth_key
            raw = getattr(key, "key", None) if key is not None else None
            return bool(raw)
        finally:
            sess.close()
    except Exception:
        return False


def copy_session_bundle(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    for suffix in _SESSION_SIDECARS:
        extra = Path(str(src) + suffix)
        if extra.is_file():
            shutil.copy2(extra, Path(str(dest) + suffix))


def restore_encrypted_session_file(encrypted_session: str | None, dest: Path) -> bool:
    payload = (encrypted_session or "").strip()
    if not payload.startswith("fernet1:"):
        return False
    try:
        from ..account_pool_service import decrypt_session_bytes, _is_valid_telegram_session

        data = decrypt_session_bytes(payload)
        if not _is_valid_telegram_session(data):
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as exc:
        logger.warning("Could not restore encrypted session to %s: %s", dest, exc)
        return False


def _make_client(session_path: str, *, api_id: int | None = None, api_hash: str | None = None):
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_path=session_path,
        prefer_desktop=True,
    )
    return client, resolved_id, resolved_hash


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

    Always opens a temp copy of the sqlite file so a failed auth cannot wipe
    the original. If `encrypted_session` is set, a wiped file is restored once.
    Uses the same API credential chain as QR/SMS login.
    """

    def __init__(
        self,
        session_path: str,
        *,
        api_id: int | None = None,
        api_hash: str | None = None,
        encrypted_session: str | None = None,
    ):
        self.session_path = session_path
        self._encrypted_session = encrypted_session
        self._api_id = api_id
        self._api_hash = api_hash
        self.client = None
        self.api_id = 0
        self.api_hash = ""
        self._session_lock: asyncio.Lock | None = None
        self._work_dir: Path | None = None
        self._work_path: Path | None = None
        self._entered_ok = False

    @classmethod
    def for_account(cls, account, *, api_id: int | None = None, api_hash: str | None = None) -> "TelegramAccountClient":
        from ...config import settings

        rel = (getattr(account, "session_file_path", None) or "").strip()
        path = Path(settings.MEDIA_ROOT).resolve() / rel
        return cls(
            str(path),
            api_id=api_id,
            api_hash=api_hash,
            encrypted_session=getattr(account, "encrypted_session", None),
        )

    def _cleanup_work_dir(self) -> None:
        if self._work_dir and self._work_dir.exists():
            shutil.rmtree(self._work_dir, ignore_errors=True)
        self._work_dir = None
        self._work_path = None

    def _prepare_work_copy(self) -> Path:
        original = Path(self.session_path)
        if self._encrypted_session and not session_file_has_auth_key(original):
            if restore_encrypted_session_file(self._encrypted_session, original):
                logger.warning("Restored session file from encrypted backup: %s", original)
        if not original.is_file():
            raise SessionInvalidError("Session file missing")
        self._work_dir = Path(tempfile.mkdtemp(prefix="rsd_tg_"))
        self._work_path = self._work_dir / "account.session"
        copy_session_bundle(original, self._work_path)
        return self._work_path

    async def _connect_work_copy(self) -> bool:
        from .telegram_error_handler import _looks_like_session_error

        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
        self.client, self.api_id, self.api_hash = _make_client(
            str(self._work_path),
            api_id=self._api_id,
            api_hash=self._api_hash,
        )
        try:
            await self.client.connect()
        except Exception as exc:
            if isinstance(exc, AuthKeyError) or _looks_like_session_error(exc):
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                raise SessionInvalidError(str(exc) or SESSION_RECONNECT_HINT) from exc
            raise
        try:
            authorized = await self.client.is_user_authorized()
        except Exception as exc:
            if isinstance(exc, AuthKeyError) or _looks_like_session_error(exc):
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                raise SessionInvalidError(str(exc) or SESSION_RECONNECT_HINT) from exc
            raise
        if authorized:
            return True
        try:
            await self.client.disconnect()
        except Exception:
            pass
        return False

    async def __aenter__(self) -> "TelegramAccountClient":
        self._session_lock = await _lock_for_session(self.session_path)
        await self._session_lock.acquire()
        try:
            self._prepare_work_copy()
            authorized = await self._connect_work_copy()
            if not authorized and self._encrypted_session:
                original = Path(self.session_path)
                if restore_encrypted_session_file(self._encrypted_session, original):
                    logger.warning("Retrying Telegram login after restoring session %s", original)
                    copy_session_bundle(original, self._work_path)
                    authorized = await self._connect_work_copy()
            if not authorized:
                raise SessionInvalidError(SESSION_RECONNECT_HINT)
            self._entered_ok = True
            return self
        except Exception:
            self._cleanup_work_dir()
            if self._session_lock is not None:
                self._session_lock.release()
                self._session_lock = None
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        authorized = False
        if self.client is not None:
            try:
                if self._entered_ok:
                    authorized = bool(await self.client.is_user_authorized())
            except Exception:
                authorized = False
            try:
                await self.client.disconnect()
            except Exception as exc_close:
                logger.debug("Error disconnecting Telegram client: %s", exc_close)
        if authorized and self._work_path and self._work_path.is_file():
            try:
                copy_session_bundle(self._work_path, Path(self.session_path))
            except Exception as exc_copy:
                logger.warning("Could not copy session back to %s: %s", self.session_path, exc_copy)
        self._cleanup_work_dir()
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
        try:
            parsed = parse_telegram_chat_ref(text)
        except TelegramChatRefError:
            parsed = None
        if parsed is not None:
            if parsed.kind == "invite":
                from telethon.tl.functions.messages import CheckChatInviteRequest

                result = await self.client(CheckChatInviteRequest(parsed.value))
                chat = getattr(result, "chat", None)
                if chat is not None:
                    return chat
            else:
                return await self.client.get_entity(parsed.lookup_value)
        phone = normalize_telegram_phone(text)
        if phone and (text.startswith("+") or text.replace(" ", "").replace("-", "").isdigit()):
            return await self.resolve_phone(phone)
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
