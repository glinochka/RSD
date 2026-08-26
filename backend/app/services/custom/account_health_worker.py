"""Background worker that checks Telegram accounts and updates their profiles."""
import asyncio
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_classification_service import classify_account
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import SessionInvalidError, update_account_after_telegram_error
from ...alembic.database import async_session_maker
from ...alembic.models import AccountClass, AccountPool, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings

logger = getLogger(__name__)

_SPAMBLOCK_RECHECK = timedelta(hours=6)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _avatar_path(automation_id: int, account_id: int) -> Path:
    path = _media_root() / "avatars" / str(automation_id) / f"{account_id}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class AccountHealthWorker:
    """Check one or many accounts via Telegram and persist classification results."""

    async def process_account(self, session: AsyncSession, automation_id: int, account_id: int) -> dict[str, Any]:
        social_account = await session.get(SocialAccount, account_id)
        if not social_account:
            return {"account_id": account_id, "status": "not_found"}

        pool_account = await session.scalar(
            select(PoolAccount).where(PoolAccount.social_account_id == account_id)
        )

        info = None
        avatar_bytes = None
        error_kind = None
        spam_state = None
        if social_account.session_file_path:
            session_path = _media_root() / social_account.session_file_path
            if session_path.exists():
                last_exc: Exception | None = None
                for attempt in range(2):
                    try:
                        need_spam_check = True
                        checked_at = social_account.spamblock_checked_at
                        if checked_at is not None:
                            then = checked_at.replace(tzinfo=None) if getattr(checked_at, "tzinfo", None) else checked_at
                            need_spam_check = (_utc_now() - then) >= _SPAMBLOCK_RECHECK
                        async with TelegramAccountClient(str(session_path)) as client:
                            info = await client.get_info()
                            if need_spam_check:
                                spam_state = await client.check_spamblock()
                            if info.get("has_avatar"):
                                try:
                                    avatar_bytes = await client.download_avatar()
                                except Exception as exc:
                                    logger.warning("Could not download avatar for %s: %s", account_id, exc)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        if attempt == 0 and isinstance(exc, SessionInvalidError):
                            logger.warning(
                                "Health check session error for account %s, retrying: %s",
                                account_id,
                                exc,
                            )
                            await asyncio.sleep(2)
                            continue
                        error_kind = await update_account_after_telegram_error(session, social_account, exc)
                        logger.warning("Health check failed for account %s: %s (%s)", account_id, exc, error_kind)
                        break
                if last_exc is not None and error_kind is None:
                    error_kind = await update_account_after_telegram_error(session, social_account, last_exc)
                    logger.warning("Health check failed for account %s: %s (%s)", account_id, last_exc, error_kind)
            else:
                social_account.is_active = False
                error_kind = "session_invalid"
                logger.warning("Session file missing for account %s: %s", account_id, social_account.session_file_path)
        else:
            social_account.is_active = False

        if error_kind in {"session_invalid", "banned", "spamblock"}:
            social_account.last_health_check_at = _utc_now()
            social_account.updated_at = _utc_now()
            await session.commit()
            return {
                "account_id": account_id,
                "status": error_kind,
                "classification": None,
                "error": error_kind,
            }

        classification = classify_account(info)

        if info:
            social_account.is_active = True
            social_account.username = info.get("username") or social_account.username
            social_account.phone_number = info.get("phone_number") or social_account.phone_number
            social_account.display_name = info.get("display_name") or social_account.display_name
            social_account.bio = info.get("bio") or social_account.bio
            social_account.current_bio = info.get("bio") or social_account.current_bio
            social_account.friends_count = info.get("dialogs_count")
            social_account.activity_score = self._activity_score(info)

        if spam_state is not None:
            blocked = spam_state.get("spamblocked")
            social_account.spamblock_checked_at = _utc_now()
            if blocked is True:
                social_account.is_spamblocked = True
                social_account.spamblocked_at = social_account.spamblocked_at or _utc_now()
            elif blocked is False:
                social_account.is_spamblocked = False
                social_account.spamblocked_at = None

        if avatar_bytes:
            try:
                avatar_file = _avatar_path(automation_id, account_id)
                avatar_file.write_bytes(avatar_bytes)
                social_account.avatar_file_path = str(avatar_file.relative_to(_media_root()))
                social_account.avatar_url = f"/media/{social_account.avatar_file_path}"
            except Exception as exc:
                logger.warning("Could not save avatar for account %s: %s", account_id, exc)

        social_account.risk_score = classification["risk_score"]
        social_account.trust_score = classification["trust_score"]
        if social_account.account_class != AccountClass.SHILLING.value:
            social_account.account_class = classification["account_class"]
            social_account.auto_classified = True
            if pool_account:
                pool_account.assigned_class = classification["account_class"]
        elif pool_account:
            pool_account.assigned_class = AccountClass.SHILLING.value
        social_account.last_health_check_at = _utc_now()

        social_account.updated_at = _utc_now()
        await session.commit()

        return {
            "account_id": account_id,
            "status": "ok" if info else "fallback",
            "classification": classification,
        }

    @staticmethod
    def _activity_score(info: dict) -> float:
        dialogs = int(info.get("dialogs_count", 0) or 0)
        has_avatar = 1 if info.get("has_avatar") else 0
        has_bio = 1 if info.get("bio") else 0
        premium = 1 if info.get("is_premium") else 0
        return min(100.0, dialogs * 0.5 + has_avatar * 10 + has_bio * 5 + premium * 10)

    async def process_accounts(self, automation_id: int, account_ids: list[int]) -> list[dict[str, Any]]:
        results = []
        async with async_session_maker() as session:
            for account_id in account_ids:
                try:
                    result = await self.process_account(session, automation_id, account_id)
                    results.append(result)
                except Exception as exc:
                    logger.exception("Account health check failed for %s: %s", account_id, exc)
                    results.append({"account_id": account_id, "status": "error", "error": str(exc)})
        return results

    async def check_all_accounts_for_automation(self, automation_id: int) -> list[dict[str, Any]]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SocialAccount.id)
                .join(PoolAccount)
                .where(
                    PoolAccount.custom_automation_id == automation_id,
                    SocialAccount.is_active.is_(True),
                )
            )
            account_ids = [row[0] for row in result.all()]
        return await self.process_accounts(automation_id, account_ids)

    async def check_all_accounts_for_all_automations(self) -> list[dict[str, Any]]:
        all_results: list[dict[str, Any]] = []
        async with async_session_maker() as session:
            result = await session.execute(
                select(CustomAutomation.id).where(CustomAutomation.status != "archived")
            )
            automation_ids = [row[0] for row in result.all()]
        for automation_id in automation_ids:
            try:
                results = await self.check_all_accounts_for_automation(automation_id)
                all_results.extend(results)
            except Exception as exc:
                logger.exception("Health check for automation %s failed: %s", automation_id, exc)
        return all_results


async def run_health_checks_forever(interval_seconds: int = 300) -> None:
    """Run health checks for all automations on a loop."""
    worker = AccountHealthWorker()
    while True:
        try:
            await worker.check_all_accounts_for_all_automations()
        except Exception as exc:
            logger.exception("Health checks pass failed: %s", exc)
        await asyncio.sleep(interval_seconds)


class AccountHealthScheduler:
    """Periodic scheduler that checks every active account of an automation."""

    def __init__(self, automation_id: int, interval_seconds: int = 300) -> None:
        self.automation_id = automation_id
        self.interval_seconds = interval_seconds
        self._worker = AccountHealthWorker()
        self._task = None
        self._stop_event = asyncio.Event()

    async def run_once(self) -> None:
        try:
            await self._worker.check_all_accounts_for_automation(self.automation_id)
        except Exception as exc:
            logger.exception("Health scheduler run_once failed for automation %s: %s", self.automation_id, exc)

    async def run(self) -> None:
        while not self._stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
