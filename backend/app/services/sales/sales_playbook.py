"""Реэкспорт sales-промптов из единого реестра (обратная совместимость)."""

from ...prompts.system_prompts import (
    EXCEL_COLD_OUTREACH_EXTRA,
    FOLLOW_UP_TIER_HINTS,
    SALES_HUMAN_FLEXIBILITY_BLOCK,
)

__all__ = [
    "EXCEL_COLD_OUTREACH_EXTRA",
    "FOLLOW_UP_TIER_HINTS",
    "SALES_HUMAN_FLEXIBILITY_BLOCK",
]
