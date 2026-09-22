"""Background worker that checks Telegram accounts and updates their profiles."""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_is_resting
from .account_classification_service import classify_account
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import SessionInvalidError, update_account_after_telegram_error
from ...alembic.database import async_session_maker
from ...alembic.models import AccountClass, AccountPool, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings

logger = getLogger(__name__)

_SPAMBLOCK_RECHECK = timedelta(days=7)
_HEALTH_MIN_GAP = timedelta(hours=10)
_RECENT_USE_GAP = timedelta(minutes=15)


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

    async def process_account(
        self,
        session: AsyncSession,
        automation_id: int,
        account_id: int,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        social_account = await session.get(SocialAccount, account_id)
        if not social_account:
            return {"account_id": account_id, "status": "not_found"}

        pool_account = await session.scalar(
            select(PoolAccount).where(PoolAccount.social_account_id == account_id)
        )

        if getattr(social_account, "is_frozen", False):
            social_account.last_health_check_at = _utc_now()
            social_account.updated_at = _utc_now()
            await session.commit()
            return {
                "account_id": account_id,
                "status": "frozen",
                "classification": None,
                "error": "frozen",
            }

        if not force:
            if account_is_resting(social_account):
                return {"account_id": account_id, "status": "skipped", "reason": "resting"}
            used = social_account.last_used_at
            if used is not None:
                then = used.replace(tzinfo=None) if getattr(used, "tzinfo", None) else used
                if (_utc_now() - then) < _RECENT_USE_GAP:
                    return {"account_id": account_id, "status": "skipped", "reason": "in_use"}
            checked = social_account.last_health_check_at
            if checked is not None:
                then = checked.replace(tzinfo=None) if getattr(checked, "tzinfo", None) else checked
                if (_utc_now() - then) < _HEALTH_MIN_GAP:
                    return {"account_id": account_id, "status": "skipped", "reason": "fresh"}

        info = None
        avatar_bytes = None
        error_kind = None
        spam_state = None
        if social_account.session_file_path:
            session_path = _media_root() / social_account.session_file_path
            if not session_path.exists():
                from .telegram_account_client import restore_encrypted_session_file

                restore_encrypted_session_file(social_account.encrypted_session, session_path)
            if session_path.exists():
                last_exc: Exception | None = None
                restored_backup = False
                promoted_spare = False
                for _attempt in range(3):
                    try:
                        need_spam_check = False
                        checked_at = social_account.spamblock_checked_at
                        if checked_at is None:
                            need_spam_check = False
                        else:
                            then = checked_at.replace(tzinfo=None) if getattr(checked_at, "tzinfo", None) else checked_at
                            jitter_days = random.uniform(0, 4)
                            need_spam_check = (_utc_now() - then) >= (_SPAMBLOCK_RECHECK + timedelta(days=jitter_days))
                            if need_spam_check:
                                need_spam_check = random.random() < 0.35
                        include_dialogs = (not bool(social_account.auto_classified)) or random.random() < 0.12
                        async with TelegramAccountClient.for_account(social_account) as client:
                            info = await client.get_info(include_dialogs=include_dialogs)
                            if need_spam_check:
                                spam_state = await client.check_spamblock(force=False)
                            avatar_path = _avatar_path(automation_id, account_id)
                            if info.get("has_avatar") and (force or not avatar_path.exists()):
                                try:
                                    avatar_bytes = await client.download_avatar()
                                except Exception as exc:
                                    logger.warning("Could not download avatar for %s: %s", account_id, exc)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        if isinstance(exc, SessionInvalidError):
                            if not restored_backup:
                                from .telegram_account_client import restore_encrypted_session_file

                                session_path = _media_root() / (social_account.session_file_path or "")
                                restored_backup = restore_encrypted_session_file(
                                    social_account.encrypted_session, session_path
                                )
                                if restored_backup:
                                    logger.warning(
                                        "Health check restored session backup for account %s, retrying",
                                        account_id,
                                    )
                                    continue
                            error_kind = await update_account_after_telegram_error(
                                session, social_account, exc
                            )
                            if error_kind == "session_retry" and not promoted_spare:
                                promoted_spare = True
                                logger.warning(
                                    "Health check promoted spare session for account %s, retrying",
                                    account_id,
                                )
                                continue
                            logger.warning(
                                "Health check failed for account %s: %s (%s)",
                                account_id,
                                exc,
                                error_kind,
                            )
                            break
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

        if error_kind == "session_busy":
            social_account.last_health_check_at = _utc_now()
            social_account.updated_at = _utc_now()
            await session.commit()
            return {
                "account_id": account_id,
                "status": "retry",
                "classification": None,
                "error": error_kind,
            }

        if error_kind in {"session_invalid", "banned", "spamblock", "frozen"}:
            if error_kind in {"session_invalid", "banned", "frozen"}:
                from .chat_membership_service import replace_watchers_for_dead_account

                await replace_watchers_for_dead_account(session, account_id)
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
            self._apply_spam_state(social_account, spam_state)

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

    @staticmethod
    def _apply_spam_state(social_account: SocialAccount, spam_state: dict[str, Any]) -> None:
        blocked = spam_state.get("spamblocked")
        social_account.spamblock_checked_at = _utc_now()
        if blocked is True:
            social_account.is_spamblocked = True
            social_account.spamblocked_at = social_account.spamblocked_at or _utc_now()
        elif blocked is False:
            social_account.is_spamblocked = False
            social_account.spamblocked_at = None
        social_account.updated_at = _utc_now()

    async def check_account_spamblock(
        self,
        session: AsyncSession,
        automation_id: int,
        account_id: int,
    ) -> dict[str, Any]:
        """Ask @SpamBot now, ignoring the periodic 6-hour skip."""
        row = await session.execute(
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.custom_automation_id == automation_id,
                SocialAccount.id == account_id,
            )
        )
        result = row.one_or_none()
        if not result:
            return {"status": "not_found"}
        pool_account, social_account = result
        if not (social_account.session_file_path or "").strip():
            return {
                "status": "no_session",
                "pool_account": pool_account,
                "social_account": social_account,
            }

        session_path = _media_root() / social_account.session_file_path
        if not session_path.exists():
            from .telegram_account_client import restore_encrypted_session_file

            restore_encrypted_session_file(social_account.encrypted_session, session_path)

        spam_state: dict[str, Any] | None = None
        try:
            async with TelegramAccountClient.for_account(social_account) as client:
                spam_state = await client.check_spamblock(force=True)
        except Exception as exc:
            error_kind = await update_account_after_telegram_error(session, social_account, exc)
            social_account.last_health_check_at = _utc_now()
            social_account.updated_at = _utc_now()
            await session.commit()
            await session.refresh(social_account)
            await session.refresh(pool_account)
            return {
                "status": error_kind or "error",
                "spamblocked": True if error_kind == "spamblock" else None,
                "source": "error",
                "detail": str(exc) or error_kind,
                "pool_account": pool_account,
                "social_account": social_account,
            }

        self._apply_spam_state(social_account, spam_state or {})
        social_account.last_health_check_at = _utc_now()
        await session.commit()
        await session.refresh(social_account)
        await session.refresh(pool_account)
        blocked = None if spam_state is None else spam_state.get("spamblocked")
        return {
            "status": "ok",
            "spamblocked": blocked,
            "source": (spam_state or {}).get("source"),
            "pool_account": pool_account,
            "social_account": social_account,
        }

    async def process_accounts(
        self, automation_id: int, account_ids: list[int], *, force: bool = False
    ) -> list[dict[str, Any]]:
        results = []
        async with async_session_maker() as session:
            for account_id in account_ids:
                try:
                    result = await self.process_account(
                        session, automation_id, account_id, force=force
                    )
                    results.append(result)
                except Exception as exc:
                    logger.exception("Account health check failed for %s: %s", account_id, exc)
                    results.append({"account_id": account_id, "status": "error", "error": str(exc)})
        return results

    async def check_all_accounts_for_automation(
        self, automation_id: int, *, force: bool = False
    ) -> list[dict[str, Any]]:
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
        return await self.process_accounts(automation_id, account_ids, force=force)

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


async def run_health_checks_forever(interval_seconds: int = 6 * 3600) -> None:
    """Run light health checks for all automations on a slow loop."""
    worker = AccountHealthWorker()
    while True:
        try:
            await worker.check_all_accounts_for_all_automations()
        except Exception as exc:
            logger.exception("Health checks pass failed: %s", exc)
        await asyncio.sleep(interval_seconds + random.uniform(0, 1800))


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
