import pytest

from app.services.sales.tool_registry import SalesNeedsConfirmationError, SalesToolRegistry


@pytest.mark.asyncio
async def test_sales_tool_registry_idempotency_replay():
    registry = SalesToolRegistry(
        allowed_tools=["record_lead_signal"],
        confirmation_policy="confirm_risky",
        user_message="фиксируем сигнал",
        agent_id=7,
        user_external_id="u-1",
        mode="draft_only",
    )
    raw_args = '{"signal_type":"intent","score":0.88,"details":"warm"}'

    first = await registry.execute_tool("record_lead_signal", raw_args)
    second = await registry.execute_tool("record_lead_signal", raw_args)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent_replay"] is True
    assert first["idempotency_key"] == second["idempotency_key"]


@pytest.mark.asyncio
async def test_sales_tool_registry_confirmation_required():
    registry = SalesToolRegistry(
        allowed_tools=["schedule_dm"],
        confirmation_policy="always_confirm",
        user_message="запусти",
        agent_id=7,
        user_external_id="u-1",
        mode="draft_only",
    )

    with pytest.raises(SalesNeedsConfirmationError):
        await registry.execute_tool(
            "schedule_dm",
            '{"text":"Здравствуйте!","target_user_external_id":"100"}',
        )


@pytest.mark.asyncio
async def test_sales_tool_registry_accepts_natural_yes_after_question(monkeypatch):
    history = [{"role": "assistant", "content": "Отправить это сообщение — подтверждаете?"}]
    registry = SalesToolRegistry(
        allowed_tools=["schedule_dm"],
        confirmation_policy="always_confirm",
        user_message="да",
        agent_id=7,
        user_external_id="u-1",
        mode="draft_only",
        recent_history=history,
    )

    class FakeQueue:
        async def enqueue_dm(self, **kwargs):
            return None

    async def noop_register(**kwargs):
        return None

    monkeypatch.setattr(
        "app.services.sales.dm_queue_service.get_dm_queue_service",
        lambda: FakeQueue(),
    )
    monkeypatch.setattr(
        "app.services.sales.contact_pool.register_user_in_agent_contact_pool",
        noop_register,
    )

    result = await registry.execute_tool(
        "schedule_dm",
        '{"text":"Здравствуйте!","target_user_external_id":"100"}',
    )
    assert result["ok"] is True


def test_sales_tool_registry_max_userbot_outbound_channel():
    registry = SalesToolRegistry(
        allowed_tools=["schedule_dm"],
        confirmation_policy="never_confirm",
        user_message="подтверждаю",
        agent_id=7,
        user_external_id="12345",
        mode="auto",
        source_channel="max_userbot",
    )
    assert registry._outbound_channel == "max_userbot"
