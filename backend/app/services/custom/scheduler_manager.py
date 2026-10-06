"""Persistent per-automation scheduler for /custom background tasks.

Keeps a dynamic set of asyncio tasks: one for each active automation and
for each job type (join, monitor, neurocommenting, discussion, dmp poll,
amocrm sync). Reconciles the running set with the database every refresh
interval so newly created or deleted automations are picked up without a
restart.
"""
import asyncio
import random
from collections.abc import Awaitable, Callable
from logging import getLogger
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomAutomation
from ...config import settings
from .chat_join_service import run_join_pending_for_automation
from .chat_monitoring_service import scan_chats_and_process
from .dmp_one_service import poll_pending_imports
from .neurocommenting_service import run_lab_neurocommenting_pass
from .amocrm_service import run_amocrm_sync_for_automation
from .chat_discovery_service import run_pending_discovery_for_automation
from .inbound_dm_service import run_inbound_dm_pass
from .lead_warmup_service import run_lead_warmup_pass
from .account_session_orchestrator import close_account_sessions, run_account_sessions
from .chat_moderation_service import run_moderation_probe_pass
from .chat_rotation_service import run_chat_rotation_pass
from .session_hygiene_service import run_session_hygiene_for_automation
from .telegram_notify_bot_service import restore_all_telegram_webhooks, retry_pending_dmp_notifications
from .warmup_module_service import warmup_scheduler_active

logger = getLogger(__name__)

JobFactory = Callable[[int], Awaitable[Any]]


