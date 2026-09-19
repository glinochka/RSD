"""Telegram client wrapper for checking a single .session account."""
import asyncio
import io
import random
import re
import shutil
import sqlite3
import tempfile
from logging import getLogger
from pathlib import Path
from typing import Any, IO

from telethon.errors import AuthKeyError, RPCError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoneContact

from .telegram_error_handler import (
    SessionInvalidError,
    _looks_like_session_busy_error,
    _looks_like_session_error,
    parse_spambot_reply,
)
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ..telegram_userbot_auth import create_telegram_client, iter_api_credential_candidates

logger = getLogger(__name__)

_MAX_BIO_LENGTH = 160
_PHONE_DIGITS_RE = re.compile(r"\D+")
_SPAMBOT = "SpamBot"
_SPAMBOT_WAIT_SECONDS = 2.0
SESSION_RECONNECT_HINT = "Нет входа в Telegram. Подключите аккаунт заново по QR или SMS."
_session_locks: dict[str, asyncio.Lock] = {}
_session_locks_guard = asyncio.Lock()
_SESSION_SIDECARS = ("-journal", "-wal", "-shm")
_PRODUCTION_DCS = {
    1: ("149.154.175.53", 443),
    2: ("149.154.167.51", 443),
    3: ("149.154.175.100", 443),
    4: ("149.154.167.91", 443),
    5: ("91.108.56.130", 443),
}


async def _lock_for_session(session_path: str) -> asyncio.Lock:
    key = str(Path(session_path).resolve())
    async with _session_locks_guard:
        lock = _session_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _session_locks[key] = lock
        return lock


def _clear_session_sidecars(path: Path) -> None:
    for suffix in _SESSION_SIDECARS:
        extra = Path(str(path) + suffix)
        extra.unlink(missing_ok=True)


def inspect_session_file(path: Path) -> dict[str, Any]:
    """Detect Telethon vs Pyrogram sqlite without letting Telethon rewrite the file."""
    if not path.is_file() or path.stat().st_size < 16:
        return {"kind": "missing", "has_key": False, "api_id": None, "dc_id": None}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "sessions" not in tables:
                return {"kind": "unknown", "has_key": False, "api_id": None, "dc_id": None}
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            if "server_address" in cols:
                row = conn.execute("SELECT dc_id, auth_key FROM sessions").fetchone()
                return {
                    "kind": "telethon",
                    "has_key": bool(row and row[1]),
                    "api_id": None,
                    "dc_id": int(row[0]) if row and row[0] is not None else None,
                    "auth_key": bytes(row[1]) if row and row[1] else None,
                }
            if "api_id" in cols:
                row = conn.execute("SELECT dc_id, api_id, auth_key FROM sessions").fetchone()
                api_id = None
                if row and row[1] is not None:
                    try:
                        api_id = int(row[1])
                    except (TypeError, ValueError):
                        api_id = None
                return {
                    "kind": "pyrogram",
                    "has_key": bool(row and row[2]),
                    "api_id": api_id,
                    "dc_id": int(row[0]) if row and row[0] is not None else None,
                    "auth_key": bytes(row[2]) if row and row[2] else None,
                }
            row = conn.execute("SELECT auth_key FROM sessions").fetchone()
            return {
                "kind": "unknown",
                "has_key": bool(row and row[0]),
                "api_id": None,
                "dc_id": None,
                "auth_key": bytes(row[0]) if row and row[0] else None,
            }
        finally:
            conn.close()
    except Exception:
        return {"kind": "unknown", "has_key": False, "api_id": None, "dc_id": None}


def session_file_has_auth_key(path: Path) -> bool:
    """Read auth_key without opening a Telethon SQLiteSession (that can rewrite the file)."""
    return bool(inspect_session_file(path).get("has_key"))


def write_telethon_session_file(dest: Path, *, dc_id: int, auth_key: bytes) -> None:
    """Write a Telethon sqlite session from a raw auth key (Pyrogram conversion)."""
    from telethon.crypto import AuthKey
    from telethon.sessions import SQLiteSession

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    _clear_session_sidecars(dest)
    host, port = _PRODUCTION_DCS.get(int(dc_id), _PRODUCTION_DCS[2])
    stem = str(dest.with_suffix(""))
    session = SQLiteSession(stem)
    try:
        session.set_dc(int(dc_id), host, port)
        session.auth_key = AuthKey(auth_key)
        session.save()
    finally:
        session.close()
    _clear_session_sidecars(dest)


