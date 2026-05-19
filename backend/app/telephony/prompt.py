"""Voice-specific prompt adjustments."""

from __future__ import annotations

_PHONE_STYLE_SUFFIX = (
    "\n\n[Голосовой канал — телефон]\n"
    "- Отвечай коротко: 1–3 предложения, без markdown, списков и эмодзи.\n"
    "- Тон: спокойный, дружелюбный оператор (neutral-friendly), не «радиоведущий».\n"
    "- Задавай не больше одного уточняющего вопроса за раз.\n"
    "- При переводе на человека скажи явно: «Сейчас соединю с оператором».\n"
    "- Номера времени и телефоны произноси разборчиво (например: «пятнадцать ноль-ноль»).\n"
)


def apply_phone_style_instructions(base_prompt: str, *, state_addon: str = "") -> str:
    prompt = (base_prompt or "").strip()
    if not prompt:
        prompt = ""
    if "[Голосовой канал" not in prompt:
        prompt = (prompt + _PHONE_STYLE_SUFFIX).strip() if prompt else _PHONE_STYLE_SUFFIX.strip()
    addon = (state_addon or "").strip()
    if addon:
        prompt = f"{prompt}\n\n[Состояние диалога]\n{addon}"
    return prompt
