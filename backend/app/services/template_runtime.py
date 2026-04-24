"""Unified template runtime for agent responses."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import AgentAnalyticsMessage, AgentCrmConnection
from ..utils.crypto import decrypt_crm_credentials
from ..utils.pii import mask_external_id, redact_pii_text
from .ai_authoring import ai_client, generate_answer_with_context
from .crm import build_provider
from .crm.tool_registry import CRMNeedsConfirmationError, CRMToolRegistry
from .sales.tool_registry import SalesNeedsConfirmationError, SalesToolRegistry
from .sales.fsm import SalesFSMError, get_sales_fsm_service
from ..qdrant.search_service import search_knowledge_base

logger = logging.getLogger(__name__)


@dataclass
class TemplateExecutionResult:
    answer: str
    sources: list[str]
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    fallback_to_text: bool = False
    fallback_reason: str | None = None


class TemplateRuntimeService:
    """Executes agent templates through a single entrypoint."""

    @staticmethod
    def _is_userbot_channel(source_channel: str) -> bool:
        normalized = (source_channel or "").strip().lower()
        return normalized in {"telegram_userbot", "whatsapp_userbot"}

    async def execute(
        self,
        *,
        template_type: str | None,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        agent_id: int | None = None,
        user_external_id: str | None = None,
        template_config: dict[str, Any] | None = None,
        source_channel: str | None = None,
    ) -> TemplateExecutionResult:
        normalized = (template_type or "qa").strip().lower()
        if normalized == "function_calling":
            normalized = "crm_admin"
        if normalized == "crm_admin":
            crm_result = await self._execute_crm_admin(
                prompt=prompt,
                user_message=user_message,
                agent_id=agent_id,
                user_external_id=user_external_id,
                template_config=template_config or {},
                source_channel=source_channel or "telegram",
            )
            if crm_result is not None:
                return crm_result
            logger.warning("crm_admin runtime fallback to qa strategy")
            qa_result = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
            )
            qa_result.fallback_to_text = True
            qa_result.fallback_reason = "crm_runtime_unavailable"
            return qa_result

        if normalized == "sales_manager":
            return await self._execute_sales_manager(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                template_config=template_config or {},
                source_channel=source_channel or "telegram",
                user_external_id=user_external_id,
                agent_id=agent_id,
            )

        if normalized in {"qa", "lead_generation", "content_factory"}:
            return await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
            )

        # Unknown template types should not break runtime.
        logger.warning("Unknown template_type=%s, fallback to qa strategy", normalized)
        return await self._execute_qa_like(
            prompt=prompt,
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
        )

    async def _execute_crm_admin(
        self,
        *,
        prompt: str,
        user_message: str,
        agent_id: int | None,
        user_external_id: str | None,
        template_config: dict[str, Any],
        source_channel: str,
    ) -> TemplateExecutionResult | None:
        if not agent_id:
            return None

        crm_provider_name = str(template_config.get("crm_provider") or "amocrm").strip().lower()
        allowed_tools_raw = template_config.get("allowed_tools")
        allowed_tools = allowed_tools_raw if isinstance(allowed_tools_raw, list) else None
        confirmation_policy = str(template_config.get("confirmation_policy") or "confirm_risky").strip().lower()

        connection = await self._get_active_crm_connection(agent_id=agent_id, provider=crm_provider_name)
        if connection is None:
            return None

        try:
            decrypted_bundle, _ = decrypt_crm_credentials(connection.encrypted_credentials)
            bundle = json.loads(decrypted_bundle)
            provider = build_provider(
                crm_provider_name,
                base_url=str(bundle.get("base_url") or ""),
                access_token=str(bundle.get("access_token") or ""),
            )
        except Exception:
            logger.exception("Failed to initialize CRM provider for agent_id=%s", agent_id)
            return TemplateExecutionResult(
                answer="Не удалось инициализировать подключение CRM. Проверьте настройки интеграции.",
                sources=[],
            )

        registry = CRMToolRegistry(
            provider=provider,
            allowed_tools=allowed_tools,
            confirmation_policy=confirmation_policy,
            user_message=user_message,
            agent_id=agent_id,
            user_external_id=user_external_id,
        )
        llm_tools = registry.tools_for_llm()
        if not llm_tools:
            return None

        chat_history = await self._load_recent_channel_history(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )

        system_prompt = (
            f"{prompt}\n\n"
            "Ты CRM-администратор. Если нужно действие в CRM — используй function tools. "
            "Не выдумывай результаты CRM операций: опирайся только на ответы tools. "
            "Отвечай только чистым текстом, без markdown."
        ).strip()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})
        tool_events: list[dict[str, Any]] = []

        for _ in range(4):
            completion = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.2,
            )
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
            content = (message.content or "").strip()

            if not tool_calls:
                cleaned = content.replace("#", "").replace("*", "").strip()
                if not cleaned:
                    cleaned = "Не удалось сформировать ответ. Уточните запрос."
                return TemplateExecutionResult(answer=cleaned, sources=[], tool_events=tool_events)

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
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": tool_result.get("tool_args_hash"),
                            "tool_status": tool_result.get("tool_status", "success"),
                            "latency_ms": int(tool_result.get("latency_ms") or 0),
                            "crm_provider": tool_result.get("crm_provider") or crm_provider_name,
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": bool(tool_result.get("ok")),
                            "idempotent_replay": bool(tool_result.get("idempotent_replay")),
                            "idempotency_key": tool_result.get("idempotency_key"),
                            "error": None,
                        }
                    )
                except CRMNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "confirmation_required",
                            "latency_ms": 0,
                            "crm_provider": crm_provider_name,
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": False,
                            "idempotent_replay": False,
                            "idempotency_key": None,
                            "error": safe_error,
                        }
                    )
                    return TemplateExecutionResult(answer=safe_error, sources=[], tool_events=tool_events)
                except Exception as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {"ok": False, "error": safe_error}
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "error",
                            "latency_ms": 0,
                            "crm_provider": crm_provider_name,
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

        return TemplateExecutionResult(
            answer="Не удалось завершить CRM-операцию за допустимое число шагов. Попробуйте уточнить запрос.",
            sources=[],
            tool_events=tool_events,
        )

    async def _get_active_crm_connection(self, *, agent_id: int, provider: str) -> AgentCrmConnection | None:
        async with async_session_maker() as session:
            async with session.begin():
                return await session.scalar(
                    select(AgentCrmConnection).where(
                        AgentCrmConnection.agent_id == agent_id,
                        AgentCrmConnection.provider == provider,
                        AgentCrmConnection.is_active.is_(True),
                    )
                )

    async def _load_recent_channel_history(
        self,
        *,
        agent_id: int,
        user_external_id: str | None,
        source_channel: str,
    ) -> list[dict[str, Any]]:
        uid = (user_external_id or "").strip()
        channel = (source_channel or "").strip().lower()
        if not uid or not channel:
            return []

        async with async_session_maker() as session:
            async with session.begin():
                rows = (
                    (
                        await session.execute(
                            select(
                                AgentAnalyticsMessage.role,
                                AgentAnalyticsMessage.message_text,
                            )
                            .where(
                                AgentAnalyticsMessage.agent_id == agent_id,
                                AgentAnalyticsMessage.user_external_id == uid,
                                AgentAnalyticsMessage.channel == channel,
                                AgentAnalyticsMessage.role.in_(["user", "agent"]),
                            )
                            .order_by(AgentAnalyticsMessage.created_at.desc())
                            .limit(8)
                        )
                    )
                    .mappings()
                    .all()
                )

        history: list[dict[str, Any]] = []
        for row in reversed(rows):
            role = (row.get("role") or "").strip().lower()
            text = (row.get("message_text") or "").strip()
            if role not in {"user", "agent"} or not text:
                continue
            history.append({"role": "assistant" if role == "agent" else "user", "content": text})
        return history

    async def _execute_qa_like(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
    ) -> TemplateExecutionResult:
        context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
        context_list = context if isinstance(context, list) else []
        answer = await generate_answer_with_context(user_message, context_list, prompt)

        sources: list[str] = []
        for item in context_list:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            if source and source not in sources:
                sources.append(str(source))

        return TemplateExecutionResult(answer=answer, sources=sources)

    async def _execute_sales_manager(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        template_config: dict[str, Any],
        source_channel: str,
        user_external_id: str | None,
        agent_id: int | None = None,
    ) -> TemplateExecutionResult:
        contact_key = self._resolve_sales_contact_key(template_config=template_config)
        if agent_id and user_external_id:
            await self._ensure_sales_contact_exists(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
            )
        qualification = await self.qualify_message(
            prompt=prompt,
            user_message=user_message,
            template_config=template_config,
        )
        intent = qualification.get("intent", "unsure")
        confidence = float(qualification.get("confidence") or 0.0)
        min_confidence = float(template_config.get("min_confidence") or 0.75)

        if intent in {"do_not_contact", "non_target"}:
            if agent_id and user_external_id:
                await self._transition_sales_state_safe(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    to_state="SKIPPED",
                    reason=f"intent:{intent}",
                    metadata={"qualification": qualification},
                )
            return self.emit_action(
                template_config=template_config,
                qualification=qualification,
                composed_dm=None,
                sources=[],
                source_channel=source_channel,
                user_external_id=user_external_id,
            )
        if confidence < min_confidence:
            if self._is_userbot_channel(source_channel):
                qa_result = await self._execute_qa_like(
                    prompt=prompt,
                    user_message=user_message,
                    knowledge_scope_id=knowledge_scope_id,
                )
                qa_result.fallback_to_text = True
                qa_result.fallback_reason = "sales_low_confidence_fallback"
                return qa_result
            if agent_id and user_external_id:
                await self._transition_sales_state_safe(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    to_state="SKIPPED",
                    reason="low_confidence",
                    metadata={"qualification": qualification},
                )
            return self.emit_action(
                template_config=template_config,
                qualification=qualification,
                composed_dm=None,
                sources=[],
                source_channel=source_channel,
                user_external_id=user_external_id,
            )

        if agent_id and user_external_id:
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
                to_state="QUALIFIED",
                reason="qualified",
                metadata={"qualification": qualification},
            )
        context_list, sources = await self.retrieve_offer_context(
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
        )
        composed_dm = await self.compose_dm(
            prompt=prompt,
            user_message=user_message,
            qualification=qualification,
            context_list=context_list,
            template_config=template_config,
        )
        tool_driven = await self._execute_sales_tools(
            prompt=prompt,
            user_message=user_message,
            qualification=qualification,
            composed_dm=composed_dm,
            template_config=template_config,
            source_channel=source_channel,
            user_external_id=user_external_id,
            agent_id=agent_id,
            sources=sources,
        )
        if tool_driven is not None:
            if agent_id and user_external_id and tool_driven.tool_events:
                await self._apply_fsm_from_tool_events(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    tool_events=tool_driven.tool_events,
                )
            return tool_driven
        result = self.emit_action(
            template_config=template_config,
            qualification=qualification,
            composed_dm=composed_dm,
            sources=sources,
            source_channel=source_channel,
            user_external_id=user_external_id,
        )
        if agent_id and user_external_id and result.tool_events:
            await self._apply_fsm_from_tool_events(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
                tool_events=result.tool_events,
            )
        return result

    async def _execute_sales_tools(
        self,
        *,
        prompt: str,
        user_message: str,
        qualification: dict[str, Any],
        composed_dm: str,
        template_config: dict[str, Any],
        source_channel: str,
        user_external_id: str | None,
        agent_id: int | None,
        sources: list[str],
    ) -> TemplateExecutionResult | None:
        allowed_tools_raw = template_config.get("allowed_tools")
        allowed_tools = allowed_tools_raw if isinstance(allowed_tools_raw, list) else None
        confirmation_policy = str(template_config.get("confirmation_policy") or "confirm_risky").strip().lower()
        mode = str(template_config.get("mode") or "draft_only").strip().lower()
        registry = SalesToolRegistry(
            allowed_tools=allowed_tools,
            confirmation_policy=confirmation_policy,
            user_message=user_message,
            agent_id=agent_id,
            user_external_id=user_external_id,
            mode=mode,
        )
        llm_tools = registry.tools_for_llm()
        if not llm_tools:
            return None

        generation_model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        system_prompt = (
            f"{prompt}\n\n"
            "Ты управляешь действиями sales-агента через function tools. "
            "Не пиши свободный ответ вместо действия, выбери tool call. "
            "Если лид нецелевой — используй skip_lead."
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Классификация: {json.dumps(qualification, ensure_ascii=False)}\n"
                    f"Черновик outreach: {composed_dm}\n"
                    f"Канал: {source_channel}"
                ),
            },
        ]
        tool_events: list[dict[str, Any]] = []

        for _ in range(3):
            completion = await ai_client.chat.completions.create(
                model=generation_model,
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.2,
            )
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
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
                except SalesNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {"ok": False, "error": safe_error}
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "confirmation_required",
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
            if tool_events:
                break

        if not tool_events:
            return None
        last_status = str(tool_events[-1].get("tool_status") or "")
        if last_status == "sent_auto":
            answer = f"Auto outreach готов к отправке:\n{composed_dm}"
        elif last_status == "draft_requires_review":
            answer = f"Требуется подтверждение владельца. Черновик:\n{composed_dm}"
        elif last_status == "confirmation_required":
            answer = "Для выполнения действия требуется явное подтверждение пользователя."
        elif last_status.startswith("skipped_"):
            answer = "Лид пропущен согласно policy."
        else:
            answer = "Действие sales-агента выполнено через tools."
        return TemplateExecutionResult(answer=answer, sources=sources, tool_events=tool_events)

    async def qualify_message(
        self,
        *,
        prompt: str,
        user_message: str,
        template_config: dict[str, Any],
    ) -> dict[str, Any]:
        model = str(template_config.get("qualification_model") or "deepseek-chat").strip() or "deepseek-chat"
        instruction = (
            f"{prompt}\n\n"
            "Ты классификатор для sales outreach. Верни только JSON объект с полями: "
            "intent, confidence, reason. "
            "intent строго один из: target_hot, target_warm, non_target, do_not_contact, unsure. "
            "confidence от 0 до 1."
        )
        completion = await ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
        )
        raw = (completion.choices[0].message.content or "").strip()
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(raw)
        except Exception:
            logger.warning("sales_manager classify parse failed, fallback to unsure")
            return {"intent": "unsure", "confidence": 0.0, "reason": "invalid_classifier_json"}

        intent = str(parsed.get("intent") or "unsure").strip().lower()
        allowed_intents = {"target_hot", "target_warm", "non_target", "do_not_contact", "unsure"}
        if intent not in allowed_intents:
            intent = "unsure"
        try:
            confidence = float(parsed.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        reason = str(parsed.get("reason") or "").strip()[:500]
        return {"intent": intent, "confidence": confidence, "reason": reason}

    async def retrieve_offer_context(
        self,
        *,
        user_message: str,
        knowledge_scope_id: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
        context_list = context if isinstance(context, list) else []
        normalized_context = [item for item in context_list if isinstance(item, dict)]
        sources: list[str] = []
        for item in normalized_context:
            source = item.get("source")
            if source and source not in sources:
                sources.append(str(source))
        return normalized_context, sources

    async def compose_dm(
        self,
        *,
        prompt: str,
        user_message: str,
        qualification: dict[str, Any],
        context_list: list[dict[str, Any]],
        template_config: dict[str, Any],
    ) -> str:
        model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        context_parts = [
            f"Источник: {c.get('source', 'Unknown')}\nТекст: {c.get('text', '')}"
            for c in context_list
        ]
        context_text = "\n\n---\n\n".join(context_parts) if context_parts else "Контекст не найден."
        system_prompt = (
            f"{prompt}\n\n"
            "Ты пишешь короткое и уместное первое сообщение в личку от менеджера продаж. "
            "Тон: уважительный, без давления, без спама. "
            "Верни только чистый текст, без markdown."
        )
        user_prompt = (
            f"Исходное сообщение в чате:\n{user_message}\n\n"
            f"Классификация:\n{json.dumps(qualification, ensure_ascii=False)}\n\n"
            f"Контекст продукта (RAG):\n{context_text}\n\n"
            "Сформируй короткий персонализированный outreach в 1-3 предложения."
        )
        completion = await ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        content = (completion.choices[0].message.content or "").strip()
        cleaned = content.replace("#", "").replace("*", "").strip()
        return cleaned[:1200]

    def emit_action(
        self,
        *,
        template_config: dict[str, Any],
        qualification: dict[str, Any],
        composed_dm: str | None,
        sources: list[str],
        source_channel: str,
        user_external_id: str | None,
    ) -> TemplateExecutionResult:
        intent = str(qualification.get("intent") or "unsure").strip().lower()
        confidence = float(qualification.get("confidence") or 0.0)
        min_confidence = float(template_config.get("min_confidence") or 0.75)
        mode = str(template_config.get("mode") or "draft_only").strip().lower()
        reason = str(qualification.get("reason") or "").strip()

        if intent == "do_not_contact":
            reason_code = "skipped_do_not_contact"
            answer = "Лид пропущен: контакт запрещен по политике."
        elif intent == "non_target":
            reason_code = "skipped_non_target"
            answer = "Лид пропущен: сообщение нецелевое."
        elif confidence < min_confidence:
            reason_code = "skipped_low_confidence"
            answer = "Лид пропущен: низкая уверенность классификатора."
        elif not composed_dm:
            reason_code = "draft_requires_review"
            answer = "Черновик не сформирован, требуется ручная проверка."
        elif mode == "auto":
            reason_code = "sent_auto"
            answer = f"Auto outreach готов к отправке:\n{composed_dm}"
        elif mode == "semi_auto":
            reason_code = "draft_requires_review"
            answer = f"Требуется подтверждение владельца. Черновик:\n{composed_dm}"
        else:
            reason_code = "draft_requires_review"
            answer = f"Черновик outreach (режим draft_only):\n{composed_dm}"

        event = {
            "tool_name": "sales_outreach_action",
            "tool_args_hash": None,
            "tool_status": reason_code,
            "latency_ms": 0,
            "crm_provider": None,
            "source_channel": source_channel,
            "user_external_id": mask_external_id(user_external_id),
            "ok": reason_code in {"sent_auto", "draft_requires_review"},
            "idempotent_replay": False,
            "idempotency_key": None,
            "error": None if reason_code not in {"skipped_do_not_contact", "skipped_non_target", "skipped_low_confidence"} else reason or reason_code,
        }
        return TemplateExecutionResult(answer=answer, sources=sources, tool_events=[event])

    @staticmethod
    def _resolve_sales_contact_key(*, template_config: dict[str, Any]) -> str:
        source_chat_id = template_config.get("source_chat_id")
        value = str(source_chat_id or "global").strip()
        return value or "global"

    async def _ensure_sales_contact_exists(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
    ) -> None:
        try:
            await get_sales_fsm_service().get_or_create_contact(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
            )
        except Exception:
            logger.exception("sales_manager FSM get_or_create failed")

    async def _transition_sales_state_safe(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
        to_state: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            await get_sales_fsm_service().transition_contact(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
                to_state=to_state,
                reason=reason,
                metadata=metadata,
            )
        except SalesFSMError:
            logger.warning("sales_manager FSM illegal transition ignored: %s", to_state)
        except Exception:
            logger.exception("sales_manager FSM transition failed: %s", to_state)

    async def _apply_fsm_from_tool_events(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
        tool_events: list[dict[str, Any]],
    ) -> None:
        if not tool_events:
            return
        status = str(tool_events[-1].get("tool_status") or "").strip().lower()
        if status == "draft_requires_review":
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
                to_state="QUEUED",
                reason=status,
            )
        elif status == "sent_auto":
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
                to_state="QUEUED",
                reason="auto_queue",
            )
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
                to_state="SENT",
                reason=status,
            )
        elif status.startswith("skipped_"):
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=source_chat_id,
                to_state="SKIPPED",
                reason=status,
            )


_runtime_service: TemplateRuntimeService | None = None


def get_template_runtime() -> TemplateRuntimeService:
    global _runtime_service
    if _runtime_service is None:
        _runtime_service = TemplateRuntimeService()
    return _runtime_service
