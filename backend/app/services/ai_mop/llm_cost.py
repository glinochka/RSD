"""Учёт токенов и стоимости LLM для лидов ИИ МОП."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopLead
from ...config import settings
from ..ai_authoring import ai_client

logger = logging.getLogger(__name__)

_current_lead_id: ContextVar[int | None] = ContextVar("ai_mop_llm_lead_id", default=None)

CNY_MICROS = 1_000_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pricing_for_model(model: str) -> tuple[float, float, float]:
    """Возвращает (input_cny_per_mtok, output_cny_per_mtok, cache_hit_cny_per_mtok)."""
    normalized = (model or "").strip().lower()
    if "coder" in normalized:
        return (
            float(settings.AI_MOP_LLM_CODER_INPUT_CNY_PER_MTOK),
            float(settings.AI_MOP_LLM_CODER_OUTPUT_CNY_PER_MTOK),
            float(settings.AI_MOP_LLM_CACHE_HIT_CNY_PER_MTOK),
        )
    return (
        float(settings.AI_MOP_LLM_INPUT_CNY_PER_MTOK),
        float(settings.AI_MOP_LLM_OUTPUT_CNY_PER_MTOK),
        float(settings.AI_MOP_LLM_CACHE_HIT_CNY_PER_MTOK),
    )


def extract_usage_counts(usage: Any) -> tuple[int, int, int]:
    """(prompt_tokens, completion_tokens, cache_hit_tokens)."""
    if usage is None:
        return 0, 0, 0
    prompt = int(getattr(usage, "prompt_tokens", None) or 0)
    completion = int(getattr(usage, "completion_tokens", None) or 0)
    cache_hit = int(getattr(usage, "prompt_cache_hit_tokens", None) or 0)
    if cache_hit < 0:
        cache_hit = 0
    if cache_hit > prompt:
        cache_hit = prompt
    return prompt, completion, cache_hit


def compute_cost_cny_micros(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int,
    model: str,
) -> int:
    input_rate, output_rate, cache_rate = _pricing_for_model(model)
    miss_tokens = max(0, prompt_tokens - cache_hit_tokens)
    cost_cny = (
        miss_tokens * input_rate / 1_000_000
        + cache_hit_tokens * cache_rate / 1_000_000
        + completion_tokens * output_rate / 1_000_000
    )
    return max(0, int(round(cost_cny * CNY_MICROS)))


def cny_micros_to_rub(micros: int) -> float:
    return (micros / CNY_MICROS) * float(settings.AI_MOP_CNY_TO_RUB_RATE)


def cny_micros_to_cny(micros: int) -> float:
    return micros / CNY_MICROS


@asynccontextmanager
async def ai_mop_lead_llm_scope(lead_id: int):
    token = _current_lead_id.set(int(lead_id))
    try:
        yield
    finally:
        _current_lead_id.reset(token)


async def record_completion_usage(response: Any, *, model: str) -> None:
    lead_id = _current_lead_id.get()
    if lead_id is None:
        return
    usage = getattr(response, "usage", None)
    prompt_tokens, completion_tokens, cache_hit = extract_usage_counts(usage)
    if prompt_tokens == 0 and completion_tokens == 0:
        return
    delta_cost = compute_cost_cny_micros(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_hit_tokens=cache_hit,
        model=model,
    )
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, int(lead_id))
            if lead is None:
                return
            lead.llm_prompt_tokens = int(lead.llm_prompt_tokens or 0) + prompt_tokens
            lead.llm_completion_tokens = int(lead.llm_completion_tokens or 0) + completion_tokens
            lead.llm_cost_cny_micros = int(lead.llm_cost_cny_micros or 0) + delta_cost
            lead.updated_at = _utc_now()


async def ai_mop_chat_completion(**kwargs: Any) -> Any:
    model = str(kwargs.get("model") or "deepseek-chat")
    response = await ai_client.chat.completions.create(**kwargs)
    await record_completion_usage(response, model=model)
    return response


async def aggregate_llm_cost_stats() -> dict[str, Any]:
    """Средняя стоимость лида по лидам с зафиксированным расходом токенов."""
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(AiMopLead.llm_cost_cny_micros).where(AiMopLead.llm_cost_cny_micros > 0)
            )
        ).all()
    costs = [int(row[0]) for row in rows if row and row[0]]
    if not costs:
        return {
            "leads_with_usage": 0,
            "avg_cost_cny": 0.0,
            "avg_cost_rub": 0.0,
            "total_cost_cny": 0.0,
            "total_cost_rub": 0.0,
        }
    total_micros = sum(costs)
    count = len(costs)
    avg_micros = total_micros / count
    return {
        "leads_with_usage": count,
        "avg_cost_cny": round(cny_micros_to_cny(int(round(avg_micros))), 4),
        "avg_cost_rub": round(cny_micros_to_rub(int(round(avg_micros))), 2),
        "total_cost_cny": round(cny_micros_to_cny(total_micros), 2),
        "total_cost_rub": round(cny_micros_to_rub(total_micros), 2),
    }
