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


_runtime_service: TemplateRuntimeService | None = None


def get_template_runtime() -> TemplateRuntimeService:
    global _runtime_service
    if _runtime_service is None:
        _runtime_service = TemplateRuntimeService()
    return _runtime_service
