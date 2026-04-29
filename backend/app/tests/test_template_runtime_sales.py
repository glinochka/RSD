from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import json

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

    async def fake_create(**kwargs):
        return _completion(
            '{"decision":"engage","intent":"target_hot","confidence":0.93,"reason":"прямой спрос",'
            '"lead_temperature":"hot","lead_heat_score":85,"resilience_score":70,"engagement_score":93,'
            '"stage_hint":"discovery","handoff_ready":false,"workflow_outcome":"continue",'
            '"composed_message":"Здравствуйте! Могу помочь с решением под ваш кейс. Хотите кратко покажу варианты?"}'
        )

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
        return _completion(
            '{"decision":"engage","intent":"target_warm","confidence":0.31,"reason":"слабый сигнал",'
            '"lead_temperature":"warm","lead_heat_score":55,"resilience_score":50,"engagement_score":31,'
            '"stage_hint":"first_touch","handoff_ready":false,"workflow_outcome":"continue",'
            '"composed_message":"Возможно, вам будет интересно узнать о наших решениях."}'
        )

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
            return _completion(
                '{"decision":"engage","intent":"target_hot","confidence":0.99,"reason":"явный запрос",'
                '"lead_temperature":"hot","lead_heat_score":90,"resilience_score":80,"engagement_score":99,'
                '"stage_hint":"discovery","handoff_ready":false,"workflow_outcome":"continue",'
                '"composed_message":"Здравствуйте! Могу предложить решение под ваш запрос."}'
            )
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
    assert result.tool_events[0]["tool_status"] == "sent_auto"


@pytest.mark.asyncio
async def test_crm_admin_runtime_uses_booking_tools_without_crm_connection(monkeypatch):
    service = TemplateRuntimeService()
    calls = {"n": 0}

    class _FakeBookingRegistry:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        def tools_for_llm(self):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "list_staff",
                        "description": "List staff",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

        def has_tool(self, tool_name: str) -> bool:
            return tool_name == "list_staff"

        async def execute_tool(self, tool_name: str, raw_arguments: str):
            return {
                "ok": True,
                "tool_name": "list_staff",
                "tool_args_hash": "hash",
                "tool_status": "success",
                "crm_provider": "booking",
                "latency_ms": 5,
                "idempotency_key": "idem-key",
                "result": {"items": [{"id": 1, "name": "Doctor A"}]},
            }

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion_with_tool_call("list_staff", "{}")
        return _completion("Нашёл свободных специалистов и могу продолжить запись.")

    async def fake_get_connection(self, *, agent_id: int, provider: str):
        return None

    monkeypatch.setattr("app.services.template_runtime.ai_client.chat.completions.create", fake_create)
    monkeypatch.setattr("app.services.template_runtime.AdminBookingToolRegistry", _FakeBookingRegistry)
    monkeypatch.setattr("app.services.template_runtime.TemplateRuntimeService._get_active_crm_connection", fake_get_connection)

    result = await service.execute(
        template_type="crm_admin",
        prompt="Ты администратор записи",
        user_message="Покажи доступных специалистов",
        knowledge_scope_id=101,
        agent_id=77,
        template_config={
            "crm_provider": "amocrm",
            "booking_backend": "local",
            "domain_type": "dental_clinic",
            "allowed_booking_tools": ["list_staff"],
        },
        source_channel="telegram",
        user_external_id="12345",
    )

    assert "продолжить запись" in result.answer.lower()
    assert result.tool_events
    assert result.tool_events[0]["tool_name"] == "list_staff"
    assert result.tool_events[0]["crm_provider"] == "booking"


