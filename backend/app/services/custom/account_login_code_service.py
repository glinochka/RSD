"""Read the latest Telegram login code from official service chats (777000)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .inbound_dm_service import TELEGRAM_SERVICE_USER_IDS, is_official_telegram_peer
from .telegram_account_client import TelegramAccountClient
from ...alembic.models import AccountPool, PoolAccount, SocialAccount

logger = logging.getLogger(__name__)

_LOGIN_CODE_RE = re.compile(
    r"(?:login code|код(?:а)?(?:\s+для\s+входа)?(?:\s+в\s+telegram)?)\D{0,24}(\d{5,7})",
    re.IGNORECASE,
)
_BARE_CODE_RE = re.compile(r"\b(\d{5,7})\b")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def extract_login_code(text: str | None) -> str | None:
    blob = str(text or "").strip()
    if not blob:
        return None
    match = _LOGIN_CODE_RE.search(blob)
    if match:
        return match.group(1)
    if "login" in blob.lower() or "вход" in blob.lower() or "код" in blob.lower():
        bare = _BARE_CODE_RE.search(blob)
        if bare:
            return bare.group(1)
    return None


def _message_date(msg: Any) -> datetime | None:
    date = getattr(msg, "date", None)
    if date is None:
        return None
    if getattr(date, "tzinfo", None):
        return date.replace(tzinfo=None)
    return date


async def read_last_telegram_login_code(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> dict[str, Any]:
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
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    if not social_account.session_file_path and not getattr(social_account, "encrypted_session", None):
        return {"status": "no_session", "pool_account": pool_account, "social_account": social_account}

    try:
        async with TelegramAccountClient.for_account(social_account) as client:
            messages = []
            for peer in (777000, *sorted(TELEGRAM_SERVICE_USER_IDS - {777000})):
                try:
                    chunk = await client.get_messages(peer, limit=20)
                except Exception:
                    continue
                messages.extend(list(chunk or []))
            try:
                dialogs = await client.get_dialogs(limit=12)
                for dialog in dialogs or []:
                    entity = getattr(dialog, "entity", None)
                    if entity is None or not is_official_telegram_peer(entity):
                        continue
                    extra = await client.get_messages(entity, limit=12)
                    messages.extend(list(extra or []))
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Login code read failed for account %s: %s", account_id, exc)
        return {
            "status": "error",
            "error": str(exc)[:255],
            "pool_account": pool_account,
            "social_account": social_account,
        }

    best: dict[str, Any] | None = None
    for msg in messages:
        if not msg or getattr(msg, "out", False):
            continue
        code = extract_login_code(getattr(msg, "text", None) or getattr(msg, "message", None))
        if not code:
            continue
        sent_at = _message_date(msg)
        if best is None or (sent_at and (best.get("sent_at") is None or sent_at > best["sent_at"])):
            best = {"code": code, "sent_at": sent_at, "text": str(getattr(msg, "text", None) or "")[:280]}
    if not best:
        return {
            "status": "empty",
            "code": None,
            "sent_at": None,
            "pool_account": pool_account,
            "social_account": social_account,
        }
    return {
        "status": "ok",
        "code": best["code"],
        "sent_at": best["sent_at"],
        "text": best.get("text"),
        "checked_at": _utc_now(),
        "pool_account": pool_account,
        "social_account": social_account,
    }