def convert_pyrogram_session_file(src: Path, dest: Path) -> dict[str, Any]:
    """Convert a Pyrogram sqlite session into Telethon format. Does not touch src if dest differs."""
    info = inspect_session_file(src)
    if info.get("kind") != "pyrogram" or not info.get("has_key") or not info.get("auth_key"):
        raise ValueError("Not a Pyrogram session with an auth key")
    write_telethon_session_file(
        dest,
        dc_id=int(info.get("dc_id") or 2),
        auth_key=info["auth_key"],
    )
    converted = inspect_session_file(dest)
    if converted.get("kind") != "telethon" or not converted.get("has_key"):
        raise ValueError("Pyrogram session conversion produced an empty Telethon file")
    converted["api_id"] = info.get("api_id")
    return converted


def ensure_telethon_session_file(path: Path) -> dict[str, Any]:
    """If `path` is Pyrogram sqlite, rewrite it in-place as Telethon sqlite."""
    info = inspect_session_file(path)
    if info.get("kind") == "pyrogram" and info.get("has_key"):
        convert_pyrogram_session_file(path, path)
        converted = inspect_session_file(path)
        converted["api_id"] = info.get("api_id")
        converted["converted_from"] = "pyrogram"
        return converted
    return info


def copy_session_bundle(src: Path, dest: Path) -> None:
    """Copy a Telethon sqlite session as a consistent snapshot.

    Never reuse Telethon's SQLiteSession here: opening the live file can
    create a WAL and overwrite a valid auth key with an empty one.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src_conn = sqlite3.connect(str(src), timeout=30)
        try:
            src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if dest.exists():
                dest.unlink()
            _clear_session_sidecars(dest)
            dst_conn = sqlite3.connect(str(dest))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()
        _clear_session_sidecars(dest)
    except Exception:
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
        _clear_session_sidecars(dest)
        return True
    except Exception as exc:
        logger.warning("Could not restore encrypted session to %s: %s", dest, exc)
        return False


def _acquire_session_file_lock(session_path: str) -> IO[bytes]:
    lock_path = Path(str(Path(session_path).resolve()) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except ImportError:
        pass
    return handle


def _release_session_file_lock(handle: IO[bytes] | None) -> None:
    if handle is None:
        return
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except ImportError:
        pass
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def _make_client(
    session_path: str,
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    proxy: dict | None = None,
    device_model: str | None = None,
):
    client, resolved_id, resolved_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_path=session_path,
        prefer_desktop=True,
        proxy=proxy,
        device_model=device_model,
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
        proxy: dict | None = None,
        device_model: str | None = None,
    ):
        self.session_path = session_path
        self._encrypted_session = encrypted_session
        self._api_id = api_id
        self._api_hash = api_hash
        self._proxy = proxy
        self._device_model = device_model
        self.client = None
        self.api_id = 0
        self.api_hash = ""
        self._session_lock: asyncio.Lock | None = None
        self._file_lock: IO[bytes] | None = None
        self._work_dir: Path | None = None
        self._work_path: Path | None = None
        self._detected_api_id: int | None = None
        self._converted_pyrogram = False

    @classmethod
    def for_account(
        cls,
        account,
        *,
        api_id: int | None = None,
        api_hash: str | None = None,
        proxy: dict | None = None,
    ) -> "TelegramAccountClient":
        from ...config import settings
        from .proxy_service import telethon_proxy_from_account

        rel = (getattr(account, "session_file_path", None) or "").strip()
        path = Path(settings.MEDIA_ROOT).resolve() / rel
        return cls(
            str(path),
            api_id=api_id,
            api_hash=api_hash,
            encrypted_session=getattr(account, "encrypted_session", None),
            proxy=proxy if proxy is not None else telethon_proxy_from_account(account),
        )

    async def _close_client(self) -> None:
        client = self.client
        self.client = None
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception:
            pass
        session = getattr(client, "session", None)
        closer = getattr(session, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass

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
        self._cleanup_work_dir()
        self._work_dir = Path(tempfile.mkdtemp(prefix="rsd_tg_"))
        self._work_path = self._work_dir / "account.session"
        copy_session_bundle(original, self._work_path)
        info = inspect_session_file(self._work_path)
        self._detected_api_id = info.get("api_id")
        self._converted_pyrogram = False
        if info.get("kind") == "pyrogram" and info.get("has_key"):
            convert_pyrogram_session_file(self._work_path, self._work_path)
            self._converted_pyrogram = True
            logger.info("Converted Pyrogram session to Telethon for %s", original)
        return self._work_path

    def _raise_connect_error(self, exc: Exception) -> None:
        if _looks_like_session_busy_error(exc):
            raise exc
        if isinstance(exc, AuthKeyError) or _looks_like_session_error(exc):
            raise SessionInvalidError(str(exc) or SESSION_RECONNECT_HINT) from exc
        raise exc

    async def _connect_work_copy(self) -> bool:
        await self._close_client()
        self.client, self.api_id, self.api_hash = _make_client(
            str(self._work_path),
            api_id=self._api_id,
            api_hash=self._api_hash,
            proxy=self._proxy,
            device_model=self._device_model,
        )
        try:
            await self.client.connect()
        except Exception as exc:
            await self._close_client()
            self._raise_connect_error(exc)
        try:
            authorized = await self.client.is_user_authorized()
        except Exception as exc:
            await self._close_client()
            self._raise_connect_error(exc)
        if authorized:
            return True
        await self._close_client()
        return False

    async def _connect_with_api_fallbacks(self) -> bool:
        last_exc: Exception | None = None
        original = Path(self.session_path)
        if original.is_file():
            self._detected_api_id = inspect_session_file(original).get("api_id")
        candidates = iter_api_credential_candidates(
            self._api_id,
            self._api_hash,
            extra_api_id=self._detected_api_id,
        )
        for api_id, api_hash in candidates or [(self._api_id, self._api_hash)]:
            self._prepare_work_copy()
            self._api_id = api_id
            self._api_hash = api_hash
            try:
                if await self._connect_work_copy():
                    return True
                last_exc = SessionInvalidError(SESSION_RECONNECT_HINT)
            except Exception as exc:
                if _looks_like_session_busy_error(exc):
                    raise
                last_exc = exc
                logger.info(
                    "Telegram login failed with api_id=%s for %s: %s",
                    api_id,
                    self.session_path,
                    exc,
                )
                continue
        if last_exc:
            if isinstance(last_exc, SessionInvalidError):
                raise last_exc
            self._raise_connect_error(last_exc)
        raise SessionInvalidError(SESSION_RECONNECT_HINT)

    def _release_locks(self) -> None:
        _release_session_file_lock(self._file_lock)
        self._file_lock = None
        if self._session_lock is not None:
            self._session_lock.release()
            self._session_lock = None

    async def __aenter__(self) -> "TelegramAccountClient":
        self._session_lock = await _lock_for_session(self.session_path)
        await self._session_lock.acquire()
        try:
            self._file_lock = await asyncio.to_thread(_acquire_session_file_lock, self.session_path)
            authorized = await self._connect_with_api_fallbacks()
            if not authorized and self._encrypted_session:
                original = Path(self.session_path)
                if restore_encrypted_session_file(self._encrypted_session, original):
                    logger.warning("Retrying Telegram login after restoring session %s", original)
                    authorized = await self._connect_with_api_fallbacks()
            if not authorized:
                raise SessionInvalidError(SESSION_RECONNECT_HINT)
            if self._converted_pyrogram and self._work_path:
                copy_session_bundle(self._work_path, Path(self.session_path))
            return self
        except Exception:
            await self._close_client()
            self._cleanup_work_dir()
            self._release_locks()
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self._close_client()
        finally:
            # Never copy the temp sqlite back. A failed/unauthorized connect can
            # write a new unregistered auth key into the work copy; copying that
            # onto the original is what looks like a "revoked" session.
            self._cleanup_work_dir()
            self._release_locks()

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

    async def probe_writable(self) -> None:
        """Touch a write RPC that frozen accounts reject. Login-only methods still work."""
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
        except ImportError:
            return
        await self.client(UpdateStatusRequest(offline=False))

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

    async def send_read_acknowledge(self, entity: Any, message: Any | None = None, **kwargs: Any) -> None:
        if message is not None:
            await self.client.send_read_acknowledge(entity, message, **kwargs)
        else:
            await self.client.send_read_acknowledge(entity, **kwargs)

    async def human_reply(
        self,
        recipient: str | int | Any,
        text: str,
        *,
        incoming_message: Any | None = None,
        max_id: int | None = None,
        lab_mode: bool = False,
    ) -> None:
        """Mark read, show typing, then send — human-like private reply."""
        from .human_dm import human_send_reply

        entity = recipient if not isinstance(recipient, (str, int)) else await self.resolve_peer(recipient)
        await human_send_reply(
            self,
            entity,
            text,
            incoming_message=incoming_message,
            max_id=max_id,
            lab_mode=lab_mode,
        )

    async def __call__(self, request: Any) -> Any:
        return await self.client(request)

    async def get_messages(self, *args: Any, **kwargs: Any) -> Any:
        return await self.client.get_messages(*args, **kwargs)

    async def get_dialogs(self, limit: int = 30) -> Any:
        return await self.client.get_dialogs(limit=limit)

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
