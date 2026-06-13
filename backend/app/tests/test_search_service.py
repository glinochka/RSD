from types import SimpleNamespace
import json

import pytest

from app.qdrant.search_service import plan_rag_queries


def _completion_with_plan(*, should_search: bool, queries: list[str]):
    payload = {"should_search": should_search, "queries": queries}
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(payload, ensure_ascii=False)))
    message = SimpleNamespace(tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.asyncio
async def test_plan_rag_queries_can_skip_rag(monkeypatch):
    async def fake_create(**kwargs):
        return _completion_with_plan(should_search=False, queries=[])

    monkeypatch.setattr("app.qdrant.search_service.ai_client.chat.completions.create", fake_create)

    planned = await plan_rag_queries("Привет")
    assert planned == []


@pytest.mark.asyncio
async def test_plan_rag_queries_fallback_skips_small_talk(monkeypatch):
    async def fake_create(**kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.qdrant.search_service.ai_client.chat.completions.create", fake_create)

    planned = await plan_rag_queries("Привет!")
    assert planned == []


@pytest.mark.asyncio
async def test_plan_rag_queries_fallback_uses_original_query(monkeypatch):
    async def fake_create(**kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.qdrant.search_service.ai_client.chat.completions.create", fake_create)

    planned = await plan_rag_queries("Сколько стоит подписка Pro?")
    assert planned == ["Сколько стоит подписка Pro?"]
