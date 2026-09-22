"""Mint a spare Telegram login and drop every extra session except that spare."""
from __future__ import annotations

import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import SocialAccount
from ...config import settings
from ..account_pool_service import encrypt_session_bytes
from ..telegram_userbot_auth import DEVICE_MODEL_MAIN, DEVICE_MODEL_SPARE, create_telegram_client, ensure_account_device
from .rotation_service import list_alive_session_accounts
from .telegram_account_client import (
    TelegramAccountClient,
    copy_session_bundle,
    restore_encrypted_session_file,
    session_file_has_auth_key,
)

logger = logging.getLogger(__name__)

_QR_ACCEPT_TIMEOUT = 45
_HYGIENE_MIN_AGE_SECONDS = 3600
# Minting a spare opens a second Telegram login. Doing that on a brand-new
# session (right after SMS/QR/upload) races with health/profile workers and
# frequently kills the main auth key — especially with 2FA accounts.
_HYGIENE_MINT_MIN_AGE_SECONDS = 6 * 3600
# Spare QR login was killing live keys (2FA / seller sessions). Keep prune of
# already-minted spares, but do not authorize a second device until this is on.
_SPARE_MINT_ENABLED = False
# ResetAuthorization of seller/phone sessions is a farm tell and can kill the
# key we are on. Leave extra devices alone until mint is proven safe.
_SESSION_PRUNE_ENABLED = False
_LEGACY_DEVICE_MODELS = frozenset({DEVICE_MODEL_MAIN, DEVICE_MODEL_SPARE})


def _device_models_for_account(account: SocialAccount | None) -> set[str]:
    models = set(_LEGACY_DEVICE_MODELS)
    if account is None:
        return models
    for field in ("telegram_device", "spare_telegram_device"):
        payload = getattr(account, field, None)
        if isinstance(payload, dict):
            model = str(payload.get("device_model") or "").strip()
            if model:
                models.add(model)
    return models


def authorization_should_keep(
    auth: Any,
    *,
    spare_hash: int | None,
    known_models: Iterable[str] | None = None,
) -> bool:
    """Keep the login we are on, the spare, and our own device fingerprints.

    Telegram hash 0 is always the currently connected session — it cannot be
    reset. Extra hashes are seller/third-party devices.
    """
    hash_value = int(getattr(auth, "hash", 0) or 0)
    if hash_value == 0:
        return True
    if spare_hash is not None and hash_value == int(spare_hash):
        return True
    model = str(getattr(auth, "device_model", "") or "").strip()
    allowed = set(_LEGACY_DEVICE_MODELS)
    if known_models:
        allowed.update(str(item).strip() for item in known_models if str(item or "").strip())
    return model in allowed


def extra_authorization_hashes(
    authorizations: Iterable[Any],
    *,
    spare_hash: int | None,
    known_models: Iterable[str] | None = None,
) -> list[int]:
    hashes: list[int] = []
    for auth in authorizations:
        if authorization_should_keep(auth, spare_hash=spare_hash, known_models=known_models):
            continue
        hashes.append(int(getattr(auth, "hash", 0) or 0))
    return hashes


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


def _session_file_age_seconds(account: SocialAccount) -> float | None:
    rel = (account.session_file_path or "").strip()
    if not rel:
        return None
    path = _media_root() / rel
    try:
        if not path.is_file():
            return None
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


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


def _spare_hash_from_authorizations(
    authorizations: Iterable[Any],
    known: int | None = None,
    *,
    spare_model: str | None = None,
) -> int | None:
    if known is not None:
        for auth in authorizations:
            if int(getattr(auth, "hash", 0) or 0) == int(known):
                return int(known)
    wanted = {DEVICE_MODEL_SPARE}
    if spare_model:
        wanted.add(str(spare_model).strip())
    for auth in authorizations:
        if int(getattr(auth, "hash", 0) or 0) == 0:
            continue
        if str(getattr(auth, "device_model", "") or "") in wanted:
            return int(getattr(auth, "hash", 0) or 0)
    return None


async def _reset_extra_sessions(
    client,
    *,
    spare_hash: int | None,
    known_models: Iterable[str] | None = None,
) -> int:
    from telethon.tl.functions.account import ResetAuthorizationRequest

    authorizations = await _list_authorizations(client)
    reset = 0
    for hash_value in extra_authorization_hashes(
        authorizations,
        spare_hash=spare_hash,
        known_models=known_models,
    ):
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


