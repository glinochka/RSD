import pytest

from app.services.http_integration.executor import hostname_is_blocked, validate_parameters_schema
from app.services.http_integration.errors import HttpIntegrationValidationError
from app.services.http_integration.tool_registry import validate_integration_config_dict


def test_hostname_blocked_private():
    assert hostname_is_blocked("127.0.0.1")
    assert hostname_is_blocked("localhost")
    assert hostname_is_blocked("10.1.2.3")
    assert not hostname_is_blocked("vendor.example")


def test_validate_parameters_schema_requires_consistency():
    with pytest.raises(HttpIntegrationValidationError):
        validate_parameters_schema({"type": "object", "required": ["x"]})

    validate_parameters_schema(
        {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    )


def test_validate_integration_bundle_minimal():
    bundle = {
        "base_url": "https://mis.vendor.example/api",
        "timeout_seconds": 15,
        "default_headers": {"Accept": "application/json"},
        "auth": {"type": "bearer", "token": "t" * 32},
        "tools": [
            {
                "name": "slots",
                "description": "List free slots.",
                "method": "GET",
                "path": "/v1/slots",
                "requires_confirmation": False,
                "parameters": {"type": "object", "properties": {"from": {"type": "string"}}, "required": []},
            }
        ],
    }
    validated = validate_integration_config_dict(bundle)
    assert validated["base_url"].startswith("https://")
    assert len(validated["tools"]) == 1
