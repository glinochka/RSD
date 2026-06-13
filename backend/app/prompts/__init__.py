"""Централизованные промпты для LLM."""

from .system_prompts import (
    DEFAULT_AGENT_SYSTEM_PROMPT,
    apply_phone_style_instructions,
    sales_stage_instruction,
)

__all__ = [
    "DEFAULT_AGENT_SYSTEM_PROMPT",
    "apply_phone_style_instructions",
    "sales_stage_instruction",
]
