"""Mint a spare Telegram login and drop every extra session except that spare."""
from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import SocialAccount
from ...config import settings
from ..account_pool_service import encrypt_session_bytes
from ..telegram_userbot_auth import DEVICE_MODEL_SPARE, create_telegram_client
from .rotation_service import list_alive_session_accounts
from .telegram_account_client import (
    TelegramAccountClient,
    copy_session_bundle,
    restore_encrypted_session_file,
    session_file_has_auth_key,
)

logger = logging.getLogger(__name__)

_QR_ACCEPT_TIMEOUT = 45


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_date(value: datetime | None = None):
    try:
        tz = ZoneInfo("Europe/Moscow")
    except Exception:
        tz = timezone.utc
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(tz).date()


def already_pruned_today(account: SocialAccount, *, now: datetime | None = None) -> bool:
    stamped = getattr(account, "sessions_pruned_at", None)
    if stamped is None:
        return False
    return _moscow_date(stamped) == _moscow_date(now)


def authorization_should_keep(auth: Any, *, spare_hash: int | None) -> bool:
    """Current session (hash 0) and the RSD spare stay; everything else is extra."""
    hash_value = int(getattr(auth, "hash", 0) or 0)
    if hash_value == 0:
        return True
    if spare_hash is not None and hash_value == int(spare_hash):
        return True
    model = str(getattr(auth, "device_model", "") or "")
    return model == DEVICE_MODEL_SPARE


def extra_authorization_hashes(authorizations: Iterable[Any], *, spare_hash: int | None) -> list[int]:
    hashes: list[int] = []
    for auth in authorizations:
        if authorization_should_keep(auth, spare_hash=spare_hash):
            continue
        hashes.append(int(getattr(auth, "hash", 0) or 0))
    return hashes


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _spare_session_rel(account: SocialAccount, automation_id: int) -> str:
    rel = (account.session_file_path or "").strip()
    if rel:
        parent = str(Path(rel).parent).replace("\\", "/")
        return f"{parent}/{account.id}_spare.session"
    return f"sessions/{automation_id}/{account.id}_spare.session"


def account_has_spare(account: SocialAccount) -> bool:
    if (getattr(account, "encrypted_spare_session", None) or "").strip():
        return True
    rel = (getattr(account, "spare_session_file_path", None) or "").strip()
    if not rel:
        return False
    return session_file_has_auth_key(_media_root() / rel)


def promote_spare_session(account: SocialAccount) -> bool:
    """Replace a revoked main session with the independently issued spare login."""
    blob = (getattr(account, "encrypted_spare_session", None) or "").strip()
    spare_rel = (getattr(account, "spare_session_file_path", None) or "").strip()
    if not blob and not spare_rel:
        return False
    dest_rel = (account.session_file_path or "").strip()
    if not dest_rel:
        dest_rel = spare_rel.replace("_spare.session", ".session") if spare_rel else f"sessions/{account.id}.session"
        account.session_file_path = dest_rel
    dest = _media_root() / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    wrote = False
    if spare_rel:
        src = _media_root() / spare_rel
        if src.is_file() and session_file_has_auth_key(src):
            copy_session_bundle(src, dest)
            wrote = True
    if not wrote and blob:
        wrote = restore_encrypted_session_file(blob, dest)
    if not wrote:
        return False
    if blob:
        account.encrypted_session = blob
    elif dest.is_file():
        account.encrypted_session = encrypt_session_bytes(dest.read_bytes())
    account.encrypted_spare_session = None
    account.spare_session_file_path = None
    account.spare_authorization_hash = None
    account.is_active = True
    account.updated_at = _utc_now()
    logger.warning("Promoted spare Telegram session for account %s", account.id)
    return True


def _persist_spare_bytes(account: SocialAccount, automation_id: int, src: Path) -> None:
    rel = _spare_session_rel(account, automation_id)
    dest = _media_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    copy_session_bundle(src, dest)
    account.encrypted_spare_session = encrypt_session_bytes(dest.read_bytes())
    account.spare_session_file_path = rel
    account.updated_at = _utc_now()


async def _list_authorizations(client) -> list[Any]:
    from telethon.tl.functions.account import GetAuthorizationsRequest

    result = await client(GetAuthorizationsRequest())
    return list(getattr(result, "authorizations", None) or [])


def _spare_hash_from_authorizations(authorizations: Iterable[Any], known: int | None = None) -> int | None:
    if known is not None:
        for auth in authorizations:
            if int(getattr(auth, "hash", 0) or 0) == int(known):
                return int(known)
    for auth in authorizations:
        if int(getattr(auth, "hash", 0) or 0) == 0:
            continue
        if str(getattr(auth, "device_model", "") or "") == DEVICE_MODEL_SPARE:
            return int(getattr(auth, "hash", 0) or 0)
    return None


