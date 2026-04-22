"""CRM provider factory."""
from __future__ import annotations

from .providers.amocrm import AmoCRMProvider
from .providers.base import CRMProvider


def build_provider(provider: str, *, base_url: str, access_token: str) -> CRMProvider:
    normalized = (provider or "").strip().lower()
    if normalized == "amocrm":
        return AmoCRMProvider(base_url=base_url, access_token=access_token)
    raise RuntimeError(f"Unsupported CRM provider: {provider}")
