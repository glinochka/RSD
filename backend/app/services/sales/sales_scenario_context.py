"""Контекст сценария sales_manager для промптов LLM."""

from __future__ import annotations

from typing import Any

from ...prompts.system_prompts import (
    CLIENT_MESSAGE_HEADER,
    INTERNAL_CONTEXT_PREAMBLE,
    format_rag_chunks_for_prompt,
)

SALES_INTERACTION_HINT = "sales_interaction_hint"

SCENARIO_CHANNEL_NEURO_COMMENT = "channel_neuro_comment"
SCENARIO_GROUP_CHAT_LEAD_GEN = "group_chat_lead_gen"
SCENARIO_GROUP_CHAT_LIVE = "group_chat_live"
SCENARIO_PRIVATE_DM_INBOUND = "private_dm_inbound"
SCENARIO_PRIVATE_DM_CONTINUATION = "private_dm_continuation"
SCENARIO_COLD_OUTREACH = "cold_outreach"
SCENARIO_FOLLOW_UP = "follow_up"
SCENARIO_GENERIC_INBOUND = "generic_inbound"

_CONTINUATION_STATES = frozenset(
    {"SENT", "REPLIED_POSITIVE", "REPLIED_NEGATIVE", "HANDOFF_CRM", "QUEUED"}
)

_CHANNEL_LABELS: dict[str, str] = {
    "telegram_userbot": "Telegram",
    "whatsapp_userbot": "WhatsApp",
    "max_userbot": "MAX",
    "telegram": "Telegram",
    "website": "сайт",
    "external_api": "внешний API",
}


def _channel_label(source_channel: str | None) -> str:
    key = str(source_channel or "").strip().lower()
    return _CHANNEL_LABELS.get(key, key or "мессенджер")


def _display_name(runtime_context: dict[str, Any] | None, user_display_name: str | None) -> str:
    explicit = str(user_display_name or "").strip()
    if explicit:
        return explicit
    from_ctx = str((runtime_context or {}).get("user_display_name") or "").strip()
    if from_ctx:
        return from_ctx
    return "клиента"


def _chat_title(runtime_context: dict[str, Any] | None) -> str:
    ctx = runtime_context or {}
    for key in ("source_chat_title", "chat_title"):
        title = str(ctx.get(key) or "").strip()
        if title:
            return title
    chat_id = str(ctx.get("source_chat_id") or "").strip()
    if chat_id and chat_id not in {"0", "global"}:
        return f"чат {chat_id}"
    return "групповом чате"


def resolve_sales_interaction_scenario(
    *,
    runtime_context: dict[str, Any] | None = None,
    source_channel: str | None = None,
    current_sales_state: str = "DISCOVERED",
    interaction_hint: str | None = None,
) -> str:
    """Определяет сценарий взаимодействия для sales_manager."""
    ctx = runtime_context or {}
    hint = str(interaction_hint or ctx.get(SALES_INTERACTION_HINT) or "").strip().lower()
    if hint:
        return hint

    state = (current_sales_state or "DISCOVERED").strip().upper()

    if bool(ctx.get("is_channel_chat")) and bool(ctx.get("neuro_commenting_enabled")):
        return SCENARIO_CHANNEL_NEURO_COMMENT

    is_private = bool(ctx.get("is_private_chat") or ctx.get("lead_initiated_private_dialog"))
    if is_private:
        if state in _CONTINUATION_STATES:
            return SCENARIO_PRIVATE_DM_CONTINUATION
        return SCENARIO_PRIVATE_DM_INBOUND

    if bool(ctx.get("is_group_chat")):
        if bool(ctx.get("live_chat_simulation_enabled")) and not bool(ctx.get("lead_generation_enabled")):
            return SCENARIO_GROUP_CHAT_LIVE
        return SCENARIO_GROUP_CHAT_LEAD_GEN

    _ = source_channel
    return SCENARIO_GENERIC_INBOUND


