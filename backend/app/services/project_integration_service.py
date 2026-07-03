"""Service layer for project integrations and secure external data handling."""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from app.utils.crypto import encrypt_crm_credentials, decrypt_crm_credentials


ALLOWED_INTEGRATION_TYPES = {
    "webhook",
    "crm_bitrix24",
    "crm_amocrm",
    "external_api",
}


def generate_webhook_token() -> str:
    """Generate a long random URL-safe token for webhook endpoints."""
    return secrets.token_urlsafe(48)[:64]


def validate_integration_type(type: str) -> str:
    """Normalize and validate integration type."""
    normalized = (type or "").strip().lower()
    if normalized not in ALLOWED_INTEGRATION_TYPES:
        raise ValueError(f"Unsupported integration type: {type}")
    return normalized


def serialize_integration(integration) -> dict[str, Any]:
    """Return a public representation of an integration (credentials hidden)."""
    return {
        "id": integration.id,
        "project_id": integration.project_id,
        "name": integration.name,
        "type": integration.type,
        "config": integration.config or {},
        "webhook_url": f"/api/projects/{integration.project_id}/integrations/webhook/{integration.webhook_token}",
        "is_active": integration.is_active,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
        "updated_at": integration.updated_at.isoformat() if integration.updated_at else None,
    }


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    """Encrypt credentials JSON before storing."""
    return encrypt_crm_credentials(json.dumps(credentials, ensure_ascii=False))


def decrypt_credentials(encrypted: str) -> dict[str, Any]:
    """Decrypt stored credentials JSON."""
    raw, _ = decrypt_crm_credentials(encrypted)
    return json.loads(raw) if raw else {}


def bundle_config(config: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Sanitize public config."""
    return dict(config) if config else {}


def credentials_from_request(request: dict[str, Any]) -> dict[str, Any]:
    """Extract credentials from a request, normalizing empty values."""
    creds = request.get("credentials") or {}
    return {k: v for k, v in creds.items() if v not in (None, "")}
