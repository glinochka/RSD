from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.crm.factory import build_provider
from app.services.crm.providers.amocrm import AmoCRMProvider
from app.services.crm.providers.bitrix24 import Bitrix24Provider


@pytest.mark.parametrize(
    ("provider_name", "provider_type"),
    [
        ("amocrm", AmoCRMProvider),
        ("bitrix24", Bitrix24Provider),
    ],
)
def test_build_provider_supports_multiple_crm(provider_name: str, provider_type: type):
    provider = build_provider(provider_name, base_url="https://crm.example.test/rest", access_token="x" * 24)
    assert isinstance(provider, provider_type)


def test_build_provider_rejects_unknown_provider():
    with pytest.raises(RuntimeError):
        build_provider("unknown", base_url="https://crm.example.test", access_token="x" * 24)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_name", "provider_type", "health_payload", "expected_external_id"),
    [
        ("amocrm", AmoCRMProvider, {"id": 123, "name": "amo"}, "123"),
        ("bitrix24", Bitrix24Provider, {"ID": "42", "NAME": "bitrix"}, "42"),
    ],
)
async def test_validate_connection_contract(
    provider_name: str,
    provider_type: type,
    health_payload: dict,
    expected_external_id: str,
):
    provider = provider_type(base_url="https://crm.example.test/rest", access_token="x" * 24)
    mock_request = AsyncMock(return_value=health_payload)
    provider._request = mock_request  # type: ignore[attr-defined]

    health = await provider.validate_connection()

    assert health.ok is True
    assert health.provider == provider_name
    assert health.external_id == expected_external_id
    assert mock_request.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_name", "provider_type"),
    [
        ("amocrm", AmoCRMProvider),
        ("bitrix24", Bitrix24Provider),
    ],
)
@pytest.mark.parametrize(
    ("operation", "kwargs"),
    [
        ("find_contact", {"query": "ivan"}),
        ("create_contact", {"name": "Ivan Petrov", "phone": "+79991234567", "email": "ivan@example.com"}),
        ("find_lead", {"query": "acme"}),
        ("create_lead", {"name": "Deal ACME", "price": 9900}),
        ("update_lead", {"lead_id": 17, "fields": {"name": "Deal ACME v2", "price": 19900}}),
        ("add_note", {"entity_type": "lead", "entity_id": 17, "text": "Contract requested"}),
        (
            "create_task",
            {
                "text": "Call customer",
                "complete_till_unix": 1_900_000_000,
                "entity_type": "lead",
                "entity_id": 17,
                "responsible_user_id": 8,
            },
        ),
        ("assign_owner", {"entity_type": "lead", "entity_id": 17, "responsible_user_id": 8}),
    ],
)
async def test_crm_provider_contract_calls(
    provider_name: str,
    provider_type: type,
    operation: str,
    kwargs: dict,
):
    provider = provider_type(base_url="https://crm.example.test/rest", access_token="x" * 24)

    if provider_name == "amocrm":
        expected_returns = {
            "find_contact": {"_embedded": {"contacts": []}},
            "create_contact": [{"id": 1}],
            "find_lead": {"_embedded": {"leads": []}},
            "create_lead": [{"id": 2}],
            "update_lead": [{"id": 17}],
            "add_note": [{"id": 3}],
            "create_task": [{"id": 4}],
            "assign_owner": [{"id": 17}],
        }
    else:
        expected_returns = {
            "find_contact": [{"ID": "1"}],
            "create_contact": 1,
            "find_lead": [{"ID": "2"}],
            "create_lead": 2,
            "update_lead": True,
            "add_note": 3,
            "create_task": {"task": {"id": "4"}},
            "assign_owner": True,
        }

    mock_request = AsyncMock(return_value=expected_returns[operation])
    provider._request = mock_request  # type: ignore[attr-defined]

    result = await getattr(provider, operation)(**kwargs)

    assert isinstance(result, dict)
    assert mock_request.await_count == 1
    args = mock_request.await_args.args
    kw = mock_request.await_args.kwargs

    if provider_name == "amocrm":
        expected = {
            "find_contact": (("GET", "/api/v4/contacts"), {"params": {"query": "ivan"}}),
            "create_contact": (
                ("POST", "/api/v4/contacts"),
                {
                    "json_body": [
                        {
                            "name": "Ivan Petrov",
                            "custom_fields_values": [
                                {"field_code": "PHONE", "values": [{"value": "+79991234567"}]},
                                {"field_code": "EMAIL", "values": [{"value": "ivan@example.com"}]},
                            ],
                        }
                    ]
                },
            ),
            "find_lead": (("GET", "/api/v4/leads"), {"params": {"query": "acme"}}),
            "create_lead": (("POST", "/api/v4/leads"), {"json_body": [{"name": "Deal ACME", "price": 9900}]}),
            "update_lead": (
                ("PATCH", "/api/v4/leads"),
                {"json_body": [{"id": 17, "name": "Deal ACME v2", "price": 19900}]},
            ),
            "add_note": (
                ("POST", "/api/v4/leads/17/notes"),
                {"json_body": [{"note_type": "common", "params": {"text": "Contract requested"}}]},
            ),
            "create_task": (
                ("POST", "/api/v4/tasks"),
                {
                    "json_body": [
                        {
                            "text": "Call customer",
                            "complete_till": 1_900_000_000,
                            "entity_id": 17,
                            "entity_type": "lead",
                            "responsible_user_id": 8,
                        }
                    ]
                },
            ),
            "assign_owner": (
                ("PATCH", "/api/v4/leads"),
                {"json_body": [{"id": 17, "responsible_user_id": 8}]},
            ),
        }[operation]
        assert args == expected[0]
        assert kw == expected[1]
    else:
        expected = {
            "find_contact": (
                ("crm.contact.list",),
                {"payload": {"filter": {"FIND": "ivan"}, "select": ["ID", "NAME", "PHONE", "EMAIL"]}},
            ),
            "create_contact": (
                ("crm.contact.add",),
                {
                    "payload": {
                        "fields": {
                            "NAME": "Ivan Petrov",
                            "PHONE": [{"VALUE": "+79991234567", "VALUE_TYPE": "WORK"}],
                            "EMAIL": [{"VALUE": "ivan@example.com", "VALUE_TYPE": "WORK"}],
                        }
                    }
                },
            ),
            "find_lead": (
                ("crm.lead.list",),
                {"payload": {"filter": {"FIND": "acme"}, "select": ["ID", "TITLE", "STATUS_ID", "OPPORTUNITY"]}},
            ),
            "create_lead": (
                ("crm.lead.add",),
                {"payload": {"fields": {"TITLE": "Deal ACME", "OPPORTUNITY": 9900}}},
            ),
            "update_lead": (
                ("crm.lead.update",),
                {"payload": {"id": 17, "fields": {"TITLE": "Deal ACME v2", "OPPORTUNITY": 19900}}},
            ),
            "add_note": (
                ("crm.timeline.comment.add",),
                {"payload": {"fields": {"ENTITY_ID": 17, "ENTITY_TYPE": "lead", "COMMENT": "Contract requested"}}},
            ),
            "create_task": (
                ("tasks.task.add",),
                {
                    "payload": {
                        "fields": {
                            "TITLE": "Call customer",
                            "DESCRIPTION": "Call customer",
                            "UF_CRM_TASK": ["L_17"],
                            "RESPONSIBLE_ID": 8,
                        }
                    }
                },
            ),
            "assign_owner": (
                ("crm.lead.update",),
                {"payload": {"id": 17, "fields": {"ASSIGNED_BY_ID": 8}}},
            ),
        }[operation]
        assert args == expected[0]
        # Deadline is deterministic format from unix timestamp.
        if operation == "create_task":
            assert kw["payload"]["fields"]["DEADLINE"] == "2030-03-17T17:46:40Z"
            reduced_payload = dict(kw["payload"])
            reduced_payload["fields"] = dict(kw["payload"]["fields"])
            reduced_payload["fields"].pop("DEADLINE", None)
            assert reduced_payload == expected[1]["payload"]
        else:
            assert kw == expected[1]