@pytest.mark.asyncio
async def test_crm_admin_runtime_executes_dsml_tool_calls(monkeypatch):
    service = TemplateRuntimeService()
    calls = {"n": 0, "args": None}

    class _FakeBookingRegistry:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        def tools_for_llm(self):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "create_appointment",
                        "description": "Create appointment",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]

        def has_tool(self, tool_name: str) -> bool:
            return tool_name == "create_appointment"

        async def execute_tool(self, tool_name: str, raw_arguments: str):
            calls["args"] = raw_arguments
            return {
                "ok": True,
                "tool_name": "create_appointment",
                "tool_args_hash": "hash",
                "tool_status": "success",
                "crm_provider": "booking",
                "latency_ms": 5,
                "idempotency_key": "idem-key",
                "result": {"id": 501, "status": "booked"},
            }

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion(
                'Отлично, повторяю запись.\n\n'
                '<｜DSML｜tool_calls>\n'
                '<｜DSML｜invoke name="create_appointment">\n'
                '<｜DSML｜parameter name="starts_at" string="true">2026-04-30T13:00:00</｜DSML｜parameter>\n'
                '<｜DSML｜parameter name="ends_at" string="true">2026-04-30T13:30:00</｜DSML｜parameter>\n'
                '<｜DSML｜parameter name="staff_id" string="false">7</｜DSML｜parameter>\n'
                '<｜DSML｜parameter name="service_id" string="false">1</｜DSML｜parameter>\n'
                '<｜DSML｜parameter name="client_name" string="true">Петр</｜DSML｜parameter>\n'
                '</｜DSML｜invoke>\n'
                '</｜DSML｜tool_calls>'
            )
        return _completion("Готово! Запись создана на 30 апреля в 13:00.")

    async def fake_get_connection(self, *, agent_id: int, provider: str):
        return None

    monkeypatch.setattr("app.services.template_runtime.ai_client.chat.completions.create", fake_create)
    monkeypatch.setattr("app.services.template_runtime.AdminBookingToolRegistry", _FakeBookingRegistry)
    monkeypatch.setattr("app.services.template_runtime.TemplateRuntimeService._get_active_crm_connection", fake_get_connection)

    result = await service.execute(
        template_type="crm_admin",
        prompt="Ты администратор записи",
        user_message="Запиши меня к Анне на 30 апреля в 13:00",
        knowledge_scope_id=101,
        agent_id=77,
        template_config={
            "crm_provider": "amocrm",
            "booking_backend": "local",
            "domain_type": "beauty_salon",
            "allowed_booking_tools": ["create_appointment"],
        },
        source_channel="telegram",
        user_external_id="12345",
    )

    assert "tool_calls" not in result.answer
    assert "запись создана" in result.answer.lower()
    assert result.tool_events
    assert result.tool_events[0]["tool_name"] == "create_appointment"
    parsed_args = json.loads(str(calls["args"] or "{}"))
    assert parsed_args["staff_id"] == 7


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


@pytest.mark.asyncio
async def test_qa_runtime_marks_owner_handoff_by_marker(monkeypatch):
    service = TemplateRuntimeService()

    async def fake_search(query, agent_id):
        return [{"source": "kb://faq", "text": "FAQ context"}]

    async def fake_generate(user_message, context_list, prompt):
        return "[OWNER_HANDOFF] Нужна ручная проверка тарифа у владельца."

    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.generate_answer_with_context", fake_generate)

    result = await service.execute(
        template_type="qa",
        prompt="Ты QA-ассистент",
        user_message="Какой у меня индивидуальный тариф?",
        knowledge_scope_id=101,
    )

    assert "ручная проверка" in result.answer
    assert result.requires_owner_handoff is True
    assert result.owner_handoff_reason is not None


@pytest.mark.asyncio
async def test_lead_generation_does_not_enable_owner_handoff(monkeypatch):
    service = TemplateRuntimeService()

    async def fake_search(query, agent_id):
        return [{"source": "kb://lead", "text": "Lead context"}]

    async def fake_generate(user_message, context_list, prompt):
        return "[OWNER_HANDOFF] Формальный маркер"

    monkeypatch.setattr("app.services.template_runtime.search_knowledge_base", fake_search)
    monkeypatch.setattr("app.services.template_runtime.generate_answer_with_context", fake_generate)

    result = await service.execute(
        template_type="lead_generation",
        prompt="Ты lead-ассистент",
        user_message="Оставьте контакты",
        knowledge_scope_id=101,
    )

    assert result.answer == "[OWNER_HANDOFF] Формальный маркер"
    assert result.requires_owner_handoff is False
    assert result.owner_handoff_reason is None


@pytest.mark.asyncio
async def test_sales_runtime_private_inbound_skips_target_check(monkeypatch):
    service = TemplateRuntimeService()
    unified_mock = AsyncMock(side_effect=AssertionError("_qualify_and_compose_unified should not be called"))
    monkeypatch.setattr(service, "_qualify_and_compose_unified", unified_mock)
    monkeypatch.setattr(service, "retrieve_offer_context", AsyncMock(return_value=([], [])))
    monkeypatch.setattr(service, "compose_dm", AsyncMock(return_value="Спасибо за сообщение! Могу показать подход под ваш кейс."))
    monkeypatch.setattr(
        service,
        "_execute_sales_tools",
        AsyncMock(return_value=SimpleNamespace(answer="Спасибо за сообщение! Могу показать подход под ваш кейс.", sources=[], tool_events=[{
            "tool_name": "sales_outreach_action",
            "tool_status": "sent_auto",
            "ok": True,
        }])),
    )
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Добрый день, занимаетесь автоматизацией?",
        knowledge_scope_id=101,
        template_config={"mode": "auto", "allowed_tools": ["send_message"]},
        source_channel="telegram_userbot",
        user_external_id="12345",
        agent_id=77,
        runtime_context={"lead_initiated_private_dialog": True},
    )

    assert result.answer.startswith("Спасибо за сообщение!")
    assert unified_mock.await_count == 0