async def _account_requires_2fa(client) -> bool:
    """Spare QR mint cannot finish without the cloud password — do not even try."""
    try:
        from telethon.tl.functions.account import GetPasswordRequest

        password = await client(GetPasswordRequest())
        return bool(getattr(password, "has_password", False))
    except Exception as exc:
        logger.info("Could not check 2FA before spare mint: %s", exc)
        return False


async def _mint_spare_session(main_client, account: SocialAccount, automation_id: int) -> int | None:
    """Issue a second independent auth key by accepting QR login from the main client."""
    from telethon.tl.functions.auth import AcceptLoginTokenRequest

    try:
        from telethon.errors import SessionPasswordNeededError
    except Exception:  # pragma: no cover
        SessionPasswordNeededError = type("SessionPasswordNeededError", (Exception,), {})

    if await _account_requires_2fa(main_client.client):
        raise RuntimeError(
            "2FA cloud password is enabled; spare session mint is skipped "
            "(QR spare login cannot complete without the password)"
        )

    work = Path(tempfile.mkdtemp(prefix="rsd_spare_"))
    spare_path = work / "spare.session"
    profile = ensure_account_device(account, spare=True)
    spare_client, _, _ = create_telegram_client(
        session_path=str(spare_path),
        device_profile=profile,
        proxy=getattr(main_client, "_proxy", None),
        api_id=getattr(main_client, "api_id", None) or None,
        api_hash=getattr(main_client, "api_hash", None) or None,
    )
    accepted = False
    try:
        await spare_client.connect()
        qr_login = await spare_client.qr_login()
        token = getattr(qr_login, "token", None)
        if not token:
            raise RuntimeError("Telegram QR login returned an empty token")
        await main_client.client(AcceptLoginTokenRequest(token=token))
        accepted = True
        try:
            await qr_login.wait(timeout=_QR_ACCEPT_TIMEOUT)
        except SessionPasswordNeededError as exc:
            raise RuntimeError(
                "Spare mint hit 2FA password after AcceptLoginToken; "
                "aborting so we do not leave a half-open device"
            ) from exc
        await _close_client(spare_client)
        spare_client = None
        if not session_file_has_auth_key(spare_path):
            raise RuntimeError("Spare session file has no auth key")
        _persist_spare_bytes(account, automation_id, spare_path)
        authorizations = await _list_authorizations(main_client.client)
        spare_hash = _spare_hash_from_authorizations(
            authorizations,
            spare_model=(profile or {}).get("device_model"),
        )
        account.spare_authorization_hash = spare_hash
        return spare_hash
    except Exception:
        if accepted:
            # Best-effort: drop any incomplete device created by AcceptLoginToken.
            try:
                authorizations = await _list_authorizations(main_client.client)
                known = _device_models_for_account(account)
                for auth in authorizations:
                    hash_value = int(getattr(auth, "hash", 0) or 0)
                    if not hash_value:
                        continue
                    model = str(getattr(auth, "device_model", "") or "").strip()
                    if model and model == str((profile or {}).get("device_model") or ""):
                        from telethon.tl.functions.account import ResetAuthorizationRequest

                        await main_client.client(ResetAuthorizationRequest(hash=hash_value))
                        logger.warning(
                            "Reset incomplete spare authorization %s for account %s",
                            hash_value,
                            account.id,
                        )
            except Exception as cleanup_exc:
                logger.warning(
                    "Could not clean incomplete spare for account %s: %s",
                    account.id,
                    cleanup_exc,
                )
        raise
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
    """Mint a spare login if missing, then drop third-party Telegram sessions.

    Mint never runs on a fresh session file — concurrent health/profile traffic
    plus a second QR login is what was revoking accounts right after SMS/upload.
    `force` may prune when a live spare exists; it does not bypass mint freshness.
    Spare mint is currently disabled (`_SPARE_MINT_ENABLED`) so we do not open
    a second Telegram login at all. Session prune (`ResetAuthorization`) is also
    off (`_SESSION_PRUNE_ENABLED`) so we do not kick other devices.
    """
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        return {"status": "skipped", "reason": "no_session"}
    if not _SPARE_MINT_ENABLED and not _SESSION_PRUNE_ENABLED:
        return {"status": "skipped", "minted": False, "pruned": 0, "reason": "hygiene_disabled"}
    if not _SPARE_MINT_ENABLED and not account_has_spare(account):
        return {"status": "skipped", "minted": False, "pruned": 0, "reason": "mint_disabled"}
    minted = False
    pruned = 0
    skip_prune = (not force) and already_pruned_today(account)
    age = _session_file_age_seconds(account)
    too_fresh_mint = age is not None and age < _HYGIENE_MINT_MIN_AGE_SECONDS
    too_fresh_prune = (not force) and age is not None and age < _HYGIENE_MIN_AGE_SECONDS
    mint_skip_reason: str | None = None
    async with TelegramAccountClient.for_account(account) as client:
        spare_hash = getattr(account, "spare_authorization_hash", None)
        if not account_has_spare(account):
            if not _SPARE_MINT_ENABLED:
                mint_skip_reason = "mint_disabled"
            elif too_fresh_mint:
                mint_skip_reason = "too_fresh"
                logger.info(
                    "Deferring spare mint for account %s (session age %.0fs < %ss)",
                    account.id,
                    age or 0,
                    _HYGIENE_MINT_MIN_AGE_SECONDS,
                )
            else:
                try:
                    spare_hash = await _mint_spare_session(client, account, automation_id)
                    minted = spare_hash is not None or account_has_spare(account)
                except Exception as exc:
                    mint_skip_reason = "mint_failed"
                    logger.warning("Could not mint spare session for account %s: %s", account.id, exc)
        else:
            authorizations = await _list_authorizations(client.client)
            live_hash = _spare_hash_from_authorizations(
                authorizations,
                known=spare_hash,
                spare_model=(getattr(account, "spare_telegram_device", None) or {}).get("device_model")
                if isinstance(getattr(account, "spare_telegram_device", None), dict)
                else None,
            )
            if live_hash is None:
                if not _SPARE_MINT_ENABLED:
                    mint_skip_reason = "mint_disabled"
                    logger.info("Spare remint disabled; leaving account %s on the main session", account.id)
                elif too_fresh_mint:
                    mint_skip_reason = "too_fresh"
                else:
                    try:
                        spare_hash = await _mint_spare_session(client, account, automation_id)
                        minted = True
                    except Exception as exc:
                        mint_skip_reason = "mint_failed"
                        logger.warning("Could not re-mint spare session for account %s: %s", account.id, exc)
            else:
                spare_hash = live_hash
                account.spare_authorization_hash = live_hash
        authorizations = await _list_authorizations(client.client)
        live_spare = _spare_hash_from_authorizations(authorizations, known=spare_hash)
        can_prune = (
            _SESSION_PRUNE_ENABLED
            and account_has_spare(account)
            and live_spare is not None
            and not skip_prune
            and not too_fresh_prune
        )
        if can_prune:
            pruned = await _reset_extra_sessions(
                client.client,
                spare_hash=live_spare,
                known_models=_device_models_for_account(account),
            )
        elif minted and (too_fresh_prune or skip_prune or live_spare is None):
            logger.info(
                "Spare session ready for account %s; third-party prune deferred (fresh=%s today=%s live=%s)",
                account.id,
                too_fresh_prune,
                skip_prune,
                live_spare,
            )
    if minted or pruned:
        if pruned:
            account.sessions_pruned_at = _utc_now()
        account.updated_at = _utc_now()
    await session.flush()
    reason = None
    if not minted and not pruned:
        if mint_skip_reason:
            reason = mint_skip_reason
        elif skip_prune and account_has_spare(account):
            reason = "already_today"
        elif too_fresh_prune:
            reason = "too_fresh"
        elif not account_has_spare(account):
            reason = "no_spare"
    status = "ok" if (minted or pruned) else "skipped"
    return {"status": status, "minted": minted, "pruned": pruned, "reason": reason}


async def run_session_hygiene_for_automation(automation_id: int) -> dict[str, Any]:
    processed = 0
    minted = 0
    pruned = 0
    skipped = 0
    errors = 0
    async with async_session_maker() as session:
        accounts = await list_alive_session_accounts(session, automation_id)
        for account in accounts:
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
