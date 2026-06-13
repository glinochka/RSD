"""Dedicated telephony worker process (stage 5).

Run: python -m app.telephony.worker_main
Exposes only internal telephony routes on TELEPHONY_WORKER_PORT.
Point telephony_bridge TELEPHONY_BACKEND_URL at this service to isolate LLM load.
"""

from __future__ import annotations

import uvicorn

from ..config import settings
from ..logger_config import setup_logger

setup_logger()


def main() -> None:
    from fastapi import FastAPI
    from ..router_telephony import router as telephony_router

    app = FastAPI(title="rsd-telephony-worker", docs_url=None, redoc_url=None)
    app.include_router(telephony_router)
    port = max(1, int(settings.TELEPHONY_WORKER_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
