"""Public website form submissions → agent dashboard (applications / leads)."""
from __future__ import annotations

import json
import uuid
from typing import Any

from ..alembic.database import async_session_maker
from ..alembic.models import Agent
from .admin_applications.fields import normalize_application_fields, validate_field_values
from .admin_applications.service import get_admin_application_service

DEFAULT_WEBSITE_LEAD_FIELDS: list[dict[str, Any]] = [
    {"key": "name", "label": "Имя", "type": "text", "required": True},
    {"key": "phone", "label": "Телефон", "type": "phone", "required": False},
    {"key": "email", "label": "Email", "type": "email", "required": False},
    {"key": "message", "label": "Сообщение", "type": "textarea", "required": False},
]

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "имя", "fio", "fullname", "full_name", "client_name", "your_name", "username", "contact_name"),
    "phone": ("phone", "tel", "telephone", "телефон", "mobile", "your_phone", "phonenumber"),
    "email": ("email", "e-mail", "mail", "your_email", "почта"),
    "message": ("message", "comment", "comments", "сообщение", "question", "text", "body", "note", "notes", "описание"),
}


def _load_template_config(agent: Agent) -> dict[str, Any]:
    raw = agent.template_config
    if not raw:
        return {}
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        return cfg if isinstance(cfg, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def resolve_application_fields(agent: Agent) -> list[dict[str, Any]]:
    cfg = _load_template_config(agent)
    try:
        fields = normalize_application_fields(cfg.get("application_fields"))
    except ValueError:
        fields = []
    return fields or list(DEFAULT_WEBSITE_LEAD_FIELDS)


def _normalize_key(raw: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(raw or "").lower()).strip("_")


def map_website_form_payload(raw_fields: dict[str, Any] | None) -> dict[str, Any]:
    """Map arbitrary HTML form keys to application schema keys."""
    incoming = raw_fields if isinstance(raw_fields, dict) else {}
    mapped: dict[str, Any] = {}

    for key, value in incoming.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        norm = _normalize_key(key)
        target = None
        for schema_key, aliases in _FIELD_ALIASES.items():
            alias_norms = {_normalize_key(a) for a in aliases}
            if norm in alias_norms or norm == schema_key:
                target = schema_key
                break
        mapped[target or norm] = value

    return mapped


async def submit_website_lead(
    *,
    agent_id: int,
    client_name: str | None,
    fields: dict[str, Any] | None,
    notes: str | None = None,
) -> dict[str, Any]:
    async with async_session_maker() as session:
        agent = await session.get(Agent, agent_id)
        if not agent or not agent.is_active:
            raise ValueError("Agent not found")

        schema = resolve_application_fields(agent)
        mapped = map_website_form_payload(fields)
        if client_name and not mapped.get("name"):
            mapped["name"] = client_name.strip()

        validated = validate_field_values(schema, mapped)
        if not validated:
            raise ValueError("Заполните хотя бы одно поле")

        client_external_id = f"web_{uuid.uuid4().hex[:16]}"
        name = str(validated.get("name") or client_name or "").strip() or None
        template_config = {**_load_template_config(agent), "application_fields": schema}

        async with session.begin():
            row = await get_admin_application_service().create_application(
                session,
                agent_id=agent_id,
                template_config=template_config,
                client_external_id=client_external_id,
                client_name=name,
                fields=validated,
                source_channel="website",
                notes=notes,
            )
        return row
