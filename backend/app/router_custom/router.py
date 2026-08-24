"""Main /custom router."""
from fastapi import APIRouter

from . import admin_router, automation_router


router = APIRouter(prefix="/api/custom")
router.include_router(admin_router.router)
router.include_router(automation_router.router)
