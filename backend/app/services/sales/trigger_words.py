"""Normalize sales_manager trigger-word lists (UI, LLM, DB)."""
from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def strip_trigger_word(value: Any) -> str:
    """Remove JSON/markdown noise from a single trigger token."""
    word = str(value or "").strip().lower()
    if not word:
        return ""
    word = _JSON_FENCE_RE.sub("", word).strip()
    if word.startswith("json"):
        word = word[4:].lstrip(" \t:[")
    word = word.strip().strip("[](){}")
    word = word.strip().strip('"').strip("'").strip()
    word = word.strip("[](){}").strip().strip('"').strip("'")
    return word


def _coerce_trigger_words_list(raw_value: Any) -> list[Any]:
    if isinstance(raw_value, list):
        items: list[Any] = []
        for item in raw_value:
            if isinstance(item, str) and item.strip().startswith("["):
                try:
                    nested = json.loads(_JSON_FENCE_RE.sub("", item.strip()))
                    if isinstance(nested, list):
                        items.extend(nested)
                        continue
                except Exception:
                    pass
            items.append(item)
        return items
    if not isinstance(raw_value, str):
        return []
    text = _JSON_FENCE_RE.sub("", raw_value.strip())
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return [segment.strip() for segment in text.split(",") if segment.strip()]


def parse_llm_trigger_words_response(raw: str) -> list[Any]:
    """Parse LLM output that may include ```json fences or prose."""
    return _coerce_trigger_words_list(raw)


def normalize_sales_trigger_words(raw_value: Any) -> list[str]:
    items = _coerce_trigger_words_list(raw_value) if raw_value is not None else []
    normalized: list[str] = []
    for item in items:
        word = strip_trigger_word(item)
        if not word:
            continue
        if len(word) > 64:
            word = word[:64]
        if word not in normalized:
            normalized.append(word)
        if len(normalized) >= 30:
            break
    return normalized or ["купить"]
