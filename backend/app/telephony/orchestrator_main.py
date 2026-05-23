"""Dedicated telephony orchestrator process (stage 4).

Run: python -m app.telephony.orchestrator_main
Subscribes to Redis `telephony:orch:events` from media gateway.
"""

from __future__ import annotations

import asyncio
import logging

from ..config import settings
from ..logger_config import setup_logger
from .orchestrator_worker import get_worker
from .stream_tts import assert_stream_tts_configured

setup_logger()
logger = logging.getLogger(__name__)


async def _main() -> None:
    if not settings.TELEPHONY_ENABLED:
        logger.error("TELEPHONY_ENABLED=false — orchestrator exiting")
        return
    if not settings.TELEPHONY_ORCHESTRATOR_ENABLED:
        logger.error("TELEPHONY_ORCHESTRATOR_ENABLED=false — orchestrator exiting")
        return
    if not settings.TELEPHONY_STREAMING_ENABLED:
        logger.error("TELEPHONY_STREAMING_ENABLED=false — orchestrator exiting")
        return
    try:
        assert_stream_tts_configured()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return
    worker = get_worker()
    await worker.run_forever()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        get_worker().stop()


if __name__ == "__main__":
    main()
