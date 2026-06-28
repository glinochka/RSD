"""Aggregator for /api/agents routes."""
from fastapi import APIRouter

from .shared import *  # noqa: F403  # re-export for tests and maintenance jobs

from .booking import router as booking_router
from .channels.max import router as channels_max_router
from .channels.telegram import router as channels_telegram_router
from .channels.whatsapp import router as channels_whatsapp_router
from .core import router as core_router
from .crm import router as crm_router
from .integrations import router as integrations_router
from .internal import router as internal_router

router = APIRouter(prefix="/api/agents")
router.include_router(internal_router)
router.include_router(crm_router)
router.include_router(integrations_router)
router.include_router(core_router)
router.include_router(channels_telegram_router)
router.include_router(channels_whatsapp_router)
router.include_router(channels_max_router)
router.include_router(booking_router)
