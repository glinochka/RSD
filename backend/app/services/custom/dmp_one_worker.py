"""DMP.one polling worker."""
import asyncio
import logging

from .dmp_one_service import poll_pending_imports

logger = logging.getLogger(__name__)


class DmpOnePollingWorker:
    """Periodically polls DMP.one for pending order results."""

    def __init__(self, automation_id: int, interval_seconds: int | None = None):
        self.automation_id = automation_id
        self.interval_seconds = interval_seconds or 300
        self._task = None

    async def run_once(self) -> dict:
        logger.info("DmpOnePollingWorker started for automation %s", self.automation_id)
        result = await poll_pending_imports(self.automation_id)
        logger.info("DmpOnePollingWorker result: %s", result)
        return result

    async def run(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("DmpOnePollingWorker error for automation %s: %s", self.automation_id, exc)
            await asyncio.sleep(self.interval_seconds)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None
