"""AmoCRM sync worker."""
import asyncio
import logging

from .amocrm_service import sync_lead_statuses

logger = logging.getLogger(__name__)


class AmocrmSyncWorker:
    """Periodically syncs lead statuses from AmoCRM."""

    def __init__(self, automation_id: int, interval_seconds: int = 300):
        self.automation_id = automation_id
        self.interval_seconds = interval_seconds
        self._task = None

    async def run_once(self) -> dict:
        logger.info("AmocrmSyncWorker started for automation %s", self.automation_id)
        result = await sync_lead_statuses(self.automation_id)
        logger.info("AmocrmSyncWorker result: %s", result)
        return result

    async def run(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("AmocrmSyncWorker error for automation %s: %s", self.automation_id, exc)
            await asyncio.sleep(self.interval_seconds)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None
