"""Application intake workflow for crm_admin template (consulting, B2B, etc.)."""

from .service import AdminApplicationService, get_admin_application_service

__all__ = ["AdminApplicationService", "get_admin_application_service"]
