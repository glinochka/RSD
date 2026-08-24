"""Custom automation router package."""
from .router import router
from . import admin_router, automation_router, schemas, dependencies

__all__ = ["router", "admin_router", "automation_router", "schemas", "dependencies"]
