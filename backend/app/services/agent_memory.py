"""Client memory block formatting for agent runtimes."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..prompts.system_prompts import CLIENT_MEMORY_PREAMBLE, CLIENT_MEMORY_USAGE_RULES


def _format_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return ""


def format_channel_history_memory(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    rows: list[str] = []
    for item in history[-20:]:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = str(item.get("role") or "").strip().lower()
        label = "Агент" if role == "assistant" else "Клиент"
        ts_str = _format_timestamp(item.get("created_at"))
        if ts_str:
            rows.append(f"[{ts_str}] {label}: {content}")
        else:
            rows.append(f"{label}: {content}")
    return "\n".join(rows)


def build_client_memory_block(
    *,
    portrait: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> str:
    sections: list[str] = []
    portrait_text = (portrait or "").strip()
    if portrait_text:
        sections.append(f"Портрет клиента:\n{portrait_text}")
    history_text = format_channel_history_memory(history)
    if history_text:
        sections.append(f"Недавние реплики:\n{history_text}")
    if not sections:
        return ""
    return f"{CLIENT_MEMORY_PREAMBLE}\n\n" + "\n\n".join(sections)


def build_client_memory_system_section(
    *,
    portrait: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> str:
    """Memory block with usage rules for the system prompt."""
    block = build_client_memory_block(portrait=portrait, history=history)
    if not block:
        return ""
    return f"{CLIENT_MEMORY_USAGE_RULES}\n\n{block}"