@pytest.mark.asyncio
async def test_sales_runtime_mark_contacted_returns_human_text(monkeypatch):
    service = TemplateRuntimeService()
    human_dm = "Здравствуйте! Да, занимаемся автоматизацией бизнес-процессов. Подскажите ваш кейс?"
    monkeypatch.setattr(
        service,
        "_qualify_and_compose_unified",
        AsyncMock(
            return_value={
                "qualification": {
                    "decision": "engage",
                    "intent": "target_hot",
                    "confidence": 0.98,
                    "reason": "явный интерес",
                    "lead_temperature": "hot",
                    "stage_hint": "discovery",
                    "handoff_ready": False,
                    "workflow_outcome": "continue",
                    "lead_heat_score": 90,
                    "resilience_score": 80,
                    "engagement_score": 98,
                },
                "composed_dm": human_dm,
            }
        ),
    )
    monkeypatch.setattr(service, "retrieve_offer_context", AsyncMock(return_value=([], [])))
    monkeypatch.setattr(
        "app.services.template_runtime.ai_client.chat.completions.create",
        AsyncMock(return_value=_completion_with_tool_call("mark_contacted", '{"channel":"telegram_userbot"}')),
    )
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Добрый день, вы занимаетесь автоматизацией?",
        knowledge_scope_id=101,
        template_config={
            "mode": "draft_only",
            "confirmation_policy": "always_confirm",
            "allowed_tools": ["mark_contacted"],
        },
        source_channel="telegram_userbot",
        user_external_id="12345",
        agent_id=77,
    )

    assert result.tool_events
    assert result.tool_events[0]["tool_status"] == "marked_contacted"
    assert result.answer == human_dm


@pytest.mark.asyncio
async def test_sales_runtime_stops_when_contact_already_terminal(monkeypatch):
    service = TemplateRuntimeService()
    qualify_mock = AsyncMock(side_effect=AssertionError("qualify_message should not be called"))
    monkeypatch.setattr(service, "qualify_message", qualify_mock)
    monkeypatch.setattr(service, "_load_sales_contact_state", AsyncMock(return_value="HANDOFF_CRM"))
    monkeypatch.setattr(service, "_load_recent_channel_history", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Когда можем созвониться?",
        knowledge_scope_id=101,
        template_config={"mode": "auto", "workflow_completion_mode": "auto_finish_on_signal"},
        source_channel="telegram_userbot",
        user_external_id="12345",
        agent_id=77,
    )

    assert "Диалог уже завершен" in result.answer
    assert result.tool_events
    assert result.tool_events[0]["tool_status"] == "workflow_finished_noop"
    assert qualify_mock.await_count == 0


@pytest.mark.asyncio
async def test_sales_runtime_finish_workflow_signal(monkeypatch):
    service = TemplateRuntimeService()
    monkeypatch.setattr(
        service,
        "_qualify_and_compose_unified",
        AsyncMock(
            return_value={
                "qualification": {
                    "decision": "finish",
                    "intent": "workflow_completed",
                    "confidence": 0.99,
                    "reason": "лид подтвердил завершение",
                    "lead_temperature": "hot",
                    "stage_hint": "handoff",
                    "handoff_ready": True,
                    "workflow_outcome": "dialog_finished",
                    "lead_heat_score": 95,
                    "resilience_score": 85,
                    "engagement_score": 99,
                },
                "composed_dm": "Спасибо за подтверждение!",
            }
        ),
    )
    monkeypatch.setattr(service, "retrieve_offer_context", AsyncMock(return_value=([], [])))
    monkeypatch.setattr(service, "_load_sales_contact_state", AsyncMock(return_value="SENT"))
    monkeypatch.setattr(service, "_load_recent_channel_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_transition_sales_state_safe", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.template_runtime.get_sales_fsm_service", lambda: _FakeFSMService())

    result = await service.execute(
        template_type="sales_manager",
        prompt="Ты sales-агент",
        user_message="Спасибо, мы уже все согласовали, можно закрывать",
        knowledge_scope_id=101,
        template_config={"mode": "auto", "workflow_completion_mode": "auto_finish_on_signal"},
        source_channel="telegram_userbot",
        user_external_id="12345",
        agent_id=77,
    )

    assert "Лид переведен в завершенный статус" in result.answer
    assert result.tool_events
    assert result.tool_events[0]["tool_status"] == "workflow_finished"
