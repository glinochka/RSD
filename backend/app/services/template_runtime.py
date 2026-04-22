"""Unified template runtime for agent responses."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import AgentCrmConnection
from ..utils.crypto import decrypt_token
from .ai_authoring import ai_client, generate_answer_with_context
from .crm import build_provider
from .crm.tool_registry import CRMNeedsConfirmationError, CRMToolRegistry
from ..qdrant.search_service import search_knowledge_base

logger = logging.getLogger(__name__)


@dataclass
class TemplateExecutionResult:
    answer: str
    sources: list[str]


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
            )
            if crm_result is not None:
                return crm_result
            logger.warning("crm_admin runtime fallback to qa strategy")

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
            bundle = json.loads(decrypt_token(connection.encrypted_credentials))
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

        system_prompt = (
            f"{prompt}\n\n"
            "Ты CRM-администратор. Если нужно действие в CRM — используй function tools. "
            "Не выдумывай результаты CRM операций: опирайся только на ответы tools. "
            "Отвечай только чистым текстом, без markdown."
        ).strip()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

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
                return TemplateExecutionResult(answer=cleaned, sources=[])

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
                except CRMNeedsConfirmationError as exc:
                    return TemplateExecutionResult(answer=str(exc), sources=[])
                except Exception as exc:
                    tool_result = {"ok": False, "error": str(exc)}

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
