"""Unified template runtime for agent responses."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import re
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentAnalyticsMessage, AgentCrmConnection, AgentSalesContact
from ..utils.crypto import decrypt_booking_payment_secret, decrypt_crm_credentials
from ..utils.pii import mask_external_id, redact_pii_text
from .admin_booking import AdminBookingNeedsConfirmationError, AdminBookingToolRegistry
from .admin_applications.tool_registry import AdminApplicationToolRegistry
from .admin_applications.fields import fields_schema_for_prompt
from .admin_booking.catalog_prompt import load_booking_catalog_knowledge
from .agent_memory import build_client_memory_block, build_client_memory_system_section
from .ai_authoring import ai_client, generate_answer_with_context
from .content_factory_runtime import get_content_factory_orchestrator
from .crm import build_provider
from .crm.tool_registry import CRMNeedsConfirmationError, CRMToolRegistry
from .http_integration.errors import HttpIntegrationNeedsConfirmationError, HttpIntegrationValidationError
from .http_integration.tool_registry import load_http_integration_registry
from .sales.tool_registry import SalesNeedsConfirmationError, SalesToolRegistry
from .sales.fsm import SalesFSMError, get_sales_fsm_service
from .sales.sales_scenario_context import (
    SCENARIO_CHANNEL_NEURO_COMMENT,
    build_sales_compose_action_instruction,
    build_sales_llm_user_prompt,
    build_sales_message_frame,
    build_sales_scenario_system_addon,
    build_sales_unified_task_instruction,
    resolve_sales_interaction_scenario,
)
from ..prompts.system_prompts import (
    CHAT_OPERATOR_PERSONA,
    CHAT_PORTRAIT_SYSTEM,
    CLIENT_ACTION_PENDING_MESSAGE,
    CLIENT_OPERATOR_ESCALATION_MESSAGE,
    CLIENT_OWNER_HANDOFF_MESSAGE,
    CRM_ADMIN_HTTP_INTEGRATION_HINT,
    CRM_ADMIN_LLM_EMPTY_FALLBACK,
    CRM_ADMIN_RESOURCE_LINKED_HINT,
    CRM_ADMIN_RESOURCE_SEPARATE_HINT,
    QA_OWNER_HANDOFF_INSTRUCTION,
    SALES_COMPOSED_MESSAGE_FALLBACK,
    SALES_DM_COMPOSE_INSTRUCTION,
    SALES_HUMAN_FLEXIBILITY_BLOCK,
    SALES_NEURO_COMMENT_INSTRUCTION,
    SALES_PRE_SALES_FINISH_MODE_ADDON,
    SALES_PRE_SALES_SCREENING_INSTRUCTION,
    SALES_PRE_SALES_SCORING_ADDON,
    SALES_TOOLS_SYSTEM_INSTRUCTION,
    SALES_UNIFIED_FINISH_MODE_ADDON,
    SALES_UNIFIED_QUALIFY_INSTRUCTION,
    SANITIZE_EMPTY_ANSWER_FALLBACK,
    build_chat_turn_user_prompt,
    build_crm_admin_system_prompt,
    build_crm_admin_applications_system_prompt,
    CRM_ADMIN_APPLICATIONS_LLM_EMPTY_FALLBACK,
    coerce_client_facing_answer,
    format_rag_chunks_for_prompt,
    sales_stage_instruction,
)
from ..qdrant.search_service import search_knowledge_base

logger = logging.getLogger(__name__)
MAX_CHAT_PORTRAIT_CHARS = 2000
_DSML_TOOL_CALLS_RE = re.compile(r"<｜DSML｜tool_calls>.*?</｜DSML｜tool_calls>", re.DOTALL)
_DSML_INVOKE_RE = re.compile(
    r"<｜DSML｜invoke name=\"(?P<name>[^\"]+)\">(?P<body>.*?)</｜DSML｜invoke>",
    re.DOTALL,
)
_DSML_PARAM_RE = re.compile(
    r"<｜DSML｜parameter name=\"(?P<name>[^\"]+)\"[^>]*>(?P<value>.*?)</｜DSML｜parameter>",
    re.DOTALL,
)
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_TEMPLATE_VAR_RE = re.compile(r"(\{\{[^{}]+\}\}|\$\{[^{}]+\}|%\([^)]+\)s)")
# Only strip obviously leaked API/internal identifiers — a broad "word=value" rule
# mangles legitimate phrases (e.g. rare English words before "=") and produces
# "технические данные скрыты" in the middle of customer-facing sentences.
_INTERNAL_ASSIGNMENT_RE = re.compile(
    r"\b(staff_id|resource_id|service_id|agent_id|appointment_id|client_external_id|"
    r"slot_id|user_id|chat_id|template_id|lookup_staff_id|new_staff_id|new_resource_id)\s*=\s*\S+",
    re.IGNORECASE,
)
_JSON_PAIR_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]{2,})\s*:\s*"
    r"(?P<value>[\"'][^\"']*[\"']|https?://\S+|[^,\]\}\n]+)"
)
# Tool fields that must reach the client (especially payment links).
_CUSTOMER_VISIBLE_JSON_KEYS = frozenset({"payment_url", "confirmation_url"})
_INTERNAL_MARKER_RE = re.compile(r"\[[A-Z][A-Z0-9_]{2,}\]")
_HTTPS_URL_RE = re.compile(r"https?://[^\s<>\"']+")


class EscalationType(str, Enum):
    """Type of escalation to operator."""

    NONE = "none"
    FREEZE_CHAT = "freeze_chat"
    NOTIFY_ONLY = "notify_only"


@dataclass
class TemplateExecutionResult:
    answer: str
    sources: list[str]
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    fallback_to_text: bool = False
    fallback_reason: str | None = None
    requires_owner_handoff: bool = False
    owner_handoff_reason: str | None = None
    escalation_type: EscalationType = EscalationType.NONE
    discard_message: bool = False


class TemplateRuntimeService:
    """Executes agent templates through a single entrypoint."""

    @staticmethod
    def _is_userbot_channel(source_channel: str) -> bool:
        normalized = (source_channel or "").strip().lower()
        return normalized in {"telegram_userbot", "whatsapp_userbot", "max_userbot"}

    @staticmethod
    def _is_smart_search_enabled(template_config: dict[str, Any] | None) -> bool:
        if not isinstance(template_config, dict):
            return True
        return bool(template_config.get("enable_smart_search", True))

    @staticmethod
    def _is_chat_freeze_enabled(template_config: dict[str, Any] | None) -> bool:
        if not isinstance(template_config, dict):
            return True
        return bool(template_config.get("enable_chat_freeze", True))

    @staticmethod
    def _is_chat_history_enabled(template_config: dict[str, Any] | None) -> bool:
        if not isinstance(template_config, dict):
            return True
        return bool(template_config.get("enable_chat_history", True))

    @staticmethod
    def _sales_workflow_completion_mode(template_config: dict[str, Any] | None) -> str:
        if not isinstance(template_config, dict):
            return "auto_finish_on_signal"
        mode = str(template_config.get("workflow_completion_mode") or "auto_finish_on_signal").strip().lower()
        if mode not in {"auto_finish_on_signal", "continue_dialog"}:
            return "auto_finish_on_signal"
        return mode

    @staticmethod
    def _is_sales_terminal_state(state: str) -> bool:
        normalized = str(state or "").strip().upper()
        return normalized in {"HANDOFF_CRM", "REPLIED_NEGATIVE", "NO_REPLY", "SKIPPED"}

    @staticmethod
    def _resolve_sales_score_scale(template_config: dict[str, Any] | None) -> int:
        if not isinstance(template_config, dict):
            return 100
        raw = template_config.get("lead_score_scale", 100)
        try:
            scale = int(raw)
        except (TypeError, ValueError):
            return 100
        if scale not in {10, 100}:
            return 100
        return scale

    @staticmethod
    def _clamp_score_0_100(value: float) -> float:
        return min(100.0, max(0.0, float(value)))

    @staticmethod
    def _to_display_score(score_0_100: float, *, score_scale: int) -> float | int:
        if score_scale == 10:
            return round(TemplateRuntimeService._clamp_score_0_100(score_0_100) / 10.0, 1)
        return int(round(TemplateRuntimeService._clamp_score_0_100(score_0_100)))

    @staticmethod
    def _normalize_model_score(value: Any, *, score_scale: int, default_0_100: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return TemplateRuntimeService._clamp_score_0_100(default_0_100)
        normalized = numeric * 10.0 if score_scale == 10 else numeric
        return TemplateRuntimeService._clamp_score_0_100(normalized)

    @staticmethod
    def _default_heat_score_from_temperature(lead_temperature: str) -> float:
        normalized = str(lead_temperature or "").strip().lower()
        if normalized == "hot":
            return 85.0
        if normalized == "cold":
            return 30.0
        return 60.0

    def _build_sales_lead_profile(
        self,
        *,
        qualification: dict[str, Any],
        previous_profile: dict[str, Any] | None,
        score_scale: int,
    ) -> dict[str, Any]:
        confidence = self._clamp_score_0_100(float(qualification.get("confidence") or 0.0) * 100.0)
        heat = self._normalize_model_score(
            qualification.get("lead_heat_score"),
            score_scale=score_scale,
            default_0_100=self._default_heat_score_from_temperature(str(qualification.get("lead_temperature") or "warm")),
        )
        resilience = self._normalize_model_score(
            qualification.get("resilience_score"),
            score_scale=score_scale,
            default_0_100=55.0,
        )
        engagement = self._normalize_model_score(
            qualification.get("engagement_score"),
            score_scale=score_scale,
            default_0_100=confidence,
        )
        fresh_overall = self._clamp_score_0_100(heat * 0.45 + resilience * 0.2 + engagement * 0.35)

        prev_overall = None
        if isinstance(previous_profile, dict):
            prev_raw = previous_profile.get("lead_score_0_100")
            try:
                prev_overall = self._clamp_score_0_100(float(prev_raw))
            except (TypeError, ValueError):
                prev_overall = None
        overall_0_100 = fresh_overall if prev_overall is None else self._clamp_score_0_100(prev_overall * 0.65 + fresh_overall * 0.35)

        delta = 0.0 if prev_overall is None else round(overall_0_100 - prev_overall, 2)
        if delta >= 4.0:
            trend = "warming"
        elif delta <= -4.0:
            trend = "cooling"
        else:
            trend = "stable"

        if overall_0_100 >= 80:
            bucket = "very_hot"
        elif overall_0_100 >= 65:
            bucket = "warm"
        elif overall_0_100 >= 45:
            bucket = "neutral"
        else:
            bucket = "cold"

        return {
            "score_scale": score_scale,
            "lead_score": self._to_display_score(overall_0_100, score_scale=score_scale),
            "lead_score_0_100": round(overall_0_100, 2),
            "lead_heat_score": self._to_display_score(heat, score_scale=score_scale),
            "lead_heat_score_0_100": round(heat, 2),
            "resilience_score": self._to_display_score(resilience, score_scale=score_scale),
            "resilience_score_0_100": round(resilience, 2),
            "engagement_score": self._to_display_score(engagement, score_scale=score_scale),
            "engagement_score_0_100": round(engagement, 2),
            "trend": trend,
            "delta_0_100": delta,
            "bucket": bucket,
        }

    @staticmethod
    def _format_sales_lead_profile(profile: dict[str, Any] | None) -> str:
        if not isinstance(profile, dict):
            return ""
        score_scale = int(profile.get("score_scale") or 100)
        lead_score = profile.get("lead_score")
        heat = profile.get("lead_heat_score")
        resilience = profile.get("resilience_score")
        engagement = profile.get("engagement_score")
        trend = str(profile.get("trend") or "stable")
        bucket = str(profile.get("bucket") or "neutral")
        return (
            "Портрет лида:\n"
            f"- Общий score: {lead_score} / {score_scale}\n"
            f"- Прогретость: {heat} / {score_scale}\n"
            f"- Устойчивость к возражениям: {resilience} / {score_scale}\n"
            f"- Вовлеченность: {engagement} / {score_scale}\n"
            f"- Тренд: {trend}, сегмент: {bucket}"
        )

    async def execute(
        self,
        *,
        template_type: str | None,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
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
                return self._sanitize_result(crm_result)
            logger.warning("crm_admin runtime fallback to qa strategy")
            qa_result = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
                enable_chat_history=self._is_chat_history_enabled(template_config),
                runtime_context=runtime_context or {},
                template_config=template_config or {},
            )
            qa_result.fallback_to_text = True
            qa_result.fallback_reason = "crm_runtime_unavailable"
            return self._sanitize_result(qa_result)

        if normalized == "sales_manager":
            sales_result = await self._execute_sales_manager(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                template_config=template_config or {},
                source_channel=source_channel or "telegram",
                user_external_id=user_external_id,
                agent_id=agent_id,
                chat_portrait=chat_portrait,
                runtime_context=runtime_context or {},
            )
            return self._sanitize_result(sales_result)

        if normalized == "content_factory":
            content_result = await self._execute_content_factory(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
                runtime_context=runtime_context or {},
                template_config=template_config or {},
            )
            return self._sanitize_result(content_result)

        if normalized == "qa":
            qa_result = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
                enable_owner_handoff=self._is_chat_freeze_enabled(template_config),
                enable_smart_search=self._is_smart_search_enabled(template_config),
                enable_chat_history=self._is_chat_history_enabled(template_config),
                runtime_context=runtime_context or {},
                template_config=template_config or {},
            )
            return self._sanitize_result(qa_result)

        if normalized == "lead_generation":
            lead_result = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
                enable_smart_search=self._is_smart_search_enabled(template_config),
                enable_chat_history=self._is_chat_history_enabled(template_config),
                runtime_context=runtime_context or {},
                template_config=template_config or {},
            )
            return self._sanitize_result(lead_result)

        # Unknown template types should not break runtime.
        logger.warning("Unknown template_type=%s, fallback to qa strategy", normalized)
        fallback_result = await self._execute_qa_like(
            prompt=prompt,
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
            knowledge_project_id=knowledge_project_id,
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
            chat_portrait=chat_portrait,
            enable_smart_search=self._is_smart_search_enabled(template_config),
            enable_chat_history=self._is_chat_history_enabled(template_config),
            runtime_context=runtime_context or {},
            template_config=template_config or {},
        )
        return self._sanitize_result(fallback_result)

    @staticmethod
    def _strip_dsml_tool_markup(text: str) -> str:
        return _DSML_TOOL_CALLS_RE.sub("", text or "")

    def _clean_llm_text(self, text: str) -> str:
        cleaned = self._strip_dsml_tool_markup(text).replace("#", "").replace("*", "").strip()
        return self._sanitize_final_answer(cleaned)

    @staticmethod
    def _is_degenerate_sanitized_answer(text: str) -> bool:
        """True if nothing usable remains except placeholder tokens from scrubbing."""
        s = (text or "").strip()
        if not s:
            return True
        junk_only = re.compile(
            r"^(технические данные скрыты|технические детали скрыты\.?)([\s,;]*)$",
            re.IGNORECASE,
        )
        for raw_line in s.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if not junk_only.match(line):
                return False
        return True

    @staticmethod
    def _redact_json_pairs(text: str) -> str:
        """Strip internal key:value leaks; keep payment URLs visible for the client."""

        def _repl(match: re.Match[str]) -> str:
            key = (match.group("key") or "").strip().lower()
            value = (match.group("value") or "").strip().strip("\"'")
            if key in _CUSTOMER_VISIBLE_JSON_KEYS:
                return value
            return "технические данные скрыты"

        return _JSON_PAIR_RE.sub(_repl, text or "")

    @staticmethod
    def _ensure_booking_payment_url(answer: str, payment_url: str | None) -> str:
        url = (payment_url or "").strip()
        if not url:
            return answer or ""
        body = (answer or "").strip()
        if url in body:
            return body
        placeholder = "технические данные скрыты"
        if placeholder in body:
            body = re.sub(
                r"(ссылк[а-яё][^\n.]{0,120}?:\s*)" + re.escape(placeholder),
                rf"\1{url}",
                body,
                count=1,
                flags=re.IGNORECASE,
            )
            if url in body:
                return body
        if not body:
            return f"Ссылка для оплаты: {url}"
        return f"{body}\n\nСсылка для оплаты: {url}"

    @staticmethod
    def _stash_https_urls(text: str) -> tuple[str, list[str]]:
        urls: list[str] = []

        def _repl(match: re.Match[str]) -> str:
            urls.append(match.group(0))
            return f"\x00PAYURL{len(urls) - 1}\x00"

        return _HTTPS_URL_RE.sub(_repl, text or ""), urls

    @staticmethod
    def _restore_https_urls(text: str, urls: list[str]) -> str:
        restored = text or ""
        for index, url in enumerate(urls):
            restored = restored.replace(f"\x00PAYURL{index}\x00", url)
        return restored

    @staticmethod
    def _sanitize_final_answer(text: str) -> str:
        """Remove leaked variable names/values from customer-facing answers."""
        sanitized, stashed_urls = TemplateRuntimeService._stash_https_urls(text or "")
        sanitized = _CODE_BLOCK_RE.sub("Технические детали скрыты.", sanitized)
        sanitized = _INTERNAL_MARKER_RE.sub("", sanitized)
        sanitized = _TEMPLATE_VAR_RE.sub("технические данные скрыты", sanitized)
        sanitized = _INTERNAL_ASSIGNMENT_RE.sub("технические данные скрыты", sanitized)
        sanitized = TemplateRuntimeService._redact_json_pairs(sanitized)

        safe_lines: list[str] = []
        for raw_line in sanitized.splitlines():
            line = re.sub(r"\s{2,}", " ", raw_line).strip()
            if not line:
                continue
            if _TEMPLATE_VAR_RE.search(line) or _INTERNAL_ASSIGNMENT_RE.search(line):
                continue
            safe_lines.append(line)

        collapsed = "\n".join(safe_lines).strip()
        if not collapsed or TemplateRuntimeService._is_degenerate_sanitized_answer(collapsed):
            return SANITIZE_EMPTY_ANSWER_FALLBACK
        restored = TemplateRuntimeService._restore_https_urls(collapsed, stashed_urls)
        return coerce_client_facing_answer(restored)

    def _sanitize_result(self, result: TemplateExecutionResult) -> TemplateExecutionResult:
        if not result.discard_message:
            result.answer = self._sanitize_final_answer(result.answer)
        handoff = getattr(result, "owner_handoff_reason", None)
        if handoff:
            result.owner_handoff_reason = self._sanitize_final_answer(str(handoff))
        return result

    @staticmethod
    def _serialize_tool_call(tool_call: Any) -> dict[str, Any]:
        if isinstance(tool_call, dict):
            return tool_call
        if hasattr(tool_call, "model_dump"):
            return tool_call.model_dump()
        fn = getattr(tool_call, "function", None)
        return {
            "id": str(getattr(tool_call, "id", "")),
            "type": "function",
            "function": {
                "name": str(getattr(fn, "name", "")),
                "arguments": str(getattr(fn, "arguments", "{}")),
            },
        }

    @staticmethod
    def _tool_call_name(tool_call: Any) -> str:
        if isinstance(tool_call, dict):
            return str(tool_call.get("function", {}).get("name") or "")
        fn = getattr(tool_call, "function", None)
        return str(getattr(fn, "name", "") or "")

    @staticmethod
    def _tool_call_arguments(tool_call: Any) -> str:
        if isinstance(tool_call, dict):
            return str(tool_call.get("function", {}).get("arguments") or "{}")
        fn = getattr(tool_call, "function", None)
        return str(getattr(fn, "arguments", "{}") or "{}")

    @staticmethod
    def _tool_call_id(tool_call: Any, *, fallback: str) -> str:
        if isinstance(tool_call, dict):
            return str(tool_call.get("id") or fallback)
        return str(getattr(tool_call, "id", "") or fallback)

    @staticmethod
    def _parse_dsml_tool_calls(content: str, *, call_id_prefix: str = "dsml_call") -> list[dict[str, Any]]:
        if "DSML" not in (content or ""):
            return []
        parsed: list[dict[str, Any]] = []
        for invoke_index, invoke_match in enumerate(_DSML_INVOKE_RE.finditer(content or ""), start=1):
            tool_name = str(invoke_match.group("name") or "").strip()
            if not tool_name:
                continue
            body = invoke_match.group("body") or ""
            args: dict[str, Any] = {}
            for param_match in _DSML_PARAM_RE.finditer(body):
                param_name = str(param_match.group("name") or "").strip()
                if not param_name:
                    continue
                raw_value = (param_match.group("value") or "").strip()
                marker_is_string = "string=\"false\"" not in (param_match.group(0) or "")
                if marker_is_string:
                    args[param_name] = raw_value
                else:
                    try:
                        args[param_name] = json.loads(raw_value)
                    except Exception:
                        args[param_name] = raw_value
            parsed.append(
                {
                    "id": f"{call_id_prefix}_{invoke_index}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
        return parsed

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

        min_message_length = 15
        important_keywords = ["купить", "заказать", "хочу", "нужно", "интересует", "цена", "стоимость"]
        is_important = (
            len(text) >= min_message_length 
            or any(keyword in text.lower() for keyword in important_keywords)
        )
        
        previous = await self._load_chat_portrait(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )
        
        if not is_important and previous:
            return previous
        cfg = template_config or {}
        model = str(
            cfg.get("portrait_model") or cfg.get("generation_model") or "deepseek-chat"
        ).strip() or "deepseek-chat"
        system_prompt = CHAT_PORTRAIT_SYSTEM
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

        workflow_mode = str(template_config.get("workflow_mode") or "booking").strip().lower()
        if workflow_mode == "applications":
            return await self._execute_crm_admin_applications(
                prompt=prompt,
                user_message=user_message,
                agent_id=agent_id,
                user_external_id=user_external_id,
                template_config=template_config,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
            )

        from .admin_booking.payment_fulfillment import sync_pending_payments_for_client
        from .admin_booking.client_notify import notify_booking_payment_confirmed

        paid_sync = await sync_pending_payments_for_client(
            agent_id=agent_id,
            client_external_id=(user_external_id or "").strip(),
        )
        if paid_sync and paid_sync.fulfilled and paid_sync.client_message:
            try:
                await notify_booking_payment_confirmed(paid_sync)
            except Exception:
                logger.exception("Failed to notify client after pending payment sync")
            return TemplateExecutionResult(
                answer=paid_sync.client_message,
                sources=[],
                tool_events=[],
            )

        from .admin_booking.domains import DOMAIN_REGISTRY as _domain_registry
        domain_type = str(template_config.get("domain_type") or "beauty_salon").strip().lower()
        if domain_type not in _domain_registry:
            domain_type = "beauty_salon"
        resource_linked_to_staff = bool(template_config.get("resource_linked_to_staff", True))
        custom_domain_instruction = template_config.get("custom_domain_instruction") or None
        booking_backend = str(template_config.get("booking_backend") or "auto").strip().lower()
        if booking_backend not in {"local", "crm", "auto"}:
            booking_backend = "auto"
        paid_booking_enabled = bool(template_config.get("paid_booking_enabled"))
        crm_provider_name = str(template_config.get("crm_provider") or "amocrm").strip().lower()
        confirmation_policy = str(template_config.get("confirmation_policy") or "confirm_risky").strip().lower()
        allowed_crm_tools_raw = template_config.get("allowed_tools")
        allowed_crm_tools = allowed_crm_tools_raw if isinstance(allowed_crm_tools_raw, list) else None
        allowed_booking_tools_raw = template_config.get("allowed_booking_tools")
        allowed_booking_tools = (
            allowed_booking_tools_raw if isinstance(allowed_booking_tools_raw, list) else None
        )
        http_integrations_enabled = bool(template_config.get("http_integrations_enabled", True))
        http_integration_names_raw = template_config.get("http_integration_names")
        http_integration_names_allow: list[str] | None = None
        if isinstance(http_integration_names_raw, list):
            http_integration_names_allow = [
                str(x or "").strip().lower() for x in http_integration_names_raw if str(x or "").strip()
            ]

        chat_history = await self._load_recent_channel_history(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )

        booking_payment_api_key = await self._get_admin_booking_payment_api_key(agent_id=agent_id)
        booking_registry = AdminBookingToolRegistry(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
            confirmation_policy=confirmation_policy,
            user_message=user_message,
            allowed_tools=allowed_booking_tools,
            paid_booking_enabled=paid_booking_enabled,
            yookassa_api_key=booking_payment_api_key,
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
                    recent_history=chat_history,
                )
                crm_tool_names = {
                    str(item.get("function", {}).get("name") or "")
                    for item in crm_registry.tools_for_llm()
                    if isinstance(item, dict)
                }
            except Exception:
                logger.exception("Failed to initialize CRM provider for agent_id=%s", agent_id)

        http_registry = await load_http_integration_registry(
            agent_id=agent_id,
            enabled=http_integrations_enabled,
            name_allowlist=http_integration_names_allow,
            user_message=user_message or "",
            recent_history=chat_history,
        )

        llm_tools: list[dict[str, Any]] = []
        llm_tools.extend(booking_llm_tools)
        if crm_registry is not None:
            llm_tools.extend(crm_registry.tools_for_llm())
        if http_registry is not None:
            llm_tools.extend(http_registry.tools_for_llm())
        if not llm_tools:
            return None

        client_memory_section = build_client_memory_system_section(
            portrait=chat_portrait,
            history=chat_history,
        )
        domain_instruction = self._crm_admin_domain_instruction(
            domain_type=domain_type,
            custom_domain_instruction=custom_domain_instruction,
        )
        backend_instruction = self._crm_admin_backend_instruction(
            booking_backend=booking_backend,
            crm_connected=connection is not None,
            crm_provider_name=crm_provider_name,
        )
        if resource_linked_to_staff:
            resource_model_hint = CRM_ADMIN_RESOURCE_LINKED_HINT
        else:
            resource_model_hint = CRM_ADMIN_RESOURCE_SEPARATE_HINT
        now_local = datetime.now()
        now_context = (
            f"Сейчас: {now_local.strftime('%Y-%m-%d %H:%M')} "
            f"(день недели: {now_local.strftime('%A')})."
        )
        http_integration_hint = ""
        if http_registry is not None:
            http_integration_hint = CRM_ADMIN_HTTP_INTEGRATION_HINT
        context_tail = f"{now_context}\n{domain_instruction}\n{resource_model_hint}\n{backend_instruction}"
        if http_integration_hint:
            context_tail = f"{context_tail}\n\n{http_integration_hint}"
        knowledge_catalog_block = await load_booking_catalog_knowledge(agent_id=agent_id)
        system_prompt = build_crm_admin_system_prompt(
            agent_prompt=prompt,
            context_tail=context_tail,
            today_date=now_local.strftime("%Y-%m-%d"),
            knowledge_catalog_block=knowledge_catalog_block,
        )
        if client_memory_section:
            system_prompt = f"{system_prompt}\n\n{client_memory_section}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        tool_events: list[dict[str, Any]] = []
        pending_payment_url: str | None = None
        max_iterations = 15

        is_phone_channel = (source_channel or "").strip().lower() == "phone"
        llm_temperature = 0.38 if is_phone_channel else 0.2

        for iteration in range(max_iterations):
            completion = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=llm_temperature,
            )
            message = completion.choices[0].message
            tool_calls: list[Any] = list(message.tool_calls or [])
            content = (message.content or "").strip()
            if not tool_calls:
                tool_calls = self._parse_dsml_tool_calls(content, call_id_prefix=f"crm_admin_{iteration}")

            if not tool_calls:
                cleaned = self._clean_llm_text(content)
                if not cleaned:
                    cleaned = CRM_ADMIN_LLM_EMPTY_FALLBACK
                cleaned = self._ensure_booking_payment_url(cleaned, pending_payment_url)
                return TemplateExecutionResult(answer=cleaned, sources=[], tool_events=tool_events)

            messages.append(
                {
                    "role": "assistant",
                    "content": self._strip_dsml_tool_markup(message.content or "").strip(),
                    "tool_calls": [self._serialize_tool_call(tool_call) for tool_call in tool_calls],
                }
            )

            all_tools_succeeded = True
            for call_index, tool_call in enumerate(tool_calls, start=1):
                tool_name = self._tool_call_name(tool_call)
                raw_args = self._tool_call_arguments(tool_call)
                tool_call_id = self._tool_call_id(
                    tool_call,
                    fallback=f"crm_admin_{iteration}_{call_index}",
                )
                try:
                    if booking_registry.has_tool(tool_name):
                        tool_result = await booking_registry.execute_tool(tool_name, raw_args)
                        self._log_crm_admin_booking_tool(
                            agent_id=agent_id,
                            tool_name=tool_name,
                            tool_result=tool_result,
                        )
                    elif crm_registry is not None and tool_name in crm_tool_names:
                        tool_result = await crm_registry.execute_tool(tool_name, raw_args)
                    elif http_registry is not None and http_registry.has_tool(tool_name):
                        tool_result = await http_registry.execute_tool(tool_name, raw_args)
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
                            "tool_args_summary": tool_result.get("tool_args_summary") or "",
                            "error": None,
                        }
                    )
                    if tool_name == "create_appointment" and tool_result.get("ok"):
                        inner = tool_result.get("result")
                        if isinstance(inner, dict):
                            raw_url = str(inner.get("payment_url") or inner.get("confirmation_url") or "").strip()
                            if raw_url:
                                pending_payment_url = raw_url
                except AdminBookingNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {
                        "ok": False,
                        "status": "awaiting_user_confirmation",
                        "hint": safe_error,
                    }
                    all_tools_succeeded = False
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "awaiting_user_confirmation",
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
                except CRMNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {
                        "ok": False,
                        "status": "awaiting_user_confirmation",
                        "hint": safe_error,
                    }
                    all_tools_succeeded = False
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "awaiting_user_confirmation",
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
                except HttpIntegrationNeedsConfirmationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {
                        "ok": False,
                        "status": "awaiting_user_confirmation",
                        "hint": safe_error,
                    }
                    all_tools_succeeded = False
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "awaiting_user_confirmation",
                            "latency_ms": 0,
                            "crm_provider": "http_integration",
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": False,
                            "idempotent_replay": False,
                            "idempotency_key": None,
                            "error": safe_error,
                        }
                    )
                except HttpIntegrationValidationError as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {"ok": False, "error": safe_error}
                    all_tools_succeeded = False
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "error",
                            "latency_ms": 0,
                            "crm_provider": "http_integration",
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
                    all_tools_succeeded = False
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
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

            if iteration == max_iterations - 1:
                final_completion = await ai_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.2,
                )
                final_content = (final_completion.choices[0].message.content or "").strip()
                cleaned = self._ensure_booking_payment_url(
                    self._clean_llm_text(final_content),
                    pending_payment_url,
                )
                return TemplateExecutionResult(
                    answer=cleaned or CRM_ADMIN_LLM_EMPTY_FALLBACK,
                    sources=[],
                    tool_events=tool_events,
                )

        final_completion = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
        )
        final_content = (final_completion.choices[0].message.content or "").strip()
        cleaned = self._ensure_booking_payment_url(
            self._clean_llm_text(final_content),
            pending_payment_url,
        )
        return TemplateExecutionResult(
            answer=cleaned or CRM_ADMIN_LLM_EMPTY_FALLBACK,
            sources=[],
            tool_events=tool_events,
        )

    async def _execute_crm_admin_applications(
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

        from .admin_booking.domains import DOMAIN_REGISTRY as _domain_registry

        domain_type = str(template_config.get("domain_type") or "consulting").strip().lower()
        if domain_type not in _domain_registry:
            domain_type = "consulting"
        custom_domain_instruction = template_config.get("custom_domain_instruction") or None
        crm_provider_name = str(template_config.get("crm_provider") or "amocrm").strip().lower()
        confirmation_policy = str(template_config.get("confirmation_policy") or "confirm_risky").strip().lower()
        allowed_crm_tools_raw = template_config.get("allowed_tools")
        allowed_crm_tools = allowed_crm_tools_raw if isinstance(allowed_crm_tools_raw, list) else None
        allowed_application_tools_raw = template_config.get("allowed_application_tools")
        allowed_application_tools = (
            allowed_application_tools_raw if isinstance(allowed_application_tools_raw, list) else None
        )
        http_integrations_enabled = bool(template_config.get("http_integrations_enabled", True))
        http_integration_names_raw = template_config.get("http_integration_names")
        http_integration_names_allow: list[str] | None = None
        if isinstance(http_integration_names_raw, list):
            http_integration_names_allow = [
                str(x or "").strip().lower() for x in http_integration_names_raw if str(x or "").strip()
            ]

        chat_history = await self._load_recent_channel_history(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
        )

        application_registry = AdminApplicationToolRegistry(
            agent_id=agent_id,
            user_external_id=user_external_id,
            source_channel=source_channel,
            template_config=template_config,
            allowed_tools=allowed_application_tools,
        )
        application_llm_tools = application_registry.tools_for_llm()

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
                    recent_history=chat_history,
                )
                crm_tool_names = {
                    str(item.get("function", {}).get("name") or "")
                    for item in crm_registry.tools_for_llm()
                    if isinstance(item, dict)
                }
            except Exception:
                logger.exception("Failed to initialize CRM provider for applications agent_id=%s", agent_id)

        http_registry = await load_http_integration_registry(
            agent_id=agent_id,
            enabled=http_integrations_enabled,
            name_allowlist=http_integration_names_allow,
            user_message=user_message or "",
            recent_history=chat_history,
        )

        llm_tools: list[dict[str, Any]] = []
        llm_tools.extend(application_llm_tools)
        if crm_registry is not None:
            llm_tools.extend(crm_registry.tools_for_llm())
        if http_registry is not None:
            llm_tools.extend(http_registry.tools_for_llm())
        if not llm_tools:
            return None

        client_memory_section = build_client_memory_system_section(
            portrait=chat_portrait,
            history=chat_history,
        )
        domain_instruction = self._crm_admin_domain_instruction(
            domain_type=domain_type,
            custom_domain_instruction=custom_domain_instruction,
        )
        now_local = datetime.now()
        now_context = (
            f"Сейчас: {now_local.strftime('%Y-%m-%d %H:%M')} "
            f"(день недели: {now_local.strftime('%A')})."
        )
        fields_schema = template_config.get("application_fields")
        if not isinstance(fields_schema, list):
            fields_schema = []
        fields_block = fields_schema_for_prompt(fields_schema)
        context_tail = f"{now_context}\n{domain_instruction}"
        system_prompt = build_crm_admin_applications_system_prompt(
            agent_prompt=prompt,
            context_tail=context_tail,
            fields_schema_block=fields_block,
        )
        if client_memory_section:
            system_prompt = f"{system_prompt}\n\n{client_memory_section}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        tool_events: list[dict[str, Any]] = []
        max_iterations = 12
        is_phone_channel = (source_channel or "").strip().lower() == "phone"
        llm_temperature = 0.38 if is_phone_channel else 0.2

        for iteration in range(max_iterations):
            completion = await ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=llm_temperature,
            )
            message = completion.choices[0].message
            tool_calls: list[Any] = list(message.tool_calls or [])
            content = (message.content or "").strip()
            if not tool_calls:
                tool_calls = self._parse_dsml_tool_calls(content, call_id_prefix=f"crm_apps_{iteration}")

            if not tool_calls:
                cleaned = self._clean_llm_text(content)
                if not cleaned:
                    cleaned = CRM_ADMIN_APPLICATIONS_LLM_EMPTY_FALLBACK
                return TemplateExecutionResult(answer=cleaned, sources=[], tool_events=tool_events)

            messages.append(
                {
                    "role": "assistant",
                    "content": self._strip_dsml_tool_markup(message.content or "").strip(),
                    "tool_calls": [self._serialize_tool_call(tool_call) for tool_call in tool_calls],
                }
            )

            for call_index, tool_call in enumerate(tool_calls, start=1):
                tool_name = self._tool_call_name(tool_call)
                raw_args = self._tool_call_arguments(tool_call)
                tool_call_id = self._tool_call_id(
                    tool_call,
                    fallback=f"crm_apps_{iteration}_{call_index}",
                )
                try:
                    if application_registry.has_tool(tool_name):
                        tool_result = await application_registry.execute_tool(tool_name, raw_args)
                    elif crm_registry is not None and tool_name in crm_tool_names:
                        tool_result = await crm_registry.execute_tool(tool_name, raw_args)
                    elif http_registry is not None and http_registry.has_tool(tool_name):
                        tool_result = await http_registry.execute_tool(tool_name, raw_args)
                    else:
                        raise RuntimeError(f"Tool '{tool_name}' is not available in current runtime")
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_status": tool_result.get("tool_status", "success"),
                            "latency_ms": int(tool_result.get("latency_ms") or 0),
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": bool(tool_result.get("ok")),
                            "error": None,
                        }
                    )
                except Exception as exc:
                    safe_error = redact_pii_text(str(exc))
                    tool_result = {"ok": False, "error": safe_error}
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_status": "error",
                            "latency_ms": 0,
                            "source_channel": source_channel,
                            "user_external_id": mask_external_id(user_external_id),
                            "ok": False,
                            "error": safe_error,
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        final_completion = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
        )
        final_content = (final_completion.choices[0].message.content or "").strip()
        cleaned = self._clean_llm_text(final_content)
        return TemplateExecutionResult(
            answer=cleaned or CRM_ADMIN_APPLICATIONS_LLM_EMPTY_FALLBACK,
            sources=[],
            tool_events=tool_events,
        )

    @staticmethod
    def _log_crm_admin_booking_tool(
        *,
        agent_id: int | None,
        tool_name: str,
        tool_result: dict[str, Any],
    ) -> None:
        """Lightweight diagnostics for booking reads (no PII, no slot times in logs)."""
        if agent_id is None or tool_name != "check_availability" or not tool_result.get("ok"):
            return
        payload = tool_result.get("result")
        if isinstance(payload, dict):
            if payload.get("validation_error"):
                logger.info("crm_admin check_availability validation_hint agent_id=%s", agent_id)
            else:
                slots = payload.get("available_slots")
                if isinstance(slots, list):
                    logger.info(
                        "crm_admin check_availability slot_count=%s agent_id=%s",
                        len(slots),
                        agent_id,
                    )
        elif isinstance(payload, list):
            logger.info(
                "crm_admin check_availability slot_count=%s agent_id=%s",
                len(payload),
                agent_id,
            )

    @staticmethod
    def _crm_admin_domain_instruction(
        *, domain_type: str, custom_domain_instruction: str | None = None
    ) -> str:
        from .admin_booking.domains import get_domain_instruction
        return get_domain_instruction(domain_type, custom_instruction=custom_domain_instruction)

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

    async def _get_admin_booking_payment_api_key(self, *, agent_id: int) -> str | None:
        async with async_session_maker() as session:
            async with session.begin():
                agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
                if not agent or not getattr(agent, "encrypted_booking_payment_api_key", None):
                    return None
                try:
                    return decrypt_booking_payment_secret(agent.encrypted_booking_payment_api_key)
                except Exception:
                    logger.warning("Failed to decrypt booking payment key for agent_id=%s", agent_id)
                    return None

    async def _load_recent_channel_history(
        self,
        *,
        agent_id: int,
        user_external_id: str | None,
        source_channel: str,
        limit: int = 20,
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
                                    AgentAnalyticsMessage.created_at,
                                )
                                .where(
                                    AgentAnalyticsMessage.agent_id == agent_id,
                                    AgentAnalyticsMessage.user_external_id == uid,
                                    AgentAnalyticsMessage.channel == channel,
                                    AgentAnalyticsMessage.role.in_(["user", "agent"]),
                                )
                                .order_by(AgentAnalyticsMessage.created_at.desc())
                                .limit(limit)
                            )
                        )
                        .mappings()
                        .all()
                    )
        except Exception:
            logger.warning("Failed to load recent channel history")
            return []

        history: list[dict[str, Any]] = []
        for row in reversed(rows):
            role = (row.get("role") or "").strip().lower()
            text = (row.get("message_text") or "").strip()
            if role not in {"user", "agent"} or not text:
                continue
            history.append(
                {
                    "role": "assistant" if role == "agent" else "user",
                    "content": text,
                    "created_at": row.get("created_at"),
                }
            )
        return history

    async def _execute_qa_like(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
        agent_id: int | None = None,
        user_external_id: str | None = None,
        source_channel: str | None = None,
        chat_portrait: str | None = None,
        enable_owner_handoff: bool = False,
        enable_smart_search: bool = True,
        enable_chat_history: bool = True,
        runtime_context: dict[str, Any] | None = None,
        template_config: dict[str, Any] | None = None,
    ) -> TemplateExecutionResult:
        cfg = template_config or {}
        chat_model = str(cfg.get("generation_model") or "").strip() or None

        if enable_smart_search:
            context = await search_knowledge_base(
                user_message,
                agent_id=knowledge_scope_id,
                project_id=knowledge_project_id,
            )
        else:
            context = await search_knowledge_base(
                user_message,
                agent_id=knowledge_scope_id,
                project_id=knowledge_project_id,
                limit=6,
                use_smart_search=False,
            )
        context_list = context if isinstance(context, list) else []
        effective_prompt = prompt.strip()
        if enable_owner_handoff:
            effective_prompt = f"{effective_prompt}\n\n{QA_OWNER_HANDOFF_INSTRUCTION}".strip()
        is_phone = bool((runtime_context or {}).get("phone_channel"))
        llm_temperature = 0.48 if is_phone else 0.3

        loaded_history: list[dict[str, Any]] = []
        if enable_chat_history and agent_id and user_external_id and source_channel:
            loaded_history = await self._load_recent_channel_history(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
            )
        memory_context = build_client_memory_block(
            portrait=chat_portrait,
            history=loaded_history,
        )

        answer = await generate_answer_with_context(
            user_message,
            context_list,
            effective_prompt,
            chat_model=chat_model,
            temperature=llm_temperature,
            memory_context=memory_context or None,
        )
        requires_owner_handoff = False
        owner_handoff_reason: str | None = None
        escalation_type = EscalationType.NONE
        if enable_owner_handoff:
            answer, requires_owner_handoff, owner_handoff_reason, escalation_type = self._extract_owner_handoff(answer)

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
            escalation_type=escalation_type,
        )

    @staticmethod
    def _extract_owner_handoff(answer: str) -> tuple[str, bool, str | None, EscalationType]:
        """
        Extract escalation markers from LLM response.

        Returns:
            tuple of (cleaned_answer, requires_handoff, reason, escalation_type)
        """
        text = (answer or "").strip()
        if not text:
            return text, False, None, EscalationType.NONE

        operator_assist_match = re.search(
            r"\[OPERATOR_ASSIST\]\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL
        )
        if operator_assist_match:
            client_part = text[: operator_assist_match.start()].strip()
            reason_text = (operator_assist_match.group(1) or "").strip()
            first_sentence = reason_text.split("\n", 1)[0][:300] if reason_text else "operator_assist_requested"
            client_answer = client_part or CLIENT_OPERATOR_ESCALATION_MESSAGE
            return client_answer, True, first_sentence, EscalationType.NOTIFY_ONLY

        owner_handoff_match = re.search(
            r"\[OWNER_HANDOFF\]\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL
        )
        if owner_handoff_match:
            client_part = text[: owner_handoff_match.start()].strip()
            reason_text = (owner_handoff_match.group(1) or "").strip()
            first_sentence = reason_text.split("\n", 1)[0][:300] if reason_text else "owner_handoff_requested"
            client_answer = client_part or CLIENT_OWNER_HANDOFF_MESSAGE
            return client_answer, True, first_sentence, EscalationType.FREEZE_CHAT

        operator_call_markers = (
            "вызываю оператора",
            "вызываю менеджера",
            "подключаю оператора",
            "подключаю менеджера",
            "свяжусь с менеджером",
            "передаю менеджеру",
            "позову менеджера",
        )
        lowered = text.lower()
        for marker in operator_call_markers:
            if marker in lowered:
                return coerce_client_facing_answer(text, fallback=CLIENT_OPERATOR_ESCALATION_MESSAGE), True, marker, EscalationType.NOTIFY_ONLY

        uncertainty_markers = (
            "не хватает данных",
            "недостаточно данных",
            "нет точной информации",
            "не могу точно ответить",
            "нужен человек",
            "передам владельцу",
            "обратитесь к владельцу",
            "требуется вмешательство",
            "внутренн",
            "системн",
            "недоступно мне",
            "требуется помощь оператора",
            "клиент запрашивает",
        )
        for marker in uncertainty_markers:
            if marker in lowered:
                return CLIENT_OPERATOR_ESCALATION_MESSAGE, True, marker, EscalationType.NOTIFY_ONLY
        return text, False, None, EscalationType.NONE

    async def _execute_content_factory(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
        agent_id: int | None = None,
        user_external_id: str | None = None,
        source_channel: str | None = None,
        chat_portrait: str | None = None,
        runtime_context: dict[str, Any] | None = None,
        template_config: dict[str, Any] | None = None,
    ) -> TemplateExecutionResult:
        decision = get_content_factory_orchestrator().route_incoming_message(user_message=user_message)
        if decision.fallback_to_text_runtime:
            fallback = await self._execute_qa_like(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
                chat_portrait=chat_portrait,
                enable_chat_history=self._is_chat_history_enabled(template_config),
                runtime_context=runtime_context or {},
                template_config=template_config or {},
            )
            fallback.fallback_to_text = True
            fallback.fallback_reason = decision.fallback_reason or "content_factory_runtime_fallback"
            return fallback

        return TemplateExecutionResult(answer=decision.answer, sources=[])

    async def _compose_neuro_channel_comment(
        self,
        *,
        prompt: str,
        post_text: str,
        context_list: list[dict[str, Any]],
        template_config: dict[str, Any],
        runtime_context: dict[str, Any] | None = None,
        source_channel: str | None = None,
    ) -> str:
        """Short public comment for channel posts; no lead qualification."""
        model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        context_text = format_rag_chunks_for_prompt(context_list)
        scenario_addon = build_sales_scenario_system_addon(scenario=SCENARIO_CHANNEL_NEURO_COMMENT)
        system_prompt = f"{prompt}\n\n{SALES_NEURO_COMMENT_INSTRUCTION.format(product_name=product_name, offer_type=offer_type)}"
        if scenario_addon:
            system_prompt = f"{system_prompt}\n\n{scenario_addon}"
        if usp:
            system_prompt = f"{system_prompt}\nУТП (служебно): {usp}"
        message_frame = build_sales_message_frame(
            scenario=SCENARIO_CHANNEL_NEURO_COMMENT,
            user_message=post_text,
            runtime_context=runtime_context,
            source_channel=source_channel,
        )
        user_prompt = build_chat_turn_user_prompt(
            client_message=post_text,
            rag_context_text=context_text,
            extra_internal_blocks=[message_frame] if message_frame else None,
            closing_instruction="Верни только текст комментария под постом.",
        )
        completion = await ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
        )
        content = (completion.choices[0].message.content or "").strip()
        return content.replace("#", "").replace("*", "").strip()[:600]

    async def _execute_sales_manager_neuro_comment(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
        template_config: dict[str, Any],
        source_channel: str,
        user_external_id: str | None,
        runtime_context: dict[str, Any] | None = None,
    ) -> TemplateExecutionResult:
        """Neuro-commenting on channel posts: compose comment only, skip lead pipeline."""
        context_list, sources = await self.retrieve_offer_context(
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
            knowledge_project_id=knowledge_project_id,
            enable_smart_search=self._is_smart_search_enabled(template_config),
        )
        raw_comment = await self._compose_neuro_channel_comment(
            prompt=prompt,
            post_text=user_message,
            context_list=context_list,
            template_config=template_config,
            runtime_context=runtime_context,
            source_channel=source_channel,
        )
        cleaned = self._clean_llm_text(raw_comment)
        if self._is_degenerate_sanitized_answer(cleaned):
            cleaned = "Интересный пост, спасибо за материал."
        event: dict[str, Any] = {
            "tool_name": "sales_neuro_channel_comment",
            "tool_args_hash": None,
            "tool_status": "neuro_comment_composed",
            "latency_ms": 0,
            "crm_provider": None,
            "source_channel": source_channel,
            "user_external_id": mask_external_id(user_external_id),
            "ok": True,
            "idempotent_replay": False,
            "idempotency_key": None,
            "error": None,
        }
        return TemplateExecutionResult(answer=cleaned, sources=sources, tool_events=[event])

    async def _execute_sales_manager(
        self,
        *,
        prompt: str,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
        template_config: dict[str, Any],
        source_channel: str,
        user_external_id: str | None,
        agent_id: int | None = None,
        chat_portrait: str | None = None,
        runtime_context: dict[str, Any] | None = None,
    ) -> TemplateExecutionResult:
        runtime_context = runtime_context or {}
        from .sales.contact_pool import (
            apply_contact_pool_guard,
            register_user_in_agent_contact_pool,
        )

        pool_guard = await apply_contact_pool_guard(
            agent_id=agent_id,
            user_external_id=user_external_id,
            template_config=template_config,
            runtime_context=runtime_context,
            source_channel=source_channel,
        )
        if pool_guard is not None:
            return TemplateExecutionResult(
                answer="",
                sources=[],
                discard_message=True,
                tool_events=[pool_guard],
            )

        if str(template_config.get("custom_runtime") or "").strip().lower() == "ai_mop":
            from .ai_mop.runtime import execute_ai_mop_runtime

            return await execute_ai_mop_runtime(
                prompt=prompt,
                user_message=user_message,
                template_config=template_config,
                source_channel=source_channel,
                user_external_id=user_external_id,
                agent_id=agent_id,
                chat_portrait=chat_portrait,
            )
        if bool(runtime_context.get("is_channel_chat")) and bool(
            runtime_context.get("neuro_commenting_enabled")
        ):
            return await self._execute_sales_manager_neuro_comment(
                prompt=prompt,
                user_message=user_message,
                knowledge_scope_id=knowledge_scope_id,
                knowledge_project_id=knowledge_project_id,
                template_config=template_config,
                source_channel=source_channel,
                user_external_id=user_external_id,
                runtime_context=runtime_context,
            )

        contacts_pool_only = bool(template_config.get("contacts_pool_only"))
        runtime_source_chat_id = str(runtime_context.get("source_chat_id") or "").strip()
        if (
            agent_id
            and user_external_id
            and bool(runtime_context.get("is_group_chat"))
            and not contacts_pool_only
        ):
            await register_user_in_agent_contact_pool(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=runtime_source_chat_id or "global",
                origin="lead_generation",
            )

        contact_key = self._resolve_sales_contact_key(template_config=template_config)
        if agent_id and user_external_id and self._is_userbot_channel(source_channel):
            from .sales.agent_contact_context import resolve_sales_source_chat_id
            from .sales.sales_followup_service import mark_excel_import_reply_if_any

            await mark_excel_import_reply_if_any(
                agent_id=agent_id,
                user_external_id=user_external_id,
            )
            contact_key = await resolve_sales_source_chat_id(
                agent_id=agent_id,
                user_external_id=user_external_id,
                default_source_chat_id=contact_key,
            )
        workflow_completion_mode = self._sales_workflow_completion_mode(template_config)
        lead_score_scale = self._resolve_sales_score_scale(template_config)
        current_sales_state = "DISCOVERED"
        previous_profile: dict[str, Any] | None = None
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
            metadata = await self._load_sales_contact_metadata(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
            )
            if isinstance(metadata.get("lead_profile"), dict):
                previous_profile = metadata.get("lead_profile")
        recent_history: list[dict[str, Any]] = []
        if agent_id and user_external_id:
            recent_history = await self._load_recent_channel_history(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_channel=source_channel,
            )
        if (
            workflow_completion_mode == "auto_finish_on_signal"
            and self._is_sales_terminal_state(current_sales_state)
        ):
            terminal_state = (current_sales_state or "SKIPPED").strip().upper()
            return TemplateExecutionResult(
                answer=(
                    "Диалог уже завершен на предыдущем этапе, "
                    "дополнительный прогрев не требуется."
                ),
                sources=[],
                tool_events=[
                    {
                        "tool_name": "sales_workflow_guard",
                        "tool_args_hash": None,
                        "tool_status": "workflow_finished_noop",
                        "latency_ms": 0,
                        "crm_provider": None,
                        "source_channel": source_channel,
                        "user_external_id": mask_external_id(user_external_id),
                        "ok": True,
                        "idempotent_replay": True,
                        "idempotency_key": None,
                        "error": None,
                        "state": terminal_state,
                    }
                ],
            )
        lead_initiated_private_dialog = bool(runtime_context.get("lead_initiated_private_dialog"))
        sales_scenario = resolve_sales_interaction_scenario(
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        context_list, sources = await self.retrieve_offer_context(
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
            knowledge_project_id=knowledge_project_id,
            enable_smart_search=self._is_smart_search_enabled(template_config),
        )
        if lead_initiated_private_dialog:
            qualification = {
                "decision": "engage",
                "intent": "target_hot",
                "confidence": 1.0,
                "reason": "lead_initiated_private_dialog",
                "lead_temperature": "hot",
                "stage_hint": "discovery",
                "handoff_ready": False,
                "workflow_outcome": "continue",
                "lead_heat_score": 85 if lead_score_scale == 100 else 8.5,
                "resilience_score": 70 if lead_score_scale == 100 else 7.0,
                "engagement_score": 90 if lead_score_scale == 100 else 9.0,
            }
            composed_dm = await self.compose_dm(
                prompt=prompt,
                user_message=user_message,
                qualification=qualification,
                context_list=context_list,
                template_config=template_config,
                chat_portrait=chat_portrait,
                current_sales_state=current_sales_state,
                recent_history=recent_history,
                sales_scenario=sales_scenario,
                runtime_context=runtime_context,
                source_channel=source_channel,
            )
        else:
            unified = await self._qualify_and_compose_unified(
                prompt=prompt,
                user_message=user_message,
                context_list=context_list,
                template_config=template_config,
                chat_portrait=chat_portrait,
                current_sales_state=current_sales_state,
                recent_history=recent_history,
                workflow_completion_mode=workflow_completion_mode,
                lead_score_scale=lead_score_scale,
                sales_scenario=sales_scenario,
                runtime_context=runtime_context,
                source_channel=source_channel,
            )
            qualification = unified["qualification"]
            composed_dm = unified["composed_dm"]

        lead_profile = self._build_sales_lead_profile(
            qualification=qualification,
            previous_profile=previous_profile,
            score_scale=lead_score_scale,
        )
        qualification["lead_profile"] = lead_profile
        if agent_id and user_external_id:
            await self._update_sales_contact_profile(
                agent_id=agent_id,
                user_external_id=user_external_id,
                source_chat_id=contact_key,
                profile=lead_profile,
                qualification=qualification,
            )
        intent = qualification.get("intent", "unsure")
        decision = str(qualification.get("decision") or "ignore").strip().lower()
        workflow_outcome = str(qualification.get("workflow_outcome") or "continue").strip().lower()
        confidence = float(qualification.get("confidence") or 0.0)
        min_confidence = float(template_config.get("min_confidence") or 0.75)

        if decision == "finish":
            if agent_id and user_external_id:
                transition_target = None
                transition_reason = "workflow_finished"
                if current_sales_state == "REPLIED_POSITIVE":
                    transition_target = "HANDOFF_CRM"
                    transition_reason = "sale_closed_signal"
                elif current_sales_state == "SENT":
                    transition_target = "REPLIED_NEGATIVE" if workflow_outcome == "dialog_finished" else "REPLIED_POSITIVE"
                    transition_reason = "dialog_finished_signal"
                elif current_sales_state in {"DISCOVERED", "QUALIFIED", "QUEUED"}:
                    transition_target = "SKIPPED"
                    transition_reason = "dialog_finished_signal"
                if transition_target:
                    await self._transition_sales_state_safe(
                        agent_id=agent_id,
                        user_external_id=user_external_id,
                        source_chat_id=contact_key,
                        to_state=transition_target,
                        reason=transition_reason,
                        metadata={"qualification": qualification},
                    )
            finish_text = (
                "Лид переведен в завершенный статус (продажа/окончание диалога). "
                "Новые прогревающие сообщения отключены."
            )
            return TemplateExecutionResult(
                answer=finish_text,
                sources=[],
                tool_events=[
                    {
                        "tool_name": "sales_workflow_finish",
                        "tool_args_hash": None,
                        "tool_status": "workflow_finished",
                        "latency_ms": 0,
                        "crm_provider": None,
                        "source_channel": source_channel,
                        "user_external_id": mask_external_id(user_external_id),
                        "ok": True,
                        "idempotent_replay": False,
                        "idempotency_key": None,
                        "error": None,
                    }
                ],
            )

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
                    knowledge_project_id=knowledge_project_id,
                    agent_id=agent_id,
                    user_external_id=user_external_id,
                    source_channel=source_channel,
                    chat_portrait=chat_portrait,
                    enable_smart_search=self._is_smart_search_enabled(template_config),
                    enable_chat_history=self._is_chat_history_enabled(template_config),
                    runtime_context=runtime_context,
                    template_config=template_config,
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

        allowed_tools_raw = template_config.get("allowed_tools")
        allowed_tools = allowed_tools_raw if isinstance(allowed_tools_raw, list) else None
        if allowed_tools:
            peer_hash = self._telegram_peer_access_hash_from_runtime(runtime_context)
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
                telegram_peer_access_hash=peer_hash,
                sales_scenario=sales_scenario,
                runtime_context=runtime_context,
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

    @staticmethod
    def _telegram_peer_access_hash_from_runtime(runtime_context: dict[str, Any] | None) -> int | None:
        rc = runtime_context or {}
        raw = rc.get("telegram_peer_access_hash")
        if raw is None:
            return None
        try:
            h = int(raw)
        except (TypeError, ValueError):
            return None
        return h if h != 0 else None

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
        telegram_peer_access_hash: int | None = None,
        sales_scenario: str | None = None,
        runtime_context: dict[str, Any] | None = None,
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
            telegram_peer_access_hash=telegram_peer_access_hash,
            source_channel=source_channel,
        )
        llm_tools = registry.tools_for_llm()
        if not llm_tools:
            return None

        generation_model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        client_memory_section = build_client_memory_system_section(portrait=chat_portrait, history=None)
        scenario = sales_scenario or resolve_sales_interaction_scenario(
            runtime_context=runtime_context,
            source_channel=source_channel,
        )
        scenario_addon = build_sales_scenario_system_addon(scenario=scenario)
        system_prompt = f"{prompt}\n\n{SALES_TOOLS_SYSTEM_INSTRUCTION}"
        if scenario_addon:
            system_prompt = f"{system_prompt}\n\n{scenario_addon}"
        if client_memory_section:
            system_prompt = f"{system_prompt}\n\n{client_memory_section}"
        message_frame = build_sales_message_frame(
            scenario=scenario,
            user_message=user_message,
            runtime_context=runtime_context,
            source_channel=source_channel,
        )
        tool_user_prompt = build_sales_llm_user_prompt(
            scenario=scenario,
            user_message=user_message,
            context_list=None,
            message_frame=message_frame,
            qualification=qualification,
            task_instruction=(
                f"Черновик outreach (служебно): {composed_dm}\n"
                f"Канал (служебно): {source_channel}\n"
                "Выбери подходящий tool call для следующего шага."
            ),
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": tool_user_prompt},
        ]
        tool_events: list[dict[str, Any]] = []
        max_tool_iterations = 2

        for iteration in range(max_tool_iterations):
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
                    tool_result = {
                        "ok": False,
                        "status": "awaiting_user_confirmation",
                        "hint": safe_error,
                    }
                    tool_events.append(
                        {
                            "tool_name": tool_name,
                            "tool_args_hash": None,
                            "tool_status": "awaiting_user_confirmation",
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
            
            if tool_events and iteration < max_tool_iterations - 1:
                has_actionable_tools = any(
                    e.get("tool_name") in {"send_message", "queue_for_approval", "skip_lead"}
                    for e in tool_events
                )
                if has_actionable_tools:
                    break

        if not tool_events:
            return None
        last_status = str(tool_events[-1].get("tool_status") or "")
        if last_status == "sent_auto":
            answer = composed_dm
        elif last_status == "draft_requires_review":
            answer = composed_dm or CLIENT_ACTION_PENDING_MESSAGE
        elif last_status in {"confirmation_required", "awaiting_user_confirmation"}:
            answer = composed_dm or CLIENT_ACTION_PENDING_MESSAGE
        elif last_status.startswith("skipped_"):
            answer = "Лид пропущен согласно policy."
        else:
            answer = composed_dm
        return TemplateExecutionResult(answer=answer, sources=sources, tool_events=tool_events)

    async def _qualify_and_compose_unified(
        self,
        *,
        prompt: str,
        user_message: str,
        context_list: list[dict[str, Any]],
        template_config: dict[str, Any],
        chat_portrait: str | None = None,
        current_sales_state: str = "DISCOVERED",
        recent_history: list[dict[str, Any]] | None = None,
        workflow_completion_mode: str = "auto_finish_on_signal",
        lead_score_scale: int = 100,
        sales_scenario: str | None = None,
        runtime_context: dict[str, Any] | None = None,
        source_channel: str | None = None,
    ) -> dict[str, Any]:
        model = str(template_config.get("qualification_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        client_memory_section = build_client_memory_system_section(
            portrait=chat_portrait,
            history=recent_history,
        )
        scenario = sales_scenario or resolve_sales_interaction_scenario(
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        scenario_addon = build_sales_scenario_system_addon(scenario=scenario)
        state_upper = (current_sales_state or "DISCOVERED").strip().upper()
        stage_hint = "discovery" if state_upper in {"SENT", "REPLIED_POSITIVE", "REPLIED_NEGATIVE", "QUEUED"} else "first_touch"
        stage_instruction = sales_stage_instruction(
            current_sales_state=state_upper,
            stage_hint=stage_hint,
        )

        instruction = f"{prompt}\n\n{SALES_UNIFIED_QUALIFY_INSTRUCTION.format(
            product_name=product_name,
            offer_type=offer_type,
            current_sales_state=state_upper,
            stage_instruction=stage_instruction,
            lead_score_scale=lead_score_scale,
        )}\n\n{CHAT_OPERATOR_PERSONA}\n\n{SALES_HUMAN_FLEXIBILITY_BLOCK}"
        if scenario_addon:
            instruction = f"{instruction}\n\n{scenario_addon}"
        if workflow_completion_mode == "auto_finish_on_signal":
            instruction = f"{instruction}\n{SALES_UNIFIED_FINISH_MODE_ADDON}"
        if client_memory_section:
            instruction = f"{instruction}\n\n{client_memory_section}"
        if usp:
            instruction = f"{instruction}\n\nКлючевое УТП (служебно, не цитировать дословно):\n{usp}"

        message_frame = build_sales_message_frame(
            scenario=scenario,
            user_message=user_message,
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        task_instruction = build_sales_unified_task_instruction(scenario=scenario)
        user_prompt = build_sales_llm_user_prompt(
            scenario=scenario,
            user_message=user_message,
            context_list=context_list,
            message_frame=message_frame,
            task_instruction=task_instruction,
        )

        try:
            completion = await ai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = (completion.choices[0].message.content or "").strip()
            parsed = json.loads(content)
        except Exception:
            logger.exception("sales_manager unified qualify+compose failed, fallback to safe defaults")
            parsed = {}

        decision = str(parsed.get("decision") or "ignore").strip().lower()
        if decision not in {"engage", "ignore", "finish"}:
            decision = "ignore"
        intent = str(parsed.get("intent") or "unsure").strip().lower()
        allowed_intents = {"target_hot", "target_warm", "non_target", "do_not_contact", "unsure", "workflow_completed"}
        if intent not in allowed_intents:
            intent = "unsure"
        try:
            confidence = float(parsed.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        reason = str(parsed.get("reason") or "").strip()[:500]
        lead_temperature = str(parsed.get("lead_temperature") or "warm").strip().lower()
        if lead_temperature not in {"cold", "warm", "hot"}:
            lead_temperature = "warm"
        stage_hint = str(parsed.get("stage_hint") or "first_touch").strip().lower()
        if stage_hint not in {"first_touch", "discovery", "value_pitch", "handoff"}:
            stage_hint = "first_touch"
        workflow_outcome = str(parsed.get("workflow_outcome") or "continue").strip().lower()
        if workflow_outcome not in {"continue", "sale_closed", "dialog_finished"}:
            workflow_outcome = "continue"
        lead_heat_score = self._normalize_model_score(
            parsed.get("lead_heat_score"),
            score_scale=lead_score_scale,
            default_0_100=self._default_heat_score_from_temperature(lead_temperature),
        )
        resilience_score = self._normalize_model_score(
            parsed.get("resilience_score"),
            score_scale=lead_score_scale,
            default_0_100=55.0,
        )
        engagement_score = self._normalize_model_score(
            parsed.get("engagement_score"),
            score_scale=lead_score_scale,
            default_0_100=confidence * 100.0,
        )
        composed_message = str(parsed.get("composed_message") or "").replace("#", "").replace("*", "").strip()
        if not composed_message:
            composed_message = SALES_COMPOSED_MESSAGE_FALLBACK

        qualification = {
            "decision": decision,
            "intent": intent,
            "confidence": confidence,
            "reason": reason,
            "lead_temperature": lead_temperature,
            "stage_hint": stage_hint,
            "handoff_ready": bool(parsed.get("handoff_ready")),
            "workflow_outcome": workflow_outcome,
            "lead_heat_score": self._to_display_score(lead_heat_score, score_scale=lead_score_scale),
            "resilience_score": self._to_display_score(resilience_score, score_scale=lead_score_scale),
            "engagement_score": self._to_display_score(engagement_score, score_scale=lead_score_scale),
        }
        return {
            "qualification": qualification,
            "composed_dm": composed_message[:1200],
        }

    async def qualify_message(
        self,
        *,
        prompt: str,
        user_message: str,
        template_config: dict[str, Any],
        chat_portrait: str | None = None,
        current_sales_state: str = "DISCOVERED",
        recent_history: list[dict[str, Any]] | None = None,
        workflow_completion_mode: str = "auto_finish_on_signal",
        lead_score_scale: int = 100,
        sales_scenario: str | None = None,
        runtime_context: dict[str, Any] | None = None,
        source_channel: str | None = None,
    ) -> dict[str, Any]:
        model = str(template_config.get("qualification_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        client_memory_section = build_client_memory_system_section(
            portrait=chat_portrait,
            history=recent_history,
        )
        scenario = sales_scenario or resolve_sales_interaction_scenario(
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        scenario_addon = build_sales_scenario_system_addon(scenario=scenario)
        instruction = f"{prompt}\n\n{SALES_PRE_SALES_SCREENING_INSTRUCTION.format(
            product_name=product_name,
            offer_type=offer_type,
            current_sales_state=(current_sales_state or 'DISCOVERED').strip().upper(),
        )}"
        if scenario_addon:
            instruction = f"{instruction}\n\n{scenario_addon}"
        if workflow_completion_mode == "auto_finish_on_signal":
            instruction = f"{instruction}\n{SALES_PRE_SALES_FINISH_MODE_ADDON}"
        instruction = f"{instruction}\n{SALES_PRE_SALES_SCORING_ADDON.format(lead_score_scale=lead_score_scale)}"
        max_score = 10 if lead_score_scale == 10 else 100
        if client_memory_section:
            instruction = f"{instruction}\n\n{client_memory_section}"
        if usp:
            instruction = f"{instruction}\n\nКлючевое УТП:\n{usp}"
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
                            "lead_heat_score": {"type": "number", "minimum": 0, "maximum": max_score},
                            "resilience_score": {"type": "number", "minimum": 0, "maximum": max_score},
                            "engagement_score": {"type": "number", "minimum": 0, "maximum": max_score},
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
        if workflow_completion_mode == "auto_finish_on_signal":
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "finish_workflow",
                        "description": "Завершить sales-воркфлоу: продажа закрыта или диалог окончательно завершен.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "intent": {"type": "string", "enum": ["workflow_completed"]},
                                "confidence": {"type": "number"},
                                "reason": {"type": "string"},
                                "workflow_outcome": {"type": "string", "enum": ["sale_closed", "dialog_finished"]},
                            },
                            "required": ["intent", "confidence", "reason", "workflow_outcome"],
                        },
                    },
                }
            )
        message_frame = build_sales_message_frame(
            scenario=scenario,
            user_message=user_message,
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        screening_task = build_sales_unified_task_instruction(scenario=scenario)
        screening_user_prompt = build_sales_llm_user_prompt(
            scenario=scenario,
            user_message=user_message,
            context_list=None,
            message_frame=message_frame,
            task_instruction=screening_task,
        )
        completion = await ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": screening_user_prompt},
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
            if tool_name == "engage_lead":
                decision = "engage"
            elif tool_name == "finish_workflow":
                decision = "finish"
            else:
                decision = "ignore"
            lead_temperature = str(payload.get("lead_temperature") or "warm").strip().lower()
            if lead_temperature not in {"cold", "warm", "hot"}:
                lead_temperature = "warm"
            stage_hint = str(payload.get("stage_hint") or "first_touch").strip().lower()
            if stage_hint not in {"first_touch", "discovery", "value_pitch", "handoff"}:
                stage_hint = "first_touch"
            workflow_outcome = str(payload.get("workflow_outcome") or "continue").strip().lower()
            if workflow_outcome not in {"continue", "sale_closed", "dialog_finished"}:
                workflow_outcome = "continue"
            lead_heat_score = self._normalize_model_score(
                payload.get("lead_heat_score"),
                score_scale=lead_score_scale,
                default_0_100=self._default_heat_score_from_temperature(lead_temperature),
            )
            resilience_score = self._normalize_model_score(
                payload.get("resilience_score"),
                score_scale=lead_score_scale,
                default_0_100=55.0,
            )
            engagement_score = self._normalize_model_score(
                payload.get("engagement_score"),
                score_scale=lead_score_scale,
                default_0_100=confidence * 100.0,
            )
            return {
                "decision": decision,
                "intent": intent,
                "confidence": confidence,
                "reason": reason,
                "lead_temperature": lead_temperature,
                "stage_hint": stage_hint,
                "handoff_ready": bool(payload.get("handoff_ready")),
                "workflow_outcome": workflow_outcome,
                "lead_heat_score": self._to_display_score(lead_heat_score, score_scale=lead_score_scale),
                "resilience_score": self._to_display_score(resilience_score, score_scale=lead_score_scale),
                "engagement_score": self._to_display_score(engagement_score, score_scale=lead_score_scale),
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
                "workflow_outcome": "continue",
                "lead_heat_score": self._to_display_score(40.0, score_scale=lead_score_scale),
                "resilience_score": self._to_display_score(50.0, score_scale=lead_score_scale),
                "engagement_score": self._to_display_score(25.0, score_scale=lead_score_scale),
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
            "workflow_outcome": "continue",
            "lead_heat_score": self._to_display_score(55.0, score_scale=lead_score_scale),
            "resilience_score": self._to_display_score(50.0, score_scale=lead_score_scale),
            "engagement_score": self._to_display_score(confidence * 100.0, score_scale=lead_score_scale),
        }

    async def retrieve_offer_context(
        self,
        *,
        user_message: str,
        knowledge_scope_id: int,
        knowledge_project_id: int | None = None,
        enable_smart_search: bool = True,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if enable_smart_search:
            context = await search_knowledge_base(
                user_message,
                agent_id=knowledge_scope_id,
                project_id=knowledge_project_id,
            )
        else:
            context = await search_knowledge_base(
                user_message,
                agent_id=knowledge_scope_id,
                project_id=knowledge_project_id,
                limit=6,
                use_smart_search=False,
            )
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
        sales_scenario: str | None = None,
        runtime_context: dict[str, Any] | None = None,
        source_channel: str | None = None,
        interaction_hint: str | None = None,
    ) -> str:
        model = str(template_config.get("generation_model") or "deepseek-chat").strip() or "deepseek-chat"
        product_name = str(template_config.get("sales_product_name") or "ваш продукт").strip() or "ваш продукт"
        offer_type = str(template_config.get("sales_offer_type") or "услуга").strip() or "услуга"
        usp = str(template_config.get("sales_usp") or "").strip()
        stage_hint = str(qualification.get("stage_hint") or "first_touch").strip().lower()
        lead_profile_block = self._format_sales_lead_profile(qualification.get("lead_profile"))
        client_memory_section = build_client_memory_system_section(
            portrait=chat_portrait,
            history=recent_history,
        )
        stage_instruction = sales_stage_instruction(
            current_sales_state=(current_sales_state or "DISCOVERED").strip().upper(),
            stage_hint=stage_hint,
        )
        scenario = sales_scenario or resolve_sales_interaction_scenario(
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
            interaction_hint=interaction_hint,
        )
        scenario_addon = build_sales_scenario_system_addon(scenario=scenario)

        system_prompt = f"{prompt}\n\n{SALES_DM_COMPOSE_INSTRUCTION.format(
            product_name=product_name,
            offer_type=offer_type,
            current_sales_state=(current_sales_state or 'DISCOVERED').strip().upper(),
            stage_instruction=stage_instruction,
        )}"
        if scenario_addon:
            system_prompt = f"{system_prompt}\n\n{scenario_addon}"
        if client_memory_section:
            system_prompt = f"{system_prompt}\n\n{client_memory_section}"
        if lead_profile_block:
            system_prompt = f"{system_prompt}\n\n{lead_profile_block}"
        if usp:
            system_prompt = f"{system_prompt}\n\nКлючевое УТП (служебно, не цитировать дословно):\n{usp}"
        message_frame = build_sales_message_frame(
            scenario=scenario,
            user_message=user_message,
            runtime_context=runtime_context,
            source_channel=source_channel,
            current_sales_state=current_sales_state,
        )
        action_instruction = build_sales_compose_action_instruction(scenario=scenario)
        user_prompt = build_sales_llm_user_prompt(
            scenario=scenario,
            user_message=user_message,
            context_list=context_list,
            message_frame=message_frame,
            qualification=qualification,
            task_instruction=action_instruction,
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
            answer = composed_dm
        elif mode == "semi_auto":
            reason_code = "draft_requires_review"
            answer = composed_dm or CLIENT_ACTION_PENDING_MESSAGE
        else:
            reason_code = "draft_requires_review"
            answer = composed_dm or CLIENT_ACTION_PENDING_MESSAGE

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
            "lead_profile": qualification.get("lead_profile"),
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

    async def _load_sales_contact_metadata(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
    ) -> dict[str, Any]:
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = await session.scalar(
                        select(AgentSalesContact.metadata_json).where(
                            AgentSalesContact.agent_id == agent_id,
                            AgentSalesContact.user_external_id == user_external_id,
                            AgentSalesContact.source_chat_id == source_chat_id,
                        )
                    )
            if not row:
                return {}
            loaded = json.loads(row)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            logger.warning("sales_manager failed to load contact metadata")
            return {}

    async def _update_sales_contact_profile(
        self,
        *,
        agent_id: int,
        user_external_id: str,
        source_chat_id: str,
        profile: dict[str, Any],
        qualification: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    row = await session.scalar(
                        select(AgentSalesContact)
                        .where(
                            AgentSalesContact.agent_id == agent_id,
                            AgentSalesContact.user_external_id == user_external_id,
                            AgentSalesContact.source_chat_id == source_chat_id,
                        )
                        .with_for_update()
                    )
                    if row is None:
                        return
                    metadata: dict[str, Any] = {}
                    if row.metadata_json:
                        try:
                            loaded = json.loads(row.metadata_json)
                            if isinstance(loaded, dict):
                                metadata = loaded
                        except Exception:
                            metadata = {}
                    metadata["lead_profile"] = profile
                    metadata["last_qualification"] = {
                        "decision": qualification.get("decision"),
                        "intent": qualification.get("intent"),
                        "confidence": qualification.get("confidence"),
                        "reason": qualification.get("reason"),
                        "workflow_outcome": qualification.get("workflow_outcome"),
                    }
                    metadata["lead_profile_updated_at"] = now.isoformat()
                    row.metadata_json = json.dumps(metadata, ensure_ascii=False)
                    row.updated_at = now
                    row.version = int(row.version or 1) + 1
                    await session.flush()
        except Exception:
            logger.warning("sales_manager failed to persist lead profile")

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