async def _run_job_loop(automation_id: int, job_name: str, job: JobFactory, interval_seconds: int) -> None:
    """Run a job in a loop, catching and logging errors."""
    from .work_mode import apply_work_mode, reset_work_mode

    while True:
        start = asyncio.get_event_loop().time()
        token = None
        try:
            async with async_session_maker() as session:
                automation = await session.get(CustomAutomation, automation_id)
                token = apply_work_mode(automation)
            result = await job(automation_id)
            logger.debug("%s job for automation %s finished: %s", job_name, automation_id, result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("%s job for automation %s failed: %s", job_name, automation_id, exc)
        finally:
            if token is not None:
                reset_work_mode(token)
        elapsed = asyncio.get_event_loop().time() - start
        pause = interval_seconds
        if job_name == "neurocommenting":
            pause = random.randint(120, 180)
        sleep_for = max(1.0, pause - elapsed)
        await asyncio.sleep(sleep_for)


class CustomAutomationScheduler:
    """Manages background jobs for all active /custom automations."""

    def __init__(self) -> None:
        self._tasks: dict[int, dict[str, asyncio.Task]] = {}
        self._scheduler_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @staticmethod
    def _job_intervals() -> dict[str, int]:
        return {
            "monitor": settings.CUSTOM_MONITOR_INTERVAL_SECONDS,
            "join": settings.CUSTOM_JOIN_INTERVAL_SECONDS,
            "discovery": settings.CUSTOM_DISCOVERY_INTERVAL_SECONDS,
            "account_sessions": getattr(settings, "CUSTOM_ACCOUNT_SESSION_INTERVAL_SECONDS", 20),
            "lead_warmup": settings.CUSTOM_LEAD_WARMUP_INTERVAL_SECONDS,
            "inbound_dm": settings.CUSTOM_INBOUND_DM_INTERVAL_SECONDS,
            "mod_probe": settings.CUSTOM_MOD_PROBE_INTERVAL_SECONDS,
            "chat_rotation": settings.CUSTOM_CHAT_ROTATION_INTERVAL_SECONDS,
            "session_hygiene": settings.CUSTOM_SESSION_HYGIENE_INTERVAL_SECONDS,
            "test_watch": settings.CUSTOM_TEST_WATCH_INTERVAL_SECONDS,
            "dmp_poll": settings.DMP_ONE_POLL_INTERVAL_SECONDS,
            "dmp_notify": 60,
            "amocrm_sync": settings.CUSTOM_AMOCRM_SYNC_INTERVAL_SECONDS,
        }

    @staticmethod
    def _job_factories() -> dict[str, JobFactory]:
        return {
            "monitor": scan_chats_and_process,
            "join": run_join_pending_for_automation,
            "discovery": run_pending_discovery_for_automation,
            "account_sessions": run_account_sessions,
            "lead_warmup": run_lead_warmup_pass,
            "inbound_dm": run_inbound_dm_pass,
            "mod_probe": run_moderation_probe_pass,
            "chat_rotation": run_chat_rotation_pass,
            "session_hygiene": run_session_hygiene_for_automation,
            "test_watch": run_lab_neurocommenting_pass,
            "dmp_poll": poll_pending_imports,
            "dmp_notify": retry_pending_dmp_notifications,
            "amocrm_sync": run_amocrm_sync_for_automation,
        }

    @staticmethod
    def _module_enabled(automation: CustomAutomation, key: str) -> bool:
        blob = getattr(automation, "module_settings", None) or {}
        return bool((blob.get(key) or {}).get("enabled"))

    @staticmethod
    def _has_modules_on(automation: CustomAutomation) -> bool:
        return any(
            [
                automation.is_chat_monitoring_enabled,
                automation.is_neurocommenting_enabled,
                automation.is_digital_footprint_enabled,
                automation.is_dmp_one_enabled,
                automation.is_amocrm_enabled,
                automation.is_shilling_enabled,
                CustomAutomationScheduler._module_enabled(automation, "neurocommenting"),
                CustomAutomationScheduler._module_enabled(automation, "neurochatting"),
                CustomAutomationScheduler._module_enabled(automation, "neuroshilling"),
                CustomAutomationScheduler._module_enabled(automation, "masslooking"),
                CustomAutomationScheduler._module_enabled(automation, "masspriming"),
                CustomAutomationScheduler._module_enabled(automation, "chat_broadcasts"),
                CustomAutomationScheduler._module_enabled(automation, "dm_broadcasts"),
                CustomAutomationScheduler._module_enabled(automation, "parser"),
                warmup_scheduler_active(automation),
            ]
        )

    @staticmethod
    def _enabled_jobs(automation: CustomAutomation) -> set[str]:
        from .solution_templates import is_dmp_notify_pipeline, qualification_enabled

        if is_dmp_notify_pipeline(automation):
            jobs: set[str] = {"dmp_notify"}
            if automation.is_dmp_one_enabled:
                jobs.add("dmp_poll")
            if qualification_enabled(automation):
                jobs.add("lead_warmup")
            return jobs

        jobs = {"join", "discovery", "mod_probe", "chat_rotation", "inbound_dm", "session_hygiene", "account_sessions"}
        if (getattr(automation, "test_channel_username", None) or "").strip():
            jobs.add("test_watch")
        if automation.is_chat_monitoring_enabled:
            jobs.add("monitor")
        if automation.is_chat_monitoring_enabled or automation.is_dmp_one_enabled:
            jobs.add("lead_warmup")
        if automation.is_dmp_one_enabled:
            jobs.add("dmp_poll")
        if automation.is_amocrm_enabled:
            jobs.add("amocrm_sync")
        if (getattr(automation, "telegram_bot_token_enc", None) or "").strip():
            jobs.add("dmp_notify")
        return jobs

    async def _fetch_active_automations(self, session: AsyncSession) -> list[CustomAutomation]:
        result = await session.execute(
            select(CustomAutomation).where(CustomAutomation.status != "archived")
        )
        automations = list(result.scalars().all())
        runnable: list[CustomAutomation] = []
        promoted = False
        for automation in automations:
            if automation.status == "active":
                runnable.append(automation)
                continue
            if automation.status == "draft" and self._has_modules_on(automation):
                automation.status = "active"
                promoted = True
                runnable.append(automation)
                logger.info(
                    "Promoted draft automation %s to active because modules are enabled",
                    automation.id,
                )
        if promoted:
            await session.commit()
        return runnable

    async def _reconcile(self) -> None:
        """Start missing jobs and stop jobs for removed or disabled automations."""
        async with async_session_maker() as session:
            try:
                automations = await self._fetch_active_automations(session)
            except Exception as exc:
                logger.exception("Failed to fetch active automations: %s", exc)
                return

        active_ids = {automation.id for automation in automations}
        intervals = self._job_intervals()
        factories = self._job_factories()

        for automation_id in list(self._tasks.keys()):
            if automation_id not in active_ids:
                await self._stop_automation(automation_id)

        for automation in automations:
            wanted = self._enabled_jobs(automation)
            current = self._tasks.setdefault(automation.id, {})
            for job_name in list(current.keys()):
                if job_name not in wanted:
                    task = current.pop(job_name)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.info("Stopped %s job for automation %s", job_name, automation.id)
            for job_name in wanted:
                if job_name in current:
                    continue
                task = asyncio.create_task(
                    _run_job_loop(automation.id, job_name, factories[job_name], intervals[job_name]),
                    name=f"custom-{job_name}-{automation.id}",
                )
                current[job_name] = task
                logger.info("Started %s job for automation %s", job_name, automation.id)

    async def _stop_automation(self, automation_id: int) -> None:
        jobs = self._tasks.pop(automation_id, {})
        for job_name, task in jobs.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped %s job for automation %s", job_name, automation_id)
        await close_account_sessions(automation_id)

    async def _run_scheduler(self) -> None:
        from .solution_templates import ensure_builtin_solutions

        try:
            async with async_session_maker() as session:
                await ensure_builtin_solutions(session)
        except Exception as exc:
            logger.exception("Failed to seed built-in custom solutions: %s", exc)
        try:
            restored = await restore_all_telegram_webhooks()
            logger.info("Restored Telegram notify webhooks: %s", restored)
        except Exception as exc:
            logger.exception("Failed to restore Telegram notify webhooks: %s", exc)
        refresh_interval = settings.CUSTOM_SCHEDULER_REFRESH_INTERVAL_SECONDS
        while not self._stop_event.is_set():
            try:
                await self._reconcile()
            except Exception as exc:
                logger.exception("Custom scheduler reconcile failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=refresh_interval)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._scheduler_task is None:
            self._stop_event.clear()
            self._scheduler_task = asyncio.create_task(self._run_scheduler(), name="custom-scheduler")
            logger.info("Custom automation scheduler started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        for automation_id in list(self._tasks.keys()):
            await self._stop_automation(automation_id)
        logger.info("Custom automation scheduler stopped")
