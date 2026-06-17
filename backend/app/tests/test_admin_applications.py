"""Tests for admin application intake workflow."""
from __future__ import annotations

import pytest

from app.services.admin_applications.fields import (
    normalize_application_fields,
    validate_field_values,
)
from app.services.admin_applications.service import AdminApplicationService


def test_normalize_application_fields_success():
    fields = normalize_application_fields(
        [
            {
                "key": "company_name",
                "label": "Название компании",
                "type": "text",
                "required": True,
            },
            {
                "label": "Email",
                "type": "email",
                "required": False,
            },
            {
                "key": "plan",
                "label": "Тариф",
                "type": "select",
                "required": True,
                "options": ["Базовый", "Премиум"],
            },
        ]
    )
    assert len(fields) == 3
    assert fields[1]["key"] == "email"
    assert fields[2]["options"] == ["Базовый", "Премиум"]


def test_normalize_application_fields_requires_select_options():
    with pytest.raises(ValueError, match="options"):
        normalize_application_fields(
            [{"key": "plan", "label": "Тариф", "type": "select", "required": True}]
        )


def test_validate_field_values_required_and_email():
    schema = [
        {"key": "email", "label": "Email", "type": "email", "required": True},
        {"key": "note", "label": "Комментарий", "type": "textarea", "required": False},
    ]
    with pytest.raises(ValueError, match="обязательно"):
        validate_field_values(schema, {})
    with pytest.raises(ValueError, match="email"):
        validate_field_values(schema, {"email": "not-an-email"})
    out = validate_field_values(schema, {"email": "user@example.com", "note": "  hello  "})
    assert out == {"email": "user@example.com", "note": "hello"}


def test_application_service_reads_schema_from_config():
    service = AdminApplicationService()
    schema = service.get_fields_schema(
        {
            "workflow_mode": "applications",
            "application_fields": [
                {"key": "phone", "label": "Телефон", "type": "phone", "required": True},
            ],
        }
    )
    assert schema[0]["key"] == "phone"
