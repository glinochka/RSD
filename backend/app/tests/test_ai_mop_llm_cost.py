"""Тесты учёта стоимости LLM ИИ МОП."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ai_mop.llm_cost import (
    CNY_MICROS,
    compute_cost_cny_micros,
    cny_micros_to_rub,
    extract_usage_counts,
)


def test_extract_usage_counts_with_cache_hit():
    usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=500, prompt_cache_hit_tokens=400)
    prompt, completion, cache_hit = extract_usage_counts(usage)
    assert prompt == 1000
    assert completion == 500
    assert cache_hit == 400


def test_compute_cost_cny_micros():
    micros = compute_cost_cny_micros(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        cache_hit_tokens=0,
        model="deepseek-chat",
    )
    # 1M input @ 1 CNY + 1M output @ 2 CNY = 3 CNY
    assert micros == 3 * CNY_MICROS


def test_cny_micros_to_rub(monkeypatch):
    monkeypatch.setattr("app.services.ai_mop.llm_cost.settings.AI_MOP_CNY_TO_RUB_RATE", 12.0)
    assert cny_micros_to_rub(CNY_MICROS) == 12.0


@pytest.mark.asyncio
async def test_record_completion_usage_accumulates(monkeypatch):
    from app.services.ai_mop import llm_cost as mod

    class _Lead:
        llm_prompt_tokens = 0
        llm_completion_tokens = 0
        llm_cost_cny_micros = 0
        updated_at = None

    lead = _Lead()

    class _Session:
        async def get(self, model, lead_id):
            return lead

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def begin(self):
            return self

    class _Maker:
        def __call__(self):
            return _Session()

    monkeypatch.setattr(mod, "async_session_maker", _Maker())
    token = mod._current_lead_id.set(42)
    try:
        response = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, prompt_cache_hit_tokens=0)
        )
        await mod.record_completion_usage(response, model="deepseek-chat")
    finally:
        mod._current_lead_id.reset(token)

    assert lead.llm_prompt_tokens == 100
    assert lead.llm_completion_tokens == 50
    assert lead.llm_cost_cny_micros > 0