async def _reset_extra_sessions(client, *, spare_hash: int | None) -> int:
    from telethon.tl.functions.account import ResetAuthorizationRequest

    authorizations = await _list_authorizations(client)
    reset = 0
    for hash_value in extra_authorization_hashes(authorizations, spare_hash=spare_hash):
        if not hash_value:
            continue
        try:
            await client(ResetAuthorizationRequest(hash=hash_value))
            reset += 1
        except Exception as exc:
            logger.warning("Could not reset Telegram authorization %s: %s", hash_value, exc)
    return reset


async def _close_client(client) -> None:
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


async def _mint_spare_session(main_client, account: SocialAccount, automation_id: int) -> int | None:
    """Issue a second independent auth key by accepting QR login from the main client."""
    from telethon.tl.functions.auth import AcceptLoginTokenRequest

    work = Path(tempfile.mkdtemp(prefix="rsd_spare_"))
    spare_path = work / "spare.session"
    spare_client, _, _ = create_telegram_client(
        session_path=str(spare_path),
        device_model=DEVICE_MODEL_SPARE,
        proxy=getattr(main_client, "_proxy", None),
        api_id=getattr(main_client, "api_id", None) or None,
        api_hash=getattr(main_client, "api_hash", None) or None,
    )
    try:
        await spare_client.connect()
        qr_login = await spare_client.qr_login()
        token = getattr(qr_login, "token", None)
        if not token:
            raise RuntimeError("Telegram QR login returned an empty token")
        await main_client.client(AcceptLoginTokenRequest(token=token))
        await qr_login.wait(timeout=_QR_ACCEPT_TIMEOUT)
        await _close_client(spare_client)
        spare_client = None
        if not session_file_has_auth_key(spare_path):
            raise RuntimeError("Spare session file has no auth key")
        _persist_spare_bytes(account, automation_id, spare_path)
        authorizations = await _list_authorizations(main_client.client)
        spare_hash = _spare_hash_from_authorizations(authorizations)
        account.spare_authorization_hash = spare_hash
        return spare_hash
    finally:
        if spare_client is not None:
            await _close_client(spare_client)
        try:
            import shutil

            shutil.rmtree(work, ignore_errors=True)
        except Exception:
            pass


async def hygienize_account(
    session: AsyncSession,
    account: SocialAccount,
    automation_id: int,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Ensure a spare login exists and drop every other Telegram session."""
    if not force and already_pruned_today(account):
        return {"status": "skipped", "reason": "already_today"}
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        return {"status": "skipped", "reason": "no_session"}
    minted = False
    pruned = 0
    async with TelegramAccountClient.for_account(account) as client:
        spare_hash = getattr(account, "spare_authorization_hash", None)
        if not account_has_spare(account):
            try:
                spare_hash = await _mint_spare_session(client, account, automation_id)
                minted = spare_hash is not None or account_has_spare(account)
            except Exception as exc:
                logger.warning("Could not mint spare session for account %s: %s", account.id, exc)
        else:
            authorizations = await _list_authorizations(client.client)
            live_hash = _spare_hash_from_authorizations(authorizations, known=spare_hash)
            if live_hash is None:
                try:
                    spare_hash = await _mint_spare_session(client, account, automation_id)
                    minted = True
                except Exception as exc:
                    logger.warning("Could not re-mint spare session for account %s: %s", account.id, exc)
            else:
                spare_hash = live_hash
                account.spare_authorization_hash = live_hash
        pruned = await _reset_extra_sessions(client.client, spare_hash=spare_hash)
    account.sessions_pruned_at = _utc_now()
    account.updated_at = _utc_now()
    await session.flush()
    return {"status": "ok", "minted": minted, "pruned": pruned}


async def run_session_hygiene_for_automation(automation_id: int) -> dict[str, Any]:
    processed = 0
    minted = 0
    pruned = 0
    skipped = 0
    errors = 0
    async with async_session_maker() as session:
        accounts = await list_alive_session_accounts(session, automation_id)
        for account in accounts:
            if already_pruned_today(account):
                skipped += 1
                continue
            try:
                result = await hygienize_account(session, account, automation_id)
            except Exception as exc:
                errors += 1
                logger.warning("Session hygiene failed for account %s: %s", account.id, exc)
                continue
            processed += 1
            if result.get("status") == "skipped":
                skipped += 1
                continue
            minted += int(bool(result.get("minted")))
            pruned += int(result.get("pruned") or 0)
        await session.commit()
    return {
        "status": "ok",
        "accounts": processed,
        "minted": minted,
        "pruned": pruned,
        "skipped": skipped,
        "errors": errors,
    }
