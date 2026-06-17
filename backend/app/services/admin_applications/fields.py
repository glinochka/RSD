"""Validation helpers for configurable application form fields."""
from __future__ import annotations

import re
from typing import Any

APPLICATION_FIELD_TYPES = frozenset({"text", "phone", "email", "number", "select", "textarea", "date"})
APPLICATION_STATUSES = frozenset({"new", "in_progress", "completed", "rejected", "cancelled"})
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_field_key(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", str(raw or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise ValueError("field key is required")
    if not _KEY_RE.match(slug):
        raise ValueError(f"invalid field key: {raw!r}")
    return slug


def normalize_application_fields(raw_fields: Any) -> list[dict[str, Any]]:
    if raw_fields is None:
        return []
    if not isinstance(raw_fields, list):
        raise ValueError("application_fields must be an array")
    if len(raw_fields) > 30:
        raise ValueError("application_fields supports at most 30 fields")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_fields):
        if not isinstance(item, dict):
            raise ValueError(f"application_fields[{idx}] must be an object")
        label = str(item.get("label") or "").strip()
        if not label:
            raise ValueError(f"application_fields[{idx}].label is required")
        if len(label) > 128:
            raise ValueError(f"application_fields[{idx}].label is too long")
        key = normalize_field_key(str(item.get("key") or label))
        if key in seen:
            raise ValueError(f"duplicate application field key: {key}")
        seen.add(key)
        field_type = str(item.get("type") or "text").strip().lower()
        if field_type not in APPLICATION_FIELD_TYPES:
            valid = ", ".join(sorted(APPLICATION_FIELD_TYPES))
            raise ValueError(f"application_fields[{idx}].type must be one of: {valid}")
        required = bool(item.get("required", False))
        placeholder = str(item.get("placeholder") or "").strip() or None
        if placeholder and len(placeholder) > 256:
            raise ValueError(f"application_fields[{idx}].placeholder is too long")
        options: list[str] = []
        if field_type == "select":
            raw_options = item.get("options")
            if not isinstance(raw_options, list) or not raw_options:
                raise ValueError(f"application_fields[{idx}].options is required for select fields")
            for opt in raw_options:
                opt_str = str(opt or "").strip()
                if not opt_str:
                    continue
                if len(opt_str) > 128:
                    raise ValueError(f"application_fields[{idx}] option value is too long")
                if opt_str not in options:
                    options.append(opt_str)
            if not options:
                raise ValueError(f"application_fields[{idx}].options must contain at least one value")
        entry: dict[str, Any] = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": required,
        }
        if placeholder:
            entry["placeholder"] = placeholder
        if field_type == "select":
            entry["options"] = options
        normalized.append(entry)
    return normalized


def validate_field_values(
    fields_schema: list[dict[str, Any]],
    raw_values: dict[str, Any] | None,
) -> dict[str, Any]:
    values_in = raw_values if isinstance(raw_values, dict) else {}
    out: dict[str, Any] = {}
    for field in fields_schema:
        key = str(field.get("key") or "")
        if not key:
            continue
        raw = values_in.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            if field.get("required"):
                label = str(field.get("label") or key)
                raise ValueError(f"Поле «{label}» обязательно для заполнения")
            continue
        field_type = str(field.get("type") or "text")
        if field_type in {"text", "textarea", "phone", "email", "date", "select"}:
            value = str(raw).strip()
            if not value:
                if field.get("required"):
                    label = str(field.get("label") or key)
                    raise ValueError(f"Поле «{label}» обязательно для заполнения")
                continue
            if field_type == "email" and not _EMAIL_RE.match(value):
                raise ValueError(f"Некорректный email в поле «{field.get('label') or key}»")
            if field_type == "select":
                options = [str(x) for x in (field.get("options") or [])]
                if value not in options:
                    raise ValueError(f"Недопустимое значение в поле «{field.get('label') or key}»")
            if field_type == "phone" and len(value) > 32:
                raise ValueError(f"Слишком длинный телефон в поле «{field.get('label') or key}»")
            if field_type in {"text", "textarea"} and len(value) > 4000:
                raise ValueError(f"Слишком длинное значение в поле «{field.get('label') or key}»")
            out[key] = value
        elif field_type == "number":
            try:
                num = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Поле «{field.get('label') or key}» должно быть числом")
            out[key] = num
        else:
            out[key] = raw
    return out


def fields_schema_for_prompt(fields_schema: list[dict[str, Any]]) -> str:
    if not fields_schema:
        return "Схема заявки не настроена."
    lines = ["Поля заявки (собирай у клиента перед create_application):"]
    for field in fields_schema:
        req = "обязательное" if field.get("required") else "опциональное"
        label = field.get("label") or field.get("key")
        ftype = field.get("type")
        line = f"- {label} (key={field.get('key')}, type={ftype}, {req})"
        if field.get("type") == "select":
            opts = ", ".join(str(x) for x in (field.get("options") or []))
            line += f"; варианты: {opts}"
        if field.get("placeholder"):
            line += f"; подсказка: {field.get('placeholder')}"
        lines.append(line)
    return "\n".join(lines)
