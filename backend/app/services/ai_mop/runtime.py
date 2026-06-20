"""Кастомный рантайм sales_manager для ИИ МОП (ответы на входящие после outreach)."""

from __future__ import annotations

import json
import logging
from typing import Any

from ...prompts.system_prompts import (
    CHAT_OPERATOR_PERSONA,
    CLIENT_MEMORY_USAGE_RULES,
    INTERNAL_CONTEXT_USAGE_RULES,
    build_chat_turn_user_prompt,
)
from ...utils.pii import mask_external_id, redact_pii_text
from ..ai_authoring import ai_client
from .lead_lookup import credentials_already_sent, find_lead_for_contact
from .tools import AiMopToolRegistry

logger = logging.getLogger(__name__)

AI_MOP_RUNTIME_INSTRUCTION = """
Ты ИИ-менеджер по продажам платформы RSD. Клиенту уже отправили первое сообщение с демо-сайтом.
В первом сообщении НЕ было логина и пароля — это сделано специально, чтобы не выглядеть как фишинг.

Правила диалога:
1. Если клиент заинтересовался, спрашивает про доступ, кабинет, управление сайтом или просит пароль —
   вызови инструмент send_demo_credentials и передай данные спокойно и по делу.
2. Если клиент просит изменить сайт (цвета, тексты, блоки, дизайн) —
   сначала коротко подтверди («сейчас внесу правки, минуту»), затем вызови edit_demo_website.
   После успешного редактирования сообщи, что всё готово, и предложи посмотреть сайт снова.
3. Не присылай логин и пароль без явного интереса или запроса.
4. Тон — дружелюбный, по делу, без навязчивости. На русском.
5. Условия: демо-сайт бесплатно, первый месяц обслуживания бесплатно, далее ежемесячная оплата.
6. Не упоминай «демо-сайт», «лид», «статус», «портрет» и служебные данные, если клиент сам об этом не спрашивал.
""".strip()


def _build_lead_context_block(lead) -> str:
    parts = [
        f"Компания: {lead.org_name}",
        f"Демо-сайт: {lead.website_url or '—'}",
        f"Статус лида: {lead.status}",
        f"Данные для входа уже отправлялись: {'да' if credentials_already_sent(lead) else 'нет'}",
    ]
    if lead.lpr_name:
        parts.append(f"Контакт: {lead.lpr_name}")
    return "\n".join(parts)