def build_sales_scenario_system_addon(*, scenario: str) -> str:
    """Короткое дополнение к system prompt под сценарий."""
    if scenario == SCENARIO_GROUP_CHAT_LEAD_GEN:
        return (
            "Сейчас ты анализируешь сообщение из группового чата. "
            "Ответ в группу не нужен — только квалификация лида и текст первого личного сообщения (DM)."
        )
    if scenario == SCENARIO_GROUP_CHAT_LIVE:
        return (
            "Сейчас ты анализируешь сообщение из группового чата в режиме живого общения. "
            "Сформируй релевантный ответ для личного продолжения диалога."
        )
    if scenario == SCENARIO_PRIVATE_DM_INBOUND:
        return (
            "Клиент сам написал в личный чат. Отвечай напрямую, без фразы «увидел ваше сообщение в чате»."
        )
    if scenario == SCENARIO_PRIVATE_DM_CONTINUATION:
        return (
            "Это продолжение личного диалога после предыдущих касаний. "
            "Не начинай заново — опирайся на стадию сделки и историю."
        )
    if scenario == SCENARIO_COLD_OUTREACH:
        from ...prompts.system_prompts import EXCEL_COLD_OUTREACH_EXTRA

        return EXCEL_COLD_OUTREACH_EXTRA
    if scenario == SCENARIO_FOLLOW_UP:
        return (
            "Это follow-up: клиент не ответил на предыдущие сообщения. "
            "Напомни о себе мягко, без давления и без дублирования первого касания."
        )
    if scenario == SCENARIO_CHANNEL_NEURO_COMMENT:
        return "Пиши публичный комментарий под постом, а не личное сообщение."
    return ""


def build_sales_message_frame(
    *,
    scenario: str,
    user_message: str,
    runtime_context: dict[str, Any] | None = None,
    source_channel: str | None = None,
    current_sales_state: str = "DISCOVERED",
    user_display_name: str | None = None,
) -> str:
    """Служебное описание ситуации (без текста реплики клиента — он передаётся отдельно)."""
    name = _display_name(runtime_context, user_display_name)
    channel = _channel_label(source_channel)
    chat = _chat_title(runtime_context)
    state = (current_sales_state or "DISCOVERED").strip().upper()
    _ = user_message

    if scenario == SCENARIO_CHANNEL_NEURO_COMMENT:
        return (
            f"Публичный комментарий под постом в канале «{chat}». "
            f"Нужен короткий комментарий под постом, не личное сообщение."
        )

    if scenario == SCENARIO_GROUP_CHAT_LEAD_GEN:
        return (
            f"Лидогенерация из группового чата «{chat}». "
            f"Пользователь {name} написал в группе. Ты ещё не писал ему в личку — "
            f"оцени, стоит ли писать, и если да, подготовь текст первого личного сообщения (не ответ в группу)."
        )

    if scenario == SCENARIO_GROUP_CHAT_LIVE:
        return (
            f"Живое общение в групповом чате «{chat}». "
            f"Пользователь {name} написал в группе — ответь естественно и по делу."
        )

    if scenario == SCENARIO_PRIVATE_DM_INBOUND:
        return (
            f"Личный диалог ({channel}): клиент {name} написал первым. "
            f"Ты общаешься с ним напрямую в личном чате."
        )

    if scenario == SCENARIO_PRIVATE_DM_CONTINUATION:
        return (
            f"Продолжение личного диалога ({channel}) с {name}. "
            f"Стадия CRM (служебно): {state}. Не начинай диалог с нуля."
        )

    if scenario == SCENARIO_COLD_OUTREACH:
        return (
            f"Холодное первое касание для {name}. "
            f"Прямого входящего сообщения от клиента нет — используй данные контакта ниже."
        )

    if scenario == SCENARIO_FOLLOW_UP:
        tier = str((runtime_context or {}).get("follow_up_tier") or "").strip().lower()
        tier_note = f", тип напоминания: {tier}" if tier else ""
        return (
            f"Follow-up в личном чате с {name}{tier_note}. "
            f"Клиент не ответил на предыдущие сообщения. Стадия CRM (служебно): {state}."
        )

    return f"Входящее сообщение ({channel}) от {name}."


