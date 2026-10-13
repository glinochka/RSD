"""Install or change Telegram cloud password (2FA) from the account drawer."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import intercept_is_quiet, intercept_parent_kept
from .telegram_account_client import TelegramAccountClient
from ...alembic.models import AccountPool, PoolAccount, SocialAccount

logger = logging.getLogger(__name__)


class CloudPasswordError(ValueError):
    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def _client_for(account: SocialAccount) -> TelegramAccountClient:
    """2FA is changed through the parent session while it is still alive."""
    return TelegramAccountClient.for_account(account, use_parent=intercept_parent_kept(account))


def _guard_quiet(account: SocialAccount) -> dict[str, Any] | None:
    if intercept_is_quiet(account):
        return {
            "status": "held",
            "error": "Первые 24 часа и до переавторизации аккаунт не трогаем",
        }
    return None


async def update_cloud_password(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    current_password: str | None,
    new_password: str,
    hint: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    row = await _load_pool_account(session, automation_id, account_id)
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    blocked = _guard_quiet(social_account)
    if blocked:
        return {**blocked, "pool_account": pool_account, "social_account": social_account}
    if not social_account.session_file_path and not getattr(social_account, "encrypted_session", None):
        return {"status": "no_session", "pool_account": pool_account, "social_account": social_account}

    new_password = str(new_password or "").strip()
    if len(new_password) < 4:
        raise CloudPasswordError("Новый пароль слишком короткий")
    hint_text = str(hint or "").strip()
    email_text = str(email or "").strip() or None
    current = str(current_password or "").strip() or None

    from telethon.errors import EmailUnconfirmedError, PasswordHashInvalidError
    from telethon.tl import types
    from telethon.tl.functions.account import GetPasswordRequest, UpdatePasswordSettingsRequest
    from telethon import password as pwd_mod

    try:
        async with _client_for(social_account) as wrapper:
            client = wrapper.client
            pwd = await client(GetPasswordRequest())
            has_password = bool(getattr(pwd, "has_password", False))
            if has_password and not current:
                raise CloudPasswordError("Сначала введите текущий облачный пароль")
            if has_password:
                check = pwd_mod.compute_check(pwd, current)
            else:
                check = types.InputCheckPasswordEmpty()
            settings = types.account.PasswordInputSettings(
                new_algo=pwd.new_algo,
                new_password_hash=pwd_mod.compute_digest(pwd.new_algo, new_password),
                hint=hint_text,
                email=email_text,
            )
            try:
                await client(UpdatePasswordSettingsRequest(password=check, new_settings=settings))
            except EmailUnconfirmedError as exc:
                from .intercept_reauth_service import store_cloud_password

                store_cloud_password(social_account, new_password)
                fresh = await client(GetPasswordRequest())
                social_account.updated_at = _utc_now()
                await session.commit()
                return {
                    "status": "need_email_code",
                    "email_pattern": getattr(fresh, "email_unconfirmed_pattern", None)
                    or getattr(pwd, "email_unconfirmed_pattern", None),
                    "code_length": int(getattr(exc, "code_length", 0) or 6),
                    "pool_account": pool_account,
                    "social_account": social_account,
                }
    except CloudPasswordError:
        raise
    except PasswordHashInvalidError as exc:
        raise CloudPasswordError("Неверный текущий облачный пароль") from exc
    except Exception as exc:
        logger.warning("Cloud password update failed for %s: %s", account_id, exc)
        return {
            "status": "error",
            "error": str(exc)[:240],
            "pool_account": pool_account,
            "social_account": social_account,
        }

    from .intercept_reauth_service import store_cloud_password

    store_cloud_password(social_account, new_password)
    social_account.updated_at = _utc_now()
    await session.commit()
    return {
        "status": "ok",
        "pool_account": pool_account,
        "social_account": social_account,
    }


async def confirm_cloud_password_email(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    code: str,
) -> dict[str, Any]:
    row = await _load_pool_account(session, automation_id, account_id)
    if not row:
        return {"status": "not_found"}
    pool_account, social_account = row
    blocked = _guard_quiet(social_account)
    if blocked:
        return {**blocked, "pool_account": pool_account, "social_account": social_account}
    token = str(code or "").strip()
    if not token:
        raise CloudPasswordError("Введите код из письма")

    from telethon.tl.functions.account import ConfirmPasswordEmailRequest

    try:
        async with _client_for(social_account) as wrapper:
            await wrapper.client(ConfirmPasswordEmailRequest(code=token))
    except CloudPasswordError:
        raise
    except Exception as exc:
        logger.warning("Cloud password email confirm failed for %s: %s", account_id, exc)
        message = str(exc)
        if "CODE" in message.upper() or "email" in message.lower():
            raise CloudPasswordError("Неверный код из почты") from exc
        return {
            "status": "error",
            "error": message[:240],
            "pool_account": pool_account,
            "social_account": social_account,
        }

    social_account.updated_at = _utc_now()
    await session.commit()
    return {
        "status": "ok",
        "pool_account": pool_account,
        "social_account": social_account,
    }
