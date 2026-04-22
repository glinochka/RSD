"""Unified template runtime for agent responses."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from ..qdrant.search_service import search_knowledge_base
from .ai_authoring import generate_answer_with_context

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
    ) -> TemplateExecutionResult:
        normalized = (template_type or "qa").strip().lower()
        if normalized == "function_calling":
            normalized = "crm_admin"
        if normalized in {"qa", "crm_admin", "lead_generation", "content_factory"}:
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
