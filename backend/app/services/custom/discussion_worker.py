"""Discussion / artificial activity periodic worker."""
import asyncio
import logging

from .discussion_service import run_discussion_pass

logger = logging.getLogger(__name__)


class DiscussionWorker:
    """Runs discussion pass for a given automation periodically."""

    def __init__(self, automation_id: int, interval_seconds: int = 300):
        self.automation_id = automation_id
        self.interval_seconds = interval_seconds
        self._task = None

    async def run_once(self) -> dict:
        logger.info("DiscussionWorker started for automation %s", self.automation_id)
        result = await run_discussion_pass(self.automation_id)
        logger.info("DiscussionWorker result: %s", result)
        return result

    async def run(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.exception("DiscussionWorker error for automation %s: %s", self.automation_id, exc)
            await asyncio.sleep(self.interval_seconds)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None