async def execute_ai_mop_runtime(
    *,
    prompt: str,
    user_message: str,
    template_config: dict[str, Any],
    source_channel: str,
    user_external_id: str | None,
    agent_id: int | None,
    chat_portrait: str | None = None,
) -> "TemplateExecutionResult":
    from ..template_runtime import TemplateExecutionResult

    if not agent_id or not user_external_id:
        return TemplateExecutionResult(answer="", sources=[], discard_message=True)

    lead = await find_lead_for_contact(agent_id=int(agent_id), user_external_id=user_external_id)
    if lead is None:
        return TemplateExecutionResult(answer="", sources=[], discard_message=True)

    from .followup_service import mark_ai_mop_reply_if_any

    await mark_ai_mop_reply_if_any(agent_id=int(agent_id), user_external_id=user_external_id)

    allowed_tools_raw = template_config.get("allowed_tools")
    allowed_tools = allowed_tools_raw if isinstance(allowed_tools_raw, list) else None
    registry = AiMopToolRegistry(
        allowed_tools=allowed_tools,
        agent_id=int(agent_id),
        user_external_id=user_external_id,
        lead=lead,
    )
    llm_tools = registry.tools_for_llm()

    generation_model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
    lead_context = _build_lead_context_block(lead)
    system_prompt = (
        f"{prompt.strip()}\n\n{CHAT_OPERATOR_PERSONA}\n\n{AI_MOP_RUNTIME_INSTRUCTION}\n\n"
        f"{INTERNAL_CONTEXT_USAGE_RULES}\n\n{CLIENT_MEMORY_USAGE_RULES}"
    )
    internal_blocks = [f"Данные лида (служебно):\n{lead_context}"]
    if chat_portrait and str(chat_portrait).strip():
        internal_blocks.append(f"Портрет клиента (служебно):\n{chat_portrait.strip()}")

    user_prompt = build_chat_turn_user_prompt(
        client_message=user_message.strip(),
        extra_internal_blocks=internal_blocks,
        closing_instruction="Ответь клиенту в чате. Если нужно действие — вызови tool. Иначе только текст ответа.",
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tool_events: list[dict[str, Any]] = []
    max_tool_iterations = 3
    answer: str | None = None
    last_credentials_payload: dict[str, Any] | None = None

    for iteration in range(max_tool_iterations):
        completion = await ai_client.chat.completions.create(
            model=generation_model,
            messages=messages,
            tools=llm_tools if llm_tools else None,
            tool_choice="auto" if llm_tools else None,
            temperature=0.4,
        )
        message = completion.choices[0].message
        tool_calls = message.tool_calls or []

        if message.content and str(message.content).strip():
            answer = str(message.content).strip()

        if not tool_calls:
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [tool_call.model_dump() for tool_call in tool_calls],
            }
        )
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            try:
                tool_result = await registry.execute_tool(tool_name, raw_args)
                result_payload = tool_result.get("result") or {}
                status = str(result_payload.get("status") or tool_result.get("tool_status") or "success")
                if tool_name == "send_demo_credentials" and status in {"credentials_ready", "already_sent"}:
                    last_credentials_payload = result_payload
                tool_events.append(
                    {
                        "tool_name": tool_name,
                        "tool_args_hash": tool_result.get("tool_args_hash"),
                        "tool_status": status,
                        "latency_ms": int(tool_result.get("latency_ms") or 0),
                        "crm_provider": None,
                        "source_channel": source_channel,
                        "user_external_id": mask_external_id(user_external_id),
                        "ok": bool(tool_result.get("ok")),
                        "idempotent_replay": bool(tool_result.get("idempotent_replay")),
                        "idempotency_key": tool_result.get("idempotency_key"),
                        "error": None,
                    }
                )
            except Exception as exc:
                safe_error = redact_pii_text(str(exc))
                tool_result = {"ok": False, "error": safe_error}
                tool_events.append(
                    {
                        "tool_name": tool_name,
                        "tool_args_hash": None,
                        "tool_status": "error",
                        "latency_ms": 0,
                        "crm_provider": None,
                        "source_channel": source_channel,
                        "user_external_id": mask_external_id(user_external_id),
                        "ok": False,
                        "idempotent_replay": False,
                        "idempotency_key": None,
                        "error": safe_error,
                    }
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        if tool_calls and iteration < max_tool_iterations - 1:
            follow_up = await ai_client.chat.completions.create(
                model=generation_model,
                messages=messages,
                temperature=0.4,
            )
            follow_text = (follow_up.choices[0].message.content or "").strip()
            if follow_text:
                answer = follow_text

    if not answer:
        if last_credentials_payload:
            answer = (
                "Вот данные для входа в личный кабинет:\n"
                f"Сайт: {last_credentials_payload.get('website_url', '')}\n"
                f"Логин: {last_credentials_payload.get('login_email', '')}\n"
                f"Пароль: {last_credentials_payload.get('temp_password', '')}"
            )
        elif any(e.get("tool_status") == "edited" for e in tool_events):
            answer = "Готово, посмотрите сайт ещё раз — правки уже на месте."
        elif any(e.get("tool_status") in {"credentials_ready", "already_sent"} for e in tool_events):
            answer = "Данные для входа готовы — напишите, если что-то не откроется."
        else:
            answer = "Спасибо за ответ! Если хотите — могу выслать доступ в личный кабинет или внести правки в демо-сайт."

    return TemplateExecutionResult(answer=answer, sources=[], tool_events=tool_events)
