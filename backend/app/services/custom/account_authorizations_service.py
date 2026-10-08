"""List and terminate Telegram devices for a pool account the operator already runs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .telegram_account_client import TelegramAccountClient
from ...alembic.models import AccountPool, PoolAccount, SocialAccount

logger = logging.getLogger(__name__)


class AccountAuthorizationError(ValueError):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _unix_iso(value: Any) -> datetime | None:
    try:
        stamp = int(value or 0)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc).replace(tzinfo=None)


def serialize_authorization(auth: Any) -> dict[str, Any]:
    hash_value = int(getattr(auth, "hash", 0) or 0)
    current = bool(getattr(auth, "current", False)) or hash_value == 0
    device = str(getattr(auth, "device_model", None) or "").strip()
    platform = str(getattr(auth, "platform", None) or "").strip()
    app_name = str(getattr(auth, "app_name", None) or "").strip()
    app_version = str(getattr(auth, "app_version", None) or "").strip()
    country = str(getattr(auth, "country", None) or "").strip()
    region = str(getattr(auth, "region", None) or "").strip()
    ip = str(getattr(auth, "ip", None) or "").strip()
    place = ", ".join(part for part in (country, region) if part)
    title = device or app_name or platform or "Сессия"
    subtitle = " · ".join(part for part in (app_name, app_version, platform) if part and part != device)
    return {
        "hash": str(hash_value),
        "current": current,
        "device_model": device or None,
        "platform": platform or None,
        "app_name": app_name or None,
        "app_version": app_version or None,
        "ip": ip or None,
        "country": country or None,
        "region": region or None,
        "place": place or None,
        "title": title,
        "subtitle": subtitle or None,
        "created_at": _unix_iso(getattr(auth, "date_created", None)),
        "active_at": _unix_iso(getattr(auth, "date_active", None)),
        "can_terminate": not current,
    }


async def _load_pool_account(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> tuple[PoolAccount, SocialAccount] | None:
    row = (
        await session.execute(
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
            .where(
                AccountPool.custom_automation_id == automation_id,
                SocialAccount.id == account_id,
            )
        )
    ).one_or_none()
    return row


async def list_authorizations_via_client(client) -> list[Any]:
    from telethon.tl.functions.account import GetAuthorizationsRequest

    result = await client(GetAuthorizationsRequest())
    return list(getattr(result, "authorizations", None) or [])


async def count_authorizations(client) -> int:
    return len(await list_authorizations_via_client(client))


async def list_account_authorizations(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> dict[str, Any]:
    row = await _load_pool_account(session, automation_id, account_id)
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    if not social_account.session_file_path and not getattr(social_account, "encrypted_session", None):
        return {"status": "no_session", "pool_account": pool_account, "social_account": social_account}
    try:
        async with TelegramAccountClient.for_account(social_account) as client:
            raw = await list_authorizations_via_client(client)
    except Exception as exc:
        logger.warning("Could not list Telegram authorizations for %s: %s", account_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "pool_account": pool_account,
            "social_account": social_account,
        }
    items = [serialize_authorization(auth) for auth in raw]
    social_account.telegram_session_count = len(items)
    social_account.updated_at = _utc_now()
    await session.commit()
    return {
        "status": "ok",
        "items": items,
        "count": len(items),
        "pool_account": pool_account,
        "social_account": social_account,
    }


async def terminate_account_authorization(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    hash_value: int,
) -> dict[str, Any]:
    if int(hash_value) == 0:
        raise AccountAuthorizationError("Текущую сессию комбайна завершить нельзя")
    row = await _load_pool_account(session, automation_id, account_id)
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    if not social_account.session_file_path and not getattr(social_account, "encrypted_session", None):
        return {"status": "no_session", "pool_account": pool_account, "social_account": social_account}
    from telethon.tl.functions.account import ResetAuthorizationRequest

    try:
        async with TelegramAccountClient.for_account(social_account) as client:
            raw = await list_authorizations_via_client(client)
            match = next((auth for auth in raw if int(getattr(auth, "hash", 0) or 0) == int(hash_value)), None)
            if match is None:
                raise AccountAuthorizationError("Эта сессия уже не активна")
            if bool(getattr(match, "current", False)):
                raise AccountAuthorizationError("Текущую сессию комбайна завершить нельзя")
            await client(ResetAuthorizationRequest(hash=int(hash_value)))
            raw = await list_authorizations_via_client(client)
    except AccountAuthorizationError:
        raise
    except Exception as exc:
        logger.warning("Could not reset Telegram authorization %s for %s: %s", hash_value, account_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "pool_account": pool_account,
            "social_account": social_account,
        }
    items = [serialize_authorization(auth) for auth in raw]
    social_account.telegram_session_count = len(items)
    social_account.updated_at = _utc_now()
    await session.commit()
    return {
        "status": "ok",
        "items": items,
        "count": len(items),
        "pool_account": pool_account,
        "social_account": social_account,
    }
