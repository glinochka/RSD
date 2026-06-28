"""Unified parsing of agent.template_config JSON."""

from __future__ import annotations

import json
from typing import Any


def parse_agent_template_config(
    raw: str | dict | None,
    *,
    none_if_empty: bool = False,
) -> dict[str, Any] | None:
    """Parse template_config from DB (JSON string), dict, or None.

    By default returns ``{}`` for missing/invalid input. Pass ``none_if_empty=True``
    when callers need ``None`` (telephony guards, message processor).
    """
    empty: dict[str, Any] | None = None if none_if_empty else {}

    if raw is None:
        return empty
    if isinstance(raw, dict):
        return raw if raw else empty
    text = str(raw).strip()
    if not text:
        return empty
    try:
        loaded = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return empty
    if isinstance(loaded, dict):
        return loaded
    return empty