def build_sales_compose_action_instruction(*, scenario: str) -> str:
    """Инструкция для compose_dm в зависимости от сценария."""
    if scenario in {SCENARIO_GROUP_CHAT_LEAD_GEN, SCENARIO_GENERIC_INBOUND}:
        return (
            "Напиши текст первого личного сообщения (DM) клиенту. "
            "Если это первый контакт из группы — можно мягко начать: "
            "«увидел ваше сообщение в чате, подскажите, вам интересно ...». "
            "Только текст сообщения, 1-4 предложения."
        )
    if scenario == SCENARIO_PRIVATE_DM_INBOUND:
        return (
            "Напиши ответ клиенту в личном чате. Клиент написал первым — "
            "не используй «увидел в чате». Только текст сообщения, 1-4 предложения."
        )
    if scenario == SCENARIO_PRIVATE_DM_CONTINUATION:
        return (
            "Напиши следующее сообщение в продолжении личного диалога. "
            "Только текст сообщения, 1-4 предложения."
        )
    if scenario == SCENARIO_COLD_OUTREACH:
        return (
            "Напиши первое холодное сообщение: мягко, без агрессивных продаж. "
            "Только текст сообщения, 1-4 предложения."
        )
    if scenario == SCENARIO_FOLLOW_UP:
        return (
            "Напиши короткое follow-up без давления. "
            "Только текст сообщения, 1-2 предложения."
        )
    return "Напиши следующее сообщение sales-диалога. Только текст, 1-4 предложения."


def build_sales_llm_user_prompt(
    *,
    scenario: str,
    user_message: str,
    context_list: list[dict[str, Any]] | None,
    message_frame: str | None = None,
    qualification: dict[str, Any] | None = None,
    task_instruction: str,
) -> str:
    """User prompt для sales LLM: служебное отдельно, реплика клиента — для ответа."""
    import json

    frame = (message_frame or "").strip()
    internal_sections: list[str] = []
    if frame:
        internal_sections.append(frame)
    if context_list:
        rag_text = format_rag_chunks_for_prompt(context_list)
        internal_sections.append(f"Справочные материалы о продукте:\n{rag_text}")
    if qualification:
        internal_sections.append(
            "Квалификация лида (служебно, не показывать клиенту):\n"
            f"{json.dumps(qualification, ensure_ascii=False)}"
        )

    parts: list[str] = []
    if internal_sections:
        parts.append(INTERNAL_CONTEXT_PREAMBLE)
        parts.append("\n\n".join(internal_sections))
        parts.append("---")
    parts.append(CLIENT_MESSAGE_HEADER)
    parts.append(str(user_message or "").strip())
    parts.append(task_instruction.strip())
    return "\n\n".join(parts)


def build_sales_unified_task_instruction(*, scenario: str) -> str:
    """Инструкция для unified qualify+compose."""
    if scenario in {SCENARIO_GROUP_CHAT_LEAD_GEN, SCENARIO_GROUP_CHAT_LIVE, SCENARIO_GENERIC_INBOUND}:
        return (
            "Верни JSON. Реши, стоит ли писать человеку в личку. "
            "В composed_message — только текст первого личного сообщения (не ответ в группу), "
            "без служебных пометок."
        )
    if scenario == SCENARIO_PRIVATE_DM_INBOUND:
        return (
            "Верни JSON. decision=engage, если диалог уместен. "
            "В composed_message — прямой ответ в личном чате, без «увидел в чате»."
        )
    if scenario == SCENARIO_PRIVATE_DM_CONTINUATION:
        return (
            "Верни JSON. В composed_message — следующий ответ клиенту, без перезапуска диалога."
        )
    return (
        "Верни JSON с квалификацией. "
        "В composed_message — только текст сообщения клиенту, без служебных пометок."
    )
