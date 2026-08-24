"""Persistent per-automation scheduler for /custom background tasks.

Keeps a dynamic set of asyncio tasks: one for each active automation and
for each job type (join, monitor, neurocommenting, discussion, dmp poll,
amocrm sync). Reconciles the running set with the database every refresh
interval so newly created or deleted automations are picked up without a
restart.
"""
import asyncio
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
from .neurocommenting_service import run_neurocommenting_pass
from .discussion_service import run_discussion_pass
from .amocrm_service import run_amocrm_sync_for_automation
from .chat_discovery_service import run_pending_discovery_for_automation
from .lead_warmup_service import run_lead_warmup_pass

logger = getLogger(__name__)

JobFactory = Callable[[int], Awaitable[Any]]


async def _run_job_loop(automation_id: int, job_name: str, job: JobFactory, interval_seconds: int) -> None:
    """Run a job in a loop, catching and logging errors."""
    while True:
        start = asyncio.get_event_loop().time()
        try:
            result = await job(automation_id)
            logger.debug("%s job for automation %s finished: %s", job_name, automation_id, result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("%s job for automation %s failed: %s", job_name, automation_id, exc)
        elapsed = asyncio.get_event_loop().time() - start
        sleep_for = max(1.0, interval_seconds - elapsed)
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
            "neurocommenting": settings.CUSTOM_NEUROCOMMENTING_INTERVAL_SECONDS,
            "discussion": settings.CUSTOM_DISCUSSION_INTERVAL_SECONDS,
            "lead_warmup": settings.CUSTOM_LEAD_WARMUP_INTERVAL_SECONDS,
            "dmp_poll": settings.DMP_ONE_POLL_INTERVAL_SECONDS,
            "amocrm_sync": settings.CUSTOM_AMOCRM_SYNC_INTERVAL_SECONDS,
        }

    @staticmethod
    def _job_factories() -> dict[str, JobFactory]:
        return {
            "monitor": scan_chats_and_process,
            "join": run_join_pending_for_automation,
            "discovery": run_pending_discovery_for_automation,
            "neurocommenting": run_neurocommenting_pass,
            "discussion": run_discussion_pass,
            "lead_warmup": run_lead_warmup_pass,
            "dmp_poll": poll_pending_imports,
            "amocrm_sync": run_amocrm_sync_for_automation,
        }

    @staticmethod
    def _has_modules_on(automation: CustomAutomation) -> bool:
        return any(
            [
                automation.is_chat_monitoring_enabled,
                automation.is_neurocommenting_enabled,
                automation.is_digital_footprint_enabled,
                automation.is_dmp_one_enabled,
                automation.is_amocrm_enabled,
            ]
        )

    @staticmethod
    def _enabled_jobs(automation: CustomAutomation) -> set[str]:
        jobs = {"join", "discovery"}
        if automation.is_chat_monitoring_enabled:
            jobs.add("monitor")
        if automation.is_neurocommenting_enabled:
            jobs.add("neurocommenting")
        if automation.is_digital_footprint_enabled:
            jobs.add("discussion")
        if automation.is_chat_monitoring_enabled or automation.is_dmp_one_enabled:
            jobs.add("lead_warmup")
        if automation.is_dmp_one_enabled:
            jobs.add("dmp_poll")
        if automation.is_amocrm_enabled:
            jobs.add("amocrm_sync")
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

    async def _run_scheduler(self) -> None:
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
