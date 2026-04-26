from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from app.services.template_runtime import TemplateRuntimeService


def _completion(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )


class _FakeToolCall:
    def __init__(self, name: str, arguments: str, call_id: str = "call_1"):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self):
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            },
        }


def _completion_with_tool_call(name: str, arguments: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[_FakeToolCall(name=name, arguments=arguments)],
                )
            )
        ]
    )


class _FakeFSMService:
    async def get_or_create_contact(self, **kwargs):
        return None

    async def transition_contact(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_sales_runtime_draft_only(monkeypatch):
    service = TemplateRuntimeService()
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion('{"intent":"target_hot","confidence":0.93,"reason":"прямой спрос"}')
        return _completion("Здравствуйте! Могу помочь с решением под ваш кейс. Хотите кратко покажу варианты?")

    async def fake_search(query, agent_id):
        return [{"source": "kb://offer", "text": "Мы автоматизируем продажи и поддержку."}]

    monkeypatch.setattr("app.services.template_runtime.ai_client.chat.completions.create", fake_create)
    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Ищем решение для автоматизации отдела продаж",
        knowledge_scope_id=101,
        template_config={"mode": "draft_only", "min_confidence": 0.75},
        source_channel="telegram_userbot",
        user_external_id="12345",
    )

    assert "Черновик outreach" in result.answer
    assert result.sources == ["kb://offer"]
    assert result.tool_events
    assert result.tool_events[0]["tool_status"] == "draft_requires_review"


@pytest.mark.asyncio
async def test_sales_runtime_skip_low_confidence(monkeypatch):
    service = TemplateRuntimeService()

    async def fake_create(**kwargs):
        return _completion('{"intent":"target_warm","confidence":0.31,"reason":"слабый сигнал"}')

    async def fake_search(query, agent_id):
        return [{"source": "kb://offer", "text": "context"}]

    monkeypatch.setattr("app.services.template_runtime.ai_client.chat.completions.create", fake_create)
    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Возможно когда-нибудь внедрим ИИ",
        knowledge_scope_id=101,
        template_config={"mode": "semi_auto", "min_confidence": 0.8},
        source_channel="telegram_userbot",
        user_external_id="12345",
    )

    assert "низкая уверенность" in result.answer.lower()
    assert result.sources == []
    assert result.tool_events
    assert result.tool_events[0]["tool_status"] == "skipped_low_confidence"


@pytest.mark.asyncio
async def test_sales_runtime_function_call_schedule_dm(monkeypatch, mock_db_session):
    service = TemplateRuntimeService()
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion('{"intent":"target_hot","confidence":0.99,"reason":"явный запрос"}')
        if calls["n"] == 2:
            return _completion("Здравствуйте! Могу предложить решение под ваш запрос.")
        return _completion_with_tool_call(
            "schedule_dm",
            '{"text":"Здравствуйте! Могу предложить решение под ваш запрос.","target_user_external_id":"12345"}',
        )

    async def fake_search(query, agent_id):
        return [{"source": "kb://offer", "text": "Контекст оффера"}]

    monkeypatch.setattr("app.services.template_runtime.ai_client.chat.completions.create", fake_create)
    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Нужен подрядчик для AI-автоматизации продаж",
        knowledge_scope_id=101,
        agent_id=77,
        template_config={
            "mode": "draft_only",
            "min_confidence": 0.7,
            "confirmation_policy": "never_confirm",
            "allowed_tools": ["schedule_dm"],
        },
        source_channel="telegram_userbot",
        user_external_id="12345",
    )

    assert result.tool_events
    assert result.tool_events[0]["tool_name"] == "schedule_dm"
    assert result.tool_events[0]["tool_status"] == "draft_requires_review"


@pytest.mark.asyncio
async def test_content_factory_runtime_pipeline_mode_message():
    service = TemplateRuntimeService()
    result = await service.execute(
        template_type="content_factory",
        prompt="Ты агент контент-завода",
        user_message="Придумай пост на сегодня",
        knowledge_scope_id=101,
        source_channel="telegram_userbot",
        user_external_id="12345",
    )

    assert "pipeline-режиме" in result.answer
    assert result.sources == []
    assert result.fallback_to_text is False
    assert result.fallback_reason is None


@pytest.mark.asyncio
async def test_content_factory_runtime_technical_message_fallback(monkeypatch):
    service = TemplateRuntimeService()

    async def fake_search(query, agent_id):
        return [{"source": "kb://ops", "text": "Проверьте OAuth и refresh token."}]

    async def fake_generate(user_message, context_list, prompt):
        return "Техподсказка: обновите OAuth токен и переподключите YouTube."

    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.generate_answer_with_context", fake_generate)

    result = await service.execute(
        template_type="content_factory",
        prompt="Ты агент контент-завода",
        user_message="Ошибка OAuth при подключении YouTube",
        knowledge_scope_id=101,
        source_channel="telegram_userbot",
        user_external_id="12345",
    )

    assert "Техподсказка" in result.answer
    assert result.sources == ["kb://ops"]
    assert result.fallback_to_text is True
    assert result.fallback_reason == "content_factory_technical_fallback"
