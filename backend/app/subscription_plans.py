from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any


UNLIMITED_KNOWLEDGE_BASE_CHUNKS = None

# Default plans. Admin can override editable fields (price/limits) via JSON file.
DEFAULT_SUBSCRIPTION_PLANS: tuple[dict, ...] = (
    {
        "code": "Free",
        "title": "Базовый (Free)",
        "max_active_agents": 1,
        "knowledge_base_chunk_limit": 100,
        "price_rub_month": 0,
        "telegram_amount_kopecks": 0,
        "telegram_invoice_description": "1 активный агент и лимит базы знаний 100 чанков на 30 дней.",
        "is_paid": False,
    },
    {
        "code": "Advanced",
        "title": "Продвинутый (Advanced)",
        "max_active_agents": 5,
        "knowledge_base_chunk_limit": 500,
        "price_rub_month": 1990,
        "telegram_amount_kopecks": 199_000,
        "telegram_invoice_description": "До 5 активных агентов и лимит базы знаний 500 чанков на 30 дней.",
        "is_paid": True,
    },
    {
        "code": "Pro",
        "title": "Pro",
        "max_active_agents": 20,
        "knowledge_base_chunk_limit": UNLIMITED_KNOWLEDGE_BASE_CHUNKS,
        "price_rub_month": 9990,
        "telegram_amount_kopecks": 999_000,
        "telegram_invoice_description": "До 20 активных агентов и безлимитная база знаний на 30 дней.",
        "is_paid": True,
    },
)

_OVERRIDE_FILE_PATH = Path(__file__).with_name("subscription_plans.override.json")
_ALLOWED_PLAN_CODES = {plan["code"] for plan in DEFAULT_SUBSCRIPTION_PLANS}


def _build_telegram_invoice_description(
    *, code: str, max_active_agents: int, knowledge_base_chunk_limit: int | None
) -> str:
    if code == "Free":
        kb_part = (
            "безлимитная база знаний"
            if knowledge_base_chunk_limit is UNLIMITED_KNOWLEDGE_BASE_CHUNKS
            else f"лимит базы знаний {int(knowledge_base_chunk_limit)} чанков"
        )
        return f"{int(max_active_agents)} активный агент и {kb_part} на 30 дней."

    if knowledge_base_chunk_limit is UNLIMITED_KNOWLEDGE_BASE_CHUNKS:
        return f"До {int(max_active_agents)} активных агентов и безлимитная база знаний на 30 дней."
    return (
        f"До {int(max_active_agents)} активных агентов и лимит базы знаний {int(knowledge_base_chunk_limit)} чанков на 30 дней."
    )


def _read_overrides() -> dict[str, dict[str, Any]]:
    if not _OVERRIDE_FILE_PATH.exists():
        return {}
    try:
        raw = json.loads(_OVERRIDE_FILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}

    overrides: dict[str, dict[str, Any]] = {}
    for code, data in raw.items():
        if code in _ALLOWED_PLAN_CODES and isinstance(data, dict):
            overrides[code] = data
    return overrides


def _apply_overrides(overrides: dict[str, dict[str, Any]]) -> tuple[dict, ...]:
    plans: list[dict] = []
    for base in DEFAULT_SUBSCRIPTION_PLANS:
        plan = dict(base)
        code = plan.get("code")
        upd = overrides.get(code, {})

        if "max_active_agents" in upd:
            plan["max_active_agents"] = int(upd.get("max_active_agents") or 0)
        if "knowledge_base_chunk_limit" in upd:
            kb_val = upd.get("knowledge_base_chunk_limit")
            plan["knowledge_base_chunk_limit"] = None if kb_val is None else int(kb_val)
        if "price_rub_month" in upd:
            plan["price_rub_month"] = int(upd.get("price_rub_month") or 0)

        # Keep telegram fields consistent with edited price/limits.
        plan["telegram_amount_kopecks"] = int(plan.get("price_rub_month", 0) or 0) * 100
        plan["telegram_invoice_description"] = _build_telegram_invoice_description(
            code=plan["code"],
            max_active_agents=int(plan.get("max_active_agents") or 0),
            knowledge_base_chunk_limit=plan.get("knowledge_base_chunk_limit"),
        )

        plans.append(plan)

    return tuple(plans)


def _reload_subscription_plans() -> None:
    global SUBSCRIPTION_PLANS
    SUBSCRIPTION_PLANS = _apply_overrides(_read_overrides())


SUBSCRIPTION_PLANS: tuple[dict, ...] = ()
_reload_subscription_plans()


def get_all_subscription_plans() -> list[dict]:
    return [dict(plan) for plan in SUBSCRIPTION_PLANS]


def get_paid_subscription_plans() -> list[dict]:
    return [plan for plan in get_all_subscription_plans() if plan["is_paid"]]


def get_subscription_plan(plan_code: str) -> dict | None:
    for plan in SUBSCRIPTION_PLANS:
        if plan["code"] == plan_code:
            return dict(plan)
    return None


def get_subscription_plan_codes(*, paid_only: bool = False) -> set[str]:
    plans: Iterable[dict] = SUBSCRIPTION_PLANS
    if paid_only:
        plans = (plan for plan in SUBSCRIPTION_PLANS if plan["is_paid"])
    return {plan["code"] for plan in plans}


def update_subscription_plan_overrides(*, plan_updates: list[dict[str, Any]]) -> None:
    """
    Persist edited fields to JSON and update in-memory plans immediately.
    plan_updates elements must contain:
      - code: str
      - price_rub_month: int
      - max_active_agents: int
      - knowledge_base_chunk_limit: int | None
    """
    overrides: dict[str, dict[str, Any]] = {}
    for upd in plan_updates:
        code = upd.get("code")
        if code not in _ALLOWED_PLAN_CODES:
            continue

        overrides[str(code)] = {
            "price_rub_month": int(upd.get("price_rub_month") or 0),
            "max_active_agents": int(upd.get("max_active_agents") or 0),
            "knowledge_base_chunk_limit": upd.get("knowledge_base_chunk_limit"),
        }

    tmp_path = _OVERRIDE_FILE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(_OVERRIDE_FILE_PATH)
    _reload_subscription_plans()
