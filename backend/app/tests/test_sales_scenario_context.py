from app.services.sales.sales_scenario_context import (
    SCENARIO_GROUP_CHAT_LEAD_GEN,
    SCENARIO_PRIVATE_DM_CONTINUATION,
    SCENARIO_PRIVATE_DM_INBOUND,
    build_sales_message_frame,
    resolve_sales_interaction_scenario,
)


def test_resolve_group_chat_lead_gen() -> None:
    scenario = resolve_sales_interaction_scenario(
        runtime_context={
            "is_group_chat": True,
            "lead_generation_enabled": True,
        },
        source_channel="telegram_userbot",
        current_sales_state="DISCOVERED",
    )
    assert scenario == SCENARIO_GROUP_CHAT_LEAD_GEN


def test_resolve_private_dm_continuation_by_fsm_state() -> None:
    scenario = resolve_sales_interaction_scenario(
        runtime_context={
            "is_private_chat": True,
            "lead_initiated_private_dialog": True,
        },
        source_channel="whatsapp_userbot",
        current_sales_state="REPLIED_POSITIVE",
    )
    assert scenario == SCENARIO_PRIVATE_DM_CONTINUATION


def test_resolve_private_dm_inbound() -> None:
    scenario = resolve_sales_interaction_scenario(
        runtime_context={
            "is_private_chat": True,
            "lead_initiated_private_dialog": True,
        },
        source_channel="telegram_userbot",
        current_sales_state="DISCOVERED",
    )
    assert scenario == SCENARIO_PRIVATE_DM_INBOUND


def test_build_group_chat_frame_includes_chat_title() -> None:
    frame = build_sales_message_frame(
        scenario=SCENARIO_GROUP_CHAT_LEAD_GEN,
        user_message="Ищем подрядчика по автоматизации",
        runtime_context={
            "source_chat_title": "B2B SaaS Founders",
            "user_display_name": "Иван",
        },
        source_channel="telegram_userbot",
    )
    assert "B2B SaaS Founders" in frame
    assert "Иван" in frame
    assert "личного сообщения" in frame.lower() or "личку" in frame.lower()


def test_build_private_inbound_frame_no_group_reference() -> None:
    frame = build_sales_message_frame(
        scenario=SCENARIO_PRIVATE_DM_INBOUND,
        user_message="Здравствуйте, есть вопрос",
        runtime_context={"user_display_name": "Мария"},
        source_channel="whatsapp_userbot",
    )
    assert "личном чате" in frame.lower()
    assert "Мария" in frame
    assert "увидел" not in frame.lower()
