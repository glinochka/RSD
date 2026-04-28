"""Unified template runtime for agent responses."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import AgentAnalyticsMessage, AgentCrmConnection, AgentSalesContact
from ..utils.crypto import decrypt_crm_credentials
from ..utils.pii import mask_external_id, redact_pii_text
from .admin_booking import AdminBookingNeedsConfirmationError, AdminBookingToolRegistry
from .ai_authoring import ai_client, generate_answer_with_context
from .content_factory_runtime import get_content_factory_orchestrator
from .crm import build_provider
from .crm.tool_registry import CRMNeedsConfirmationError, CRMToolRegistry
from .sales.tool_registry import SalesNeedsConfirmationError, SalesToolRegistry
from .sales.fsm import SalesFSMError, get_sales_fsm_service
from ..qdrant.search_service import search_knowledge_base

logger = logging.getLogger(__name__)
MAX_CHAT_PORTRAIT_CHARS = 2000


@dataclass
class TemplateExecutionResult:
    answer: str
    sources: list[str]
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    fallback_to_text: bool = False
    fallback_reason: str | None = None
    requires_owner_handoff: bool = False
    owner_handoff_reason: str | None = None


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
        chat_portrait: str | None = None,
        runtime_context: dict[str, Any] | None = None,
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
                chat_portrait=chat_portrait,
            )
            if crm_result is not None:
                return crm_result
            logger.warning("crm_admin runtime fallback to qa strategy")
            qa_result = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                chat_portrait=chat_portrait,
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
                chat_portrait=chat_portrait,
                runtime_context=runtime_context or {},
            )

        if normalized == "content_factory":
            return await self._execute_content_factory(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                chat_portrait=chat_portrait,
            )

        if normalized == "qa":
            return await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                chat_portrait=chat_portrait,
                enable_owner_handoff=True,
            )

        if normalized == "lead_generation":
            return await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                chat_portrait=chat_portrait,
            )

        # Unknown template types should not break runtime.
        logger.warning("Unknown template_type=%s, fallback to qa strategy", normalized)
        return await self._execute_qa_like(
            prompt=prompt,
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
            chat_portrait=chat_portrait,
        )

    @staticmethod
    def _format_portrait_block(chat_portrait: str | None) -> str:
        portrait = (chat_portrait or "").strip()
        if not portrait:
            return ""
        return f"Портрет текущего клиента/чата:\n{portrait}"

    async def update_chat_portrait(
        self,
        *,
        agent_id: int | None,
        analytics_namespace_id: int | None = None,
        user_external_id: str | None,
        source_channel: str | None,
        user_message: str,
        base_prompt: str,
        template_config: dict[str, Any] | None = None,
    ) -> str:
        if not agent_id or not user_external_id or not source_channel:
            return ""
        text = (user_message or "").strip()
        if not text:
            return await self._load_chat_portrait(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
            )

        previous = await self._load_chat_portrait(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )
        cfg = template_config or {}
        model = str(
            cfg.get("portrait_model") or cfg.get("generation_model") or "deepseek-chat"
        ).strip() or "deepseek-chat"
        system_prompt = (
            "Ты модуль памяти клиента. Обнови портрет клиента/чата на основе нового сообщения. "
            "Портрет должен быть кратким, фактическим и полезным для будущих ответов ассистента. "
            "Включай: цели, интересы, ограничения, предпочтительный стиль общения, важные факты и текущий контекст. "
            "Не выдумывай данные, не добавляй markdown, верни только итоговый портрет."
        )
        if (base_prompt or "").strip():
            system_prompt = f"{base_prompt.strip()}\n\n{system_prompt}"
        user_prompt = (
            f"Текущий портрет:\n{previous or 'Портрет пока отсутствует.'}\n\n"
            f"Новое сообщение клиента:\n{text}\n\n"
            "Верни обновлённый портрет (до 2000 символов)."
        )
        try:
            completion = await ai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            updated = (completion.choices[0].message.content or "").replace("#", "").replace("*", "").strip()
            if not updated:
                return previous
            updated = updated[:MAX_CHAT_PORTRAIT_CHARS]
            if updated != previous:
                await self._save_chat_portrait(
                    agent_id=agent_id,
                    analytics_namespace_id=analytics_namespace_id or agent_id,
                    user_external_id=user_external_id,
                    source_channel=source_channel,
                    portrait=updated,
                )
            return updated
        except Exception:
            logger.exception("Failed to update chat portrait for agent_id=%s", agent_id)
            return previous

    async def _load_chat_portrait(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_channel: str,
    ) -> str:
        uid = (user_external_id or "").strip()
        channel = (source_channel or "").strip().lower()
        if not uid or not channel:
            return ""
        async with async_session_maker() as session:
            async with session.begin():
                row = (
                    (
                        await session.execute(
                            select(AgentAnalyticsMessage.message_text)
                            .where(
                                AgentAnalyticsMessage.agent_id == agent_id,
                                AgentAnalyticsMessage.user_external_id == uid,
                                AgentAnalyticsMessage.channel == channel,
                                AgentAnalyticsMessage.role == "portrait",
                            )
                            .order_by(AgentAnalyticsMessage.created_at.desc())
                            .limit(1)
                        )
                    )
                    .mappings()
                    .first()
                )
        if not row:
            return ""
        return str(row.get("message_text") or "").strip()[:MAX_CHAT_PORTRAIT_CHARS]

    async def _save_chat_portrait(
        self,
        *,
        agent_id: int,
        analytics_namespace_id: int,
        user_external_id: str,
        source_channel: str,
        portrait: str,
    ) -> None:
        async with async_session_maker() as session:
            async with session.begin():
                session.add(
                    AgentAnalyticsMessage(
                        agent_id=agent_id,
                        bot_id=analytics_namespace_id,
                        role="portrait",
                        channel=(source_channel or "").strip().lower(),
                        user_external_id=(user_external_id or "").strip(),
                        user_display_name=None,
                        telegram_peer_access_hash=None,
                        tool_name="chat_portrait_update",
                        tool_args_hash=None,
                        tool_status="success",
                        latency_ms=0,
                        crm_provider=None,
                        message_text=(portrait or "").strip()[:MAX_CHAT_PORTRAIT_CHARS],
                    )
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
        chat_portrait: str | None = None,
    ) -> TemplateExecutionResult | None:
        if not agent_id:
            return None

        domain_type = str(template_config.get("domain_type") or "beauty_salon").strip().lower()
        if domain_type not in {"beauty_salon", "dental_clinic"}:
            domain_type = "beauty_salon"
        booking_backend = str(template_config.get("booking_backend") or "auto").strip().lower()
        if booking_backend not in {"local", "crm", "auto"}:
            booking_backend = "auto"
        crm_provider_name = str(template_config.get("crm_provider") or "amocrm").strip().lower()
        confirmation_policy = str(template_config.get("confirmation_policy") or "confirm_risky").strip().lower()
        allowed_crm_tools_raw = template_config.get("allowed_tools")
        allowed_crm_tools = allowed_crm_tools_raw if isinstance(allowed_crm_tools_raw, list) else None
        allowed_booking_tools_raw = template_config.get("allowed_booking_tools")
        allowed_booking_tools = (
            allowed_booking_tools_raw if isinstance(allowed_booking_tools_raw, list) else None
        )

        booking_registry = AdminBookingToolRegistry(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
            confirmation_policy=confirmation_policy,
            user_message=user_message,
            allowed_tools=allowed_booking_tools,
        )
        booking_llm_tools = booking_registry.tools_for_llm()

        crm_registry: CRMToolRegistry | None = None
        crm_tool_names: set[str] = set()
        connection = await self._get_active_crm_connection(agent_id=agent_id, provider=crm_provider_name)
        if connection is not None:
            try:
                decrypted_bundle, _ = decrypt_crm_credentials(connection.encrypted_credentials)
                bundle = json.loads(decrypted_bundle)
                provider = build_provider(
                    crm_provider_name,
                    base_url=str(bundle.get("base_url") or ""),
                    access_token=str(bundle.get("access_token") or ""),
                )
                crm_registry = CRMToolRegistry(
                    provider=provider,
                    allowed_tools=allowed_crm_tools,
                    confirmation_policy=confirmation_policy,
                    user_message=user_message,
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                )
                crm_tool_names = {
                    str(item.get("function", {}).get("name") or "")
                    for item in crm_registry.tools_for_llm()
                    if isinstance(item, dict)
                }
            except Exception:
                logger.exception("Failed to initialize CRM provider for agent_id=%s", agent_id)

        llm_tools: list[dict[str, Any]] = []
        llm_tools.extend(booking_llm_tools)
        if crm_registry is not None:
            llm_tools.extend(crm_registry.tools_for_llm())
        if not llm_tools:
            return None

        chat_history = await self._load_recent_channel_history(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )

        portrait_block = self._format_portrait_block(chat_portrait)
        domain_instruction = self._crm_admin_domain_instruction(domain_type=domain_type)
        backend_instruction = self._crm_admin_backend_instruction(
            booking_backend=booking_backend,
            crm_connected=connection is not None,
            crm_provider_name=crm_provider_name,
        )
        system_prompt = (
            f"{prompt}\n\n"
            "Ты AI-администратор записи. Работай через function tools для операций расписания и записи. "
            "Не выдумывай результаты операций: опирайся только на ответы tools. "
            "Если не хватает параметров для tool call — задай уточняющий вопрос. "
            "Отвечай только чистым текстом, без markdown.\n\n"
            f"{domain_instruction}\n{backend_instruction}"
        ).strip()
        if portrait_block:
            system_prompt = f"{system_prompt}\n\n{portrait_block}"

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
                    if booking_registry.has_tool(tool_name):
                        tool_result = await booking_registry.execute_tool(tool_name, raw_args)
                    elif crm_registry is not None and tool_name in crm_tool_names:
                        tool_result = await crm_registry.execute_tool(tool_name, raw_args)
                    else:
                        raise RuntimeError(f"Tool '{tool_name}' is not available in current runtime")
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": tool_result.get("tool_args_hash"),
                            "tool_status": tool_result.get("tool_status", "success"),
                            "latency_ms": int(tool_result.get("latency_ms") or 0),
                            "crm_provider": tool_result.get("crm_provider"),
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": bool(tool_result.get("ok")),
                            "idempotent_replay": bool(tool_result.get("idempotent_replay")),
                            "idempotency_key": tool_result.get("idempotency_key"),
                            "error": None,
                        }
                    )
                except AdminBookingNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "confirmation_required",
                            "latency_ms": 0,
                            "crm_provider": "booking",
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": False,
                            "idempotent_replay": False,
                            "idempotency_key": None,
                            "error": safe_error,
                        }
                    )
                    return TemplateExecutionResult(answer=safe_error, sources=[], tool_events=tool_events)
                except CRMNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "confirmation_required",
                            "latency_ms": 0,
                            "crm_provider": crm_provider_name if crm_registry is not None else None,
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

        return TemplateExecutionResult(
            answer="Не удалось завершить CRM-операцию за допустимое число шагов. Попробуйте уточнить запрос.",
            sources=[],
            tool_events=tool_events,
        )

    @staticmethod
    def _crm_admin_domain_instruction(*, domain_type: str) -> str:
        if domain_type == "dental_clinic":
            return (
                "Предметная область: стоматологическая клиника. "
                "Используй терминологию врач/кабинет/процедура и уточняй длительность приема."
            )
        return (
            "Предметная область: салон красоты. "
            "Используй терминологию мастер/кресло/услуга и уточняй предпочтения по времени."
        )

    @staticmethod
    def _crm_admin_backend_instruction(
        *,
        booking_backend: str,
        crm_connected: bool,
        crm_provider_name: str,
    ) -> str:
        if booking_backend == "local":
            return "Backend бронирования: local (локальная доменная БД записи)."
        if booking_backend == "crm":
            if crm_connected:
                return (
                    f"Backend бронирования: crm (синхронизация через CRM-провайдер {crm_provider_name})."
                )
            return "Backend бронирования: crm, но CRM не подключена; используй local fallback для записи."
        if crm_connected:
            return f"Backend бронирования: auto (сейчас активен CRM-провайдер {crm_provider_name})."
        return "Backend бронирования: auto (CRM не подключена, используй local backend)."

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
        try:
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
        except Exception:
            logger.warning("Failed to load recent channel history for sales context")
            return []

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
        chat_portrait: str | None = None,
        enable_owner_handoff: bool = False,
    ) -> TemplateExecutionResult:
        context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
        context_list = context if isinstance(context, list) else []
        portrait_block = self._format_portrait_block(chat_portrait)
        effective_prompt = prompt.strip()
        if enable_owner_handoff:
            effective_prompt = (
                f"{effective_prompt}\n\n"
                "Если нет четкого ответа на вопрос из доступного контекста "
                "или требуется вмешательство человека, начни ответ строго с маркера "
                "[OWNER_HANDOFF], кратко укажи причину и сообщи пользователю, что запрос передан владельцу."
            ).strip()
        if portrait_block:
            effective_prompt = f"{effective_prompt}\n\n{portrait_block}" if effective_prompt else portrait_block
        answer = await generate_answer_with_context(user_message, context_list, effective_prompt)
        requires_owner_handoff = False
        owner_handoff_reason: str | None = None
        if enable_owner_handoff:
            answer, requires_owner_handoff, owner_handoff_reason = self._extract_owner_handoff(answer)

        sources: list[str] = []
        for item in context_list:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            if source and source not in sources:
                sources.append(str(source))

        return TemplateExecutionResult(
            answer=answer,
            sources=sources,
            requires_owner_handoff=requires_owner_handoff,
            owner_handoff_reason=owner_handoff_reason,
        )

    @staticmethod
    def _extract_owner_handoff(answer: str) -> tuple[str, bool, str | None]:
        text = (answer or "").strip()
        if not text:
            return text, False, None

        match = re.match(r"^\[OWNER_HANDOFF\]\s*(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            reason_text = (match.group(1) or "").strip()
            first_sentence = reason_text.split("\n", 1)[0][:300] if reason_text else "owner_handoff_requested"
            return reason_text or "Передаю запрос владельцу для ручной обработки.", True, first_sentence

        uncertainty_markers = (
            "не хватает данных",
            "недостаточно данных",
            "нет точной информации",
            "не могу точно ответить",
            "нужен человек",
            "передам владельцу",
            "обратитесь к владельцу",
            "требуется вмешательство",
        )
        lowered = text.lower()
        for marker in uncertainty_markers:
            if marker in lowered:
                return text, True, marker
        return text, False, None

    async def _execute_content_factory(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        chat_portrait: str | None = None,
    ) -> TemplateExecutionResult:
        decision = get_content_factory_orchestrator().route_incoming_message(user_message=user_message)
        if decision.fallback_to_text_runtime:
            fallback = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                chat_portrait=chat_portrait,
            )
            fallback.fallback_to_text = True
            fallback.fallback_reason = decision.fallback_reason or "content_factory_runtime_fallback"
            return fallback

        return TemplateExecutionResult(answer=decision.answer, sources=[])

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
        chat_portrait: str | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> TemplateExecutionResult:
        runtime_context = runtime_context or {}
        contact_key = self._resolve_sales_contact_key(template_config=template_config)
        current_sales_state = "DISCOVERED"
        if agent_id and user_external_id:
            await self._ensure_sales_contact_exists(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
            )
            current_sales_state = await self._load_sales_contact_state(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
            )
        recent_history: list[dict[str, Any]] = []
        if agent_id and user_external_id:
            recent_history = await self._load_recent_channel_history(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
            )
        lead_initiated_private_dialog = bool(runtime_context.get("lead_initiated_private_dialog"))
        if lead_initiated_private_dialog:
            qualification = {
                "decision": "engage",
                "intent": "target_hot",
                "confidence": 1.0,
                "reason": "lead_initiated_private_dialog",
                "lead_temperature": "hot",
                "stage_hint": "discovery",
                "handoff_ready": False,
            }
        else:
            qualification = await self.qualify_message(
                prompt=prompt,
                user_message=user_message,
                template_config=template_config,
                chat_portrait=chat_portrait,
                current_sales_state=current_sales_state,
                recent_history=recent_history,
            )
        intent = qualification.get("intent", "unsure")
        decision = str(qualification.get("decision") or "ignore").strip().lower()
        confidence = float(qualification.get("confidence") or 0.0)
        min_confidence = float(template_config.get("min_confidence") or 0.75)

        if intent in {"do_not_contact", "non_target"} or decision == "ignore":
            skip_reason = f"intent:{intent}" if intent in {"do_not_contact", "non_target"} else "llm_ignore"
            if (
                agent_id
                and user_external_id
                and current_sales_state == "SENT"
                and intent in {"do_not_contact", "non_target"}
            ):
                await self._transition_sales_state_safe(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    to_state="REPLIED_NEGATIVE",
                    reason="reply_negative_signal",
                    metadata={"qualification": qualification},
                )
            if agent_id and user_external_id:
                await self._transition_sales_state_safe(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    to_state="SKIPPED",
                    reason=skip_reason,
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
            low_confidence_fallback_to_qa = bool(template_config.get("low_confidence_fallback_to_qa"))
            if self._is_userbot_channel(source_channel) and low_confidence_fallback_to_qa:
                qa_result = await self._execute_qa_like(
                    prompt=prompt,
                    user_message=user_message,
                    knowledge_scope_id=knowledge_scope_id,
                    chat_portrait=chat_portrait,
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

        if agent_id and user_external_id and current_sales_state == "SENT" and decision == "engage":
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
                to_state="REPLIED_POSITIVE",
                reason="reply_engaged",
                metadata={"qualification": qualification},
            )
            current_sales_state = "REPLIED_POSITIVE"

        if agent_id and user_external_id and current_sales_state == "DISCOVERED":
            await self._transition_sales_state_safe(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
                to_state="QUALIFIED",
                reason="qualified",
                metadata={"qualification": qualification},
            )
            current_sales_state = "QUALIFIED"
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
            chat_portrait=chat_portrait,
            current_sales_state=current_sales_state,
            recent_history=recent_history,
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
            chat_portrait=chat_portrait,
        )
        if tool_driven is not None:
            if agent_id and user_external_id and tool_driven.tool_events:
                await self._apply_fsm_from_tool_events(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    tool_events=tool_driven.tool_events,
                )
                if bool(qualification.get("handoff_ready")) and current_sales_state == "REPLIED_POSITIVE":
                    await self._transition_sales_state_safe(
                        agent_id=agent_id,
                        user_external_id=user_external_id,
                        source_chat_id=contact_key,
                        to_state="HANDOFF_CRM",
                        reason="llm_handoff_ready",
                        metadata={"qualification": qualification},
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
            if bool(qualification.get("handoff_ready")) and current_sales_state == "REPLIED_POSITIVE":
                await self._transition_sales_state_safe(
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_chat_id=contact_key,
                    to_state="HANDOFF_CRM",
                    reason="llm_handoff_ready",
                    metadata={"qualification": qualification},
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
        chat_portrait: str | None = None,
    ) -> TemplateExecutionResult | None:
        allowed_tools_raw = template_config.get("allowed_tools")
        allowed_tools = allowed_tools_raw if isinstance(allowed_tools_raw, list) else None
        # Sales workflow is fully autonomous: no interactive confirmations in runtime.
        confirmation_policy = "never_confirm"
        mode = "auto"
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
        portrait_block = self._format_portrait_block(chat_portrait)
        system_prompt = (
            f"{prompt}\n\n"
            "Ты управляешь действиями sales-агента через function tools. "
            "Не пиши свободный ответ вместо действия, выбери tool call. "
            "Если лид нецелевой — используй skip_lead."
        )
        if portrait_block:
            system_prompt = f"{system_prompt}\n\n{portrait_block}"
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
            answer = composed_dm
        return TemplateExecutionResult(answer=answer, sources=sources, tool_events=tool_events)

    async def qualify_message(
        self,
        *,
        prompt: str,
        user_message: str,
        template_config: dict[str, Any],
        chat_portrait: str | None = None,
        current_sales_state: str = "DISCOVERED",
        recent_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        model = str(template_config.get("qualification_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        history_block = self._format_sales_history(recent_history)
        portrait_block = self._format_portrait_block(chat_portrait)
        instruction = (
            f"{prompt}\n\n"
            "Ты модуль pre-sales скрининга с function-calling. "
            f"Продукт: {product_name}. Категория: {offer_type}. "
            "Твоя задача: понять, стоит ли писать человеку в личку и как вести следующий шаг продаж.\n"
            "Выбирай ровно один function call:\n"
            "1) engage_lead - если нужно продолжать диалог/продажу.\n"
            "2) ignore_lead - если лид нецелевой или писать не нужно.\n"
            "Стадия продажи: "
            f"{(current_sales_state or 'DISCOVERED').strip().upper()}.\n"
            "Учитывай этап воронки, контекст и историю взаимодействия."
        )
        if portrait_block:
            instruction = f"{instruction}\n\n{portrait_block}"
        if usp:
            instruction = f"{instruction}\n\nКлючевое УТП:\n{usp}"
        if history_block:
            instruction = f"{instruction}\n\nНедавняя история диалога:\n{history_block}"
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "engage_lead",
                    "description": "Продолжить диалог с лидом и продажу.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {"type": "string", "enum": ["target_hot", "target_warm", "unsure"]},
                            "confidence": {"type": "number"},
                            "reason": {"type": "string"},
                            "lead_temperature": {"type": "string", "enum": ["cold", "warm", "hot"]},
                            "stage_hint": {
                                "type": "string",
                                "enum": ["first_touch", "discovery", "value_pitch", "handoff"],
                            },
                            "handoff_ready": {"type": "boolean"},
                        },
                        "required": ["intent", "confidence", "reason"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ignore_lead",
                    "description": "Не писать пользователю и пропустить лид.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {"type": "string", "enum": ["non_target", "do_not_contact", "unsure"]},
                            "confidence": {"type": "number"},
                            "reason": {"type": "string"},
                        },
                        "required": ["intent", "confidence", "reason"],
                    },
                },
            },
        ]
        completion = await ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": (
                        "Вот сообщение из чата потенциального клиента:\n"
                        f"{user_message}\n\n"
                        "Реши, стоит ли отписывать этому человеку в личку для продажи."
                    ),
                },
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
        message = completion.choices[0].message
        tool_calls = message.tool_calls or []
        if tool_calls:
            tool_call = tool_calls[0]
            tool_name = str(tool_call.function.name or "").strip()
            try:
                payload = json.loads(tool_call.function.arguments or "{}")
            except Exception:
                payload = {}
            intent = str(payload.get("intent") or "unsure").strip().lower()
            try:
                confidence = float(payload.get("confidence"))
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = min(1.0, max(0.0, confidence))
            reason = str(payload.get("reason") or "").strip()[:500]
            decision = "engage" if tool_name == "engage_lead" else "ignore"
            lead_temperature = str(payload.get("lead_temperature") or "warm").strip().lower()
            if lead_temperature not in {"cold", "warm", "hot"}:
                lead_temperature = "warm"
            stage_hint = str(payload.get("stage_hint") or "first_touch").strip().lower()
            if stage_hint not in {"first_touch", "discovery", "value_pitch", "handoff"}:
                stage_hint = "first_touch"
            return {
                "decision": decision,
                "intent": intent,
                "confidence": confidence,
                "reason": reason,
                "lead_temperature": lead_temperature,
                "stage_hint": stage_hint,
                "handoff_ready": bool(payload.get("handoff_ready")),
            }

        raw = (message.content or "").strip()
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(raw)
        except Exception:
            logger.warning("sales_manager classify parse failed, fallback to unsure")
            return {
                "decision": "ignore",
                "intent": "unsure",
                "confidence": 0.0,
                "reason": "invalid_classifier_json",
                "lead_temperature": "warm",
                "stage_hint": "first_touch",
                "handoff_ready": False,
            }

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
        return {
            "decision": "ignore" if intent in {"non_target", "do_not_contact", "unsure"} else "engage",
            "intent": intent,
            "confidence": confidence,
            "reason": reason,
            "lead_temperature": "warm",
            "stage_hint": "first_touch",
            "handoff_ready": False,
        }

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
        chat_portrait: str | None = None,
        current_sales_state: str = "DISCOVERED",
        recent_history: list[dict[str, Any]] | None = None,
    ) -> str:
        model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        stage_hint = str(qualification.get("stage_hint") or "first_touch").strip().lower()
        context_parts = [
            f"Источник: {c.get('source', 'Unknown')}\nТекст: {c.get('text', '')}"
            for c in context_list
        ]
        context_text = "\n\n---\n\n".join(context_parts) if context_parts else "Контекст не найден."
        history_block = self._format_sales_history(recent_history)
        portrait_block = self._format_portrait_block(chat_portrait)
        stage_instruction = self._sales_stage_instruction(
            current_sales_state=(current_sales_state or "DISCOVERED").strip().upper(),
            stage_hint=stage_hint,
        )
        system_prompt = (
            f"{prompt}\n\n"
            "Ты менеджер отдела продаж. Пиши сообщение строго под текущую стадию сделки и контекст.\n"
            f"Продукт: {product_name}\n"
            f"Категория: {offer_type}\n"
            f"Текущая стадия CRM/FSM: {(current_sales_state or 'DISCOVERED').strip().upper()}\n"
            f"Инструкция по стадии: {stage_instruction}\n"
            "Все сообщения должны быть ненавязчивыми, человеческими и полезными. "
            "Не выдумывай факты про клиента. "
            "Верни только чистый текст, без markdown."
        )
        if portrait_block:
            system_prompt = f"{system_prompt}\n\n{portrait_block}"
        if usp:
            system_prompt = f"{system_prompt}\n\nКлючевое УТП:\n{usp}"
        if history_block:
            system_prompt = f"{system_prompt}\n\nНедавняя история диалога:\n{history_block}"
        user_prompt = (
            f"Исходное сообщение в чате:\n{user_message}\n\n"
            f"Классификация:\n{json.dumps(qualification, ensure_ascii=False)}\n\n"
            f"Контекст продукта (RAG):\n{context_text}\n\n"
            "Сгенерируй следующее сообщение sales-диалога.\n"
            "Если это первый контакт - используй мягкий старт формата: "
            "'увидел ваше сообщение в чате, подскажите, вам интересно ...'.\n"
            "Если это продолжение - выявляй боли, показывай что изменится после внедрения, "
            "и подводи к передаче на ЛПР/заявку, когда клиент готов.\n"
            "Длина: 1-4 предложения."
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

    @staticmethod
    def _sales_stage_instruction(*, current_sales_state: str, stage_hint: str) -> str:
        if stage_hint == "handoff":
            return (
                "Заверши диалог на шаге передачи: предложи удобный формат передачи на ЛПР, "
                "заявку или демо-звонок."
            )
        if stage_hint == "value_pitch":
            return (
                "Покажи ценность и ожидаемые изменения после внедрения, "
                "связывай выгоды с болями клиента."
            )
        if stage_hint == "discovery":
            return "Уточни боли и текущий процесс клиента, задай 1-2 коротких вопроса для квалификации."
        if current_sales_state in {"SENT", "REPLIED_POSITIVE", "QUEUED"}:
            return "Продолжай диалог после первого касания: выяви потребность и подведи к следующему шагу."
        return "Сделай ненавязчивое первое касание и предложи релевантную помощь по запросу из чата."

    @staticmethod
    def _format_sales_history(history: list[dict[str, Any]] | None) -> str:
        if not history:
            return ""
        rows: list[str] = []
        for item in history[-6:]:
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            label = "Агент" if role == "assistant" else "Клиент"
            rows.append(f"{label}: {content}")
        return "\n".join(rows)

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

    async def _load_sales_contact_state(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
    ) -> str:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = await session.scalar(
                        select(AgentSalesContact.state).where(
                            AgentSalesContact.agent_id == agent_id,
                            AgentSalesContact.user_external_id == user_external_id,
                            AgentSalesContact.source_chat_id == source_chat_id,
                        )
                    )
            value = str(row or "DISCOVERED").strip().upper()
            return value or "DISCOVERED"
        except Exception:
            logger.warning("sales_manager failed to load FSM state, fallback to DISCOVERED")
            return "DISCOVERED"

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
