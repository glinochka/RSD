"""Инструменты кастомного рантайма ИИ МОП."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopLead, Website, WebsiteBlock
from ...router_websites.dao import WebsiteBlockDAO, WebsiteDAO
from ..website_generation_service import get_website_generation_service
from ..website_sanitization_service import get_website_sanitization_service
from .lead_lookup import credentials_already_sent, mark_credentials_sent

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL_SECONDS = 120
_IDEMPOTENCY_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}


class _SendDemoCredentialsArgs(BaseModel):
    pass


class _EditDemoWebsiteArgs(BaseModel):
    edit_prompt: str = Field(..., min_length=3, max_length=2000)


_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "send_demo_credentials": _SendDemoCredentialsArgs,
    "edit_demo_website": _EditDemoWebsiteArgs,
}

_TOOL_DESCRIPTIONS = {
    "send_demo_credentials": (
        "Отправить клиенту ссылку на личный кабинет, логин и временный пароль. "
        "Используй, когда клиент заинтересовался доступом или явно просит данные для входа."
    ),
    "edit_demo_website": (
        "Внести правки в демо-сайт клиента по текстовому описанию (цвета, тексты, блоки). "
        "Используй, когда клиент просит изменить внешний вид или содержимое сайта."
    ),
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cleanup_idempotency_cache() -> None:
    now = _now_utc()
    expired = [key for key, (expires_at, _) in _IDEMPOTENCY_CACHE.items() if expires_at <= now]
    for key in expired:
        _IDEMPOTENCY_CACHE.pop(key, None)


class AiMopToolRegistry:
    def __init__(
        self,
        *,
        allowed_tools: list[str] | None,
        agent_id: int,
        user_external_id: str,
        lead: AiMopLead,
    ) -> None:
        requested = [str(tool or "").strip() for tool in (allowed_tools or [])]
        unique: list[str] = []
        for tool in requested:
            if tool and tool in _TOOL_MODELS and tool not in unique:
                unique.append(tool)
        self._allowed_tools = unique or list(_TOOL_MODELS.keys())
        self._agent_id = int(agent_id)
        self._user_external_id = (user_external_id or "").strip() or "anonymous"
        self._lead = lead

    def tools_for_llm(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for name in self._allowed_tools:
            model = _TOOL_MODELS[name]
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": _TOOL_DESCRIPTIONS[name],
                        "parameters": model.model_json_schema(),
                    },
                }
            )
        return tools

    @staticmethod
    def _canonical_args(model: BaseModel) -> str:
        return json.dumps(model.model_dump(), ensure_ascii=False, sort_keys=True)

    def _idempotency_key(self, tool_name: str, canonical_args: str) -> str:
        raw = f"{self._agent_id}:{self._user_external_id}:{self._lead.id}:{tool_name}:{canonical_args}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _tool_args_hash(canonical_args: str) -> str:
        return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    async def execute_tool(self, tool_name: str, raw_arguments: str) -> dict[str, Any]:
        if tool_name not in self._allowed_tools:
            raise RuntimeError(f"Tool '{tool_name}' is not allowed")

        model_type = _TOOL_MODELS.get(tool_name)
        if not model_type:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        try:
            payload = json.loads(raw_arguments or "{}")
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON arguments for tool '{tool_name}': {exc}") from None

        try:
            args = model_type.model_validate(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Validation failed for tool '{tool_name}': {exc}") from None

        canonical_args = self._canonical_args(args)
        tool_args_hash = self._tool_args_hash(canonical_args)
        _cleanup_idempotency_cache()
        idempotency_key = self._idempotency_key(tool_name, canonical_args)
        cached = _IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached:
            _, value = cached
            return {
                "ok": True,
                "tool_name": tool_name,
                "tool_args_hash": tool_args_hash,
                "tool_status": value.get("status", "success"),
                "latency_ms": 0,
                "idempotent_replay": True,
                "idempotency_key": idempotency_key,
                "result": value,
            }

        started = time.perf_counter()
        if tool_name == "send_demo_credentials":
            result = await self._send_demo_credentials()
        elif tool_name == "edit_demo_website":
            result = await self._edit_demo_website(args.edit_prompt)
        else:
            raise RuntimeError(f"Tool '{tool_name}' is not implemented")

        latency_ms = int((time.perf_counter() - started) * 1000)
        _IDEMPOTENCY_CACHE[idempotency_key] = (
            _now_utc() + timedelta(seconds=_IDEMPOTENCY_TTL_SECONDS),
            result,
        )
        return {
            "ok": True,
            "tool_name": tool_name,
            "tool_args_hash": tool_args_hash,
            "tool_status": result.get("status", "success"),
            "latency_ms": latency_ms,
            "idempotent_replay": False,
            "idempotency_key": idempotency_key,
            "result": result,
        }

    async def _send_demo_credentials(self) -> dict[str, Any]:
        lead = self._lead
        if not lead.website_url or not lead.email or not lead.temp_password:
            return {
                "status": "error",
                "message": "Данные доступа для лида ещё не готовы",
            }
        if credentials_already_sent(lead):
            return {
                "status": "already_sent",
                "website_url": lead.website_url,
                "login_email": lead.email,
                "temp_password": lead.temp_password,
                "message": "Данные для входа уже отправлялись ранее — можно повторить по запросу клиента",
            }

        await mark_credentials_sent(lead_id=int(lead.id))
        return {
            "status": "credentials_ready",
            "website_url": lead.website_url,
            "login_email": lead.email,
            "temp_password": lead.temp_password,
            "message": (
                "Передай клиенту ссылку на сайт, email для входа и временный пароль. "
                "Формулировка — спокойная и деловая, без давления."
            ),
        }

    async def _edit_demo_website(self, edit_prompt: str) -> dict[str, Any]:
        website_id = self._lead.provisioned_website_id
        if not website_id:
            return {"status": "error", "message": "Демо-сайт для лида не найден"}

        async with async_session_maker() as session:
            website_dao = WebsiteDAO(session)
            block_dao = WebsiteBlockDAO(session)
            website = await website_dao.find_one_by_filter(id=int(website_id))
            if website is None:
                return {"status": "error", "message": "Сайт не найден в базе"}

            blocks = await block_dao.list_by_website(int(website_id), only_visible=False)
            block = next((b for b in blocks if b.type == "fullpage"), None)
            if block is None:
                return {"status": "error", "message": "На сайте нет fullpage-блока для редактирования"}

            current_html = (block.content or {}).get("html", "")
            if not current_html:
                return {"status": "error", "message": "У сайта нет HTML-контента"}

            service = get_website_generation_service()
            sanitization = get_website_sanitization_service()
            try:
                edited_html = await service.edit_website_with_prompt(
                    current_html=current_html,
                    prompt=edit_prompt.strip(),
                    business_name=website.title or self._lead.org_name,
                )
            except Exception as exc:
                logger.warning("AI MOP website edit failed lead_id=%s: %s", self._lead.id, exc)
                return {"status": "error", "message": f"Не удалось применить правки: {exc}"}

            sanitized_html = sanitization.sanitize_fullpage_html(edited_html)
            async with session.begin():
                fresh_block = await session.get(WebsiteBlock, block.id)
                fresh_website = await session.get(Website, website.id)
                if fresh_block is None or fresh_website is None:
                    return {"status": "error", "message": "Сайт изменился во время редактирования"}
                content = dict(fresh_block.content or {})
                content["html"] = sanitized_html
                fresh_block.content = content
                fresh_block.updated_at = _now_utc()
                fresh_website.updated_at = _now_utc()

        website_url = self._lead.website_url or ""
        return {
            "status": "edited",
            "website_url": website_url,
            "message": "Правки применены. Сообщи клиенту, что сайт обновлён, и предложи посмотреть ещё раз.",
        }
