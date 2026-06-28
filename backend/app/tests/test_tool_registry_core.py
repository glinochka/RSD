"""Unit tests for tool_registry_core."""

import pytest
from pydantic import BaseModel, Field

from app.services.tool_registry_core import (
    IdempotencyCache,
    build_idempotency_key,
    build_openai_tool_schema,
    filter_allowed_tools,
    parse_tool_arguments,
    tools_for_llm_from_models,
)


class _SampleArgs(BaseModel):
    query: str = Field(..., min_length=1)


_MODELS = {"find_item": _SampleArgs}
_DESCRIPTIONS = {"find_item": "Find an item."}


def test_filter_allowed_tools_defaults_to_all():
    assert filter_allowed_tools(None, _MODELS) == ["find_item"]


def test_filter_allowed_tools_respects_allowlist():
    assert filter_allowed_tools(["find_item"], _MODELS) == ["find_item"]
    assert filter_allowed_tools(["unknown"], _MODELS) == ["find_item"]


def test_parse_tool_arguments_validates():
    args = parse_tool_arguments('{"query":"x"}', _SampleArgs, tool_name="find_item")
    assert args.query == "x"


def test_parse_tool_arguments_rejects_large_payload():
    huge = "x" * 20_000
    with pytest.raises(RuntimeError, match="too large"):
        parse_tool_arguments(f'{{"query":"{huge}"}}', _SampleArgs, tool_name="find_item")


def test_idempotency_cache_replay():
    cache = IdempotencyCache(ttl_seconds=120)
    key = build_idempotency_key(1, "user", "tool", '{"a":1}')
    cache.set(key, {"result": {"ok": True}})
    assert cache.get(key) == {"result": {"ok": True}}


def test_build_openai_tool_schema_shape():
    schema = build_openai_tool_schema("find_item", _SampleArgs, "desc")
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "find_item"
    assert schema["function"]["description"] == "desc"
    assert "parameters" in schema["function"]


def test_tools_for_llm_from_models():
    tools = tools_for_llm_from_models(["find_item"], _MODELS, _DESCRIPTIONS)
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "find_item"
