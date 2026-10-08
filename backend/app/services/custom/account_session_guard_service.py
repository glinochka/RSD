"""Kill unexpected Telegram logins on regular pool accounts.

Known hashes are snapshotted on first connect. Later newcomers are reset,
except during operator grace after "Код из Telegram" / a manual pause.
"Перевести в общий пул" adopts the current device list as the new baseline.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_authorizations_service import list_authorizations_via_client, serialize_authorization
from .telegram_account_client import TelegramAccountClient
from ...alembic.models import AccountPool, CustomAutomation, PoolAccount, SocialAccount

logger = logging.getLogger(__name__)

LOGIN_CODE_GRACE_SECONDS = 5 * 60
OPERATOR_PAUSE_SECONDS = 15 * 60
GUARD_INTERVAL_SECONDS = 4 * 60

_LOGIN_ALERT_RE = re.compile(
    r"(new login|detected a login|новый вход|вход в аккаунт|login from a new|new device)",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


def guard_is_paused(account: Any, *, now: datetime | None = None) -> bool:
    until = _naive(getattr(account, "session_guard_paused_until", None))
    if until is None:
        return False
    return until > (_naive(now) or _utc_now())


def pause_session_guard(account: SocialAccount, *, seconds: int = LOGIN_CODE_GRACE_SECONDS) -> datetime:
    until = _utc_now() + timedelta(seconds=max(30, int(seconds)))
    current = _naive(getattr(account, "session_guard_paused_until", None))
    if current and current > until:
        return current
    account.session_guard_paused_until = until
    account.updated_at = _utc_now()
    return until


def looks_like_login_alert(text: str | None) -> bool:
    return bool(_LOGIN_ALERT_RE.search(str(text or "")))


def plan_session_guard(
    known: set[str],
    live: list[dict[str, Any]],
    *,
    paused: bool,
    takeover: bool = False,
) -> dict[str, Any]:
    hashes = {str(item.get("hash") or "") for item in live if item.get("hash") is not None}
    hashes.discard("")
    currents = {
        str(item.get("hash") or "")
        for item in live
        if item.get("current") or str(item.get("hash") or "") == "0"
    }
    if paused:
        return {"action": "pause_adopt", "keep": (known or set()) | hashes, "terminate": []}
    if takeover:
        terminate = [item for item in sorted(hashes) if item not in currents]
        keep = hashes - set(terminate)
        return {
            "action": "takeover" if terminate else "hold",
            "keep": keep,
            "terminate": terminate,
        }
    if not known:
        return {"action": "snapshot", "keep": hashes, "terminate": []}
    newcomers = hashes - known
    terminate = [item for item in sorted(newcomers) if item not in currents]
    keep = hashes - set(terminate)
    return {"action": "enforce", "keep": keep, "terminate": terminate}


def _hash_set(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    return set()


def _needs_scan(account: SocialAccount, *, force: bool = False, now: datetime | None = None) -> bool:
    if getattr(account, "session_guard_enabled", True) is False:
        return False
    if force:
        return True
    checked = _naive(getattr(account, "session_guard_checked_at", None))
    if checked is None:
        return True
    return (_naive(now) or _utc_now()) - checked >= timedelta(seconds=GUARD_INTERVAL_SECONDS)


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


async def enforce_authorizations(client: Any, account: SocialAccount, *, force: bool = False) -> dict[str, Any]:
    if getattr(account, "session_guard_enabled", True) is False:
        return {"status": "disabled", "terminated": []}
    from .account_pacing import account_is_intercept, account_may_keep_alive

    if not force and not account_may_keep_alive(account):
        return {"status": "skipped", "terminated": []}
    if not _needs_scan(account, force=force) and not guard_is_paused(account):
        return {"status": "skipped", "terminated": []}
    from telethon.tl.functions.account import ResetAuthorizationRequest

    raw = await list_authorizations_via_client(client)
    live = [serialize_authorization(item) for item in raw]
    plan = plan_session_guard(
        _hash_set(getattr(account, "known_auth_hashes", None)),
        live,
        paused=guard_is_paused(account),
        takeover=account_is_intercept(account),
    )
    terminated: list[str] = []
    for hash_value in plan["terminate"]:
        try:
            await client(ResetAuthorizationRequest(hash=int(hash_value)))
            terminated.append(hash_value)
        except Exception as exc:
            logger.warning("Session guard could not reset %s on %s: %s", hash_value, account.id, exc)
    if terminated:
        raw = await list_authorizations_via_client(client)
        live = [serialize_authorization(item) for item in raw]
        keep = {str(item.get("hash") or "") for item in live if item.get("hash") is not None}
        keep.discard("")
    else:
        keep = set(plan["keep"])
    account.known_auth_hashes = sorted(keep)
    account.telegram_session_count = len(live)
    account.session_guard_checked_at = _utc_now()
    account.updated_at = _utc_now()
    status = "terminated" if terminated else plan["action"]
    if terminated:
        logger.info("Session guard dropped %s new login(s) on account %s", len(terminated), account.id)
    return {
        "status": status,
        "terminated": terminated,
        "count": len(live),
        "items": live,
        "paused": guard_is_paused(account),
    }


async def guard_live_client(
    session: AsyncSession,
    account: SocialAccount,
    client: Any,
    *,
    force: bool = False,
) -> dict[str, Any]:
    telethon = getattr(client, "client", client)
    if telethon is None:
        return {"status": "no_client", "terminated": []}
    result = await enforce_authorizations(telethon, account, force=force)
    return result


async def maybe_guard_hub_clients(hub: Any) -> dict[str, int]:
    from ...alembic.database import async_session_maker

    scanned = 0
    terminated = 0
    if not getattr(hub, "clients", None):
        return {"scanned": 0, "terminated": 0}
    async with async_session_maker() as session:
        for account_id, wrapper in list(hub.clients.items()):
            account = await session.get(SocialAccount, account_id)
            if account is None:
                continue
            try:
                result = await guard_live_client(session, account, wrapper)
            except Exception as exc:
                logger.warning("Session guard tick failed for %s: %s", account_id, exc)
                continue
            scanned += 1
            terminated += len(result.get("terminated") or [])
        await session.commit()
    return {"scanned": scanned, "terminated": terminated}


async def pause_account_session_guard(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    seconds: int = OPERATOR_PAUSE_SECONDS,
) -> dict[str, Any]:
    row = await _load_pool_account(session, automation_id, account_id)
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    until = pause_session_guard(social_account, seconds=seconds)
    await session.commit()
    return {
        "status": "ok",
        "paused_until": until,
        "pool_account": pool_account,
        "social_account": social_account,
    }


async def adopt_account_sessions(
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
        logger.warning("Adopt sessions failed for %s: %s", account_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "pool_account": pool_account,
            "social_account": social_account,
        }
    items = [serialize_authorization(item) for item in raw]
    hashes = sorted({str(item.get("hash") or "") for item in items if item.get("hash") is not None} - {""})
    social_account.known_auth_hashes = hashes
    social_account.telegram_session_count = len(items)
    social_account.session_guard_enabled = True
    social_account.session_guard_paused_until = None
    social_account.session_guard_checked_at = _utc_now()
    social_account.updated_at = _utc_now()
    moved = False
    from .account_pacing import ORIGIN_FARM, account_is_intercept
    from ..account_pool_service import get_or_create_default_pool

    pool = await session.get(AccountPool, pool_account.account_pool_id)
    if account_is_intercept(social_account) or getattr(pool, "purpose", ORIGIN_FARM) == "intercept":
        farm = await get_or_create_default_pool(session, automation_id)
        pool_account.account_pool_id = farm.id
        social_account.origin = ORIGIN_FARM
        social_account.created_at = _utc_now()
        automation = await session.get(CustomAutomation, automation_id)
        from .account_warmup_service import enroll_pool_account
        from .chat_membership_service import ensure_memberships_for_account

        enroll_pool_account(automation, pool_account)
        await ensure_memberships_for_account(session, automation_id, social_account.id)
        moved = True
    await session.commit()
    return {
        "status": "ok",
        "items": items,
        "count": len(items),
        "moved": moved,
        "pool_account": pool_account,
        "social_account": social_account,
    }
