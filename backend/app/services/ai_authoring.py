from openai import AsyncOpenAI
import logging
import re

from ..config import settings
from ..prompts.system_prompts import (
    AI_AUTHORING_EMPTY_ANSWER_FALLBACK,
    IMPROVE_PROMPT_INSTRUCTION,
    WELCOME_GENERATION_INSTRUCTION,
    build_chat_turn_user_prompt,
    build_rag_answer_system_prompt,
    format_rag_chunks_for_prompt,
)

logger = logging.getLogger(__name__)

ai_client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

_TEMPLATE_VAR_RE = re.compile(r"(\{\{[^{}]+\}\}|\$\{[^{}]+\}|%\([^)]+\)s)")
_INTERNAL_ASSIGNMENT_RE = re.compile(
    r"\b(staff_id|resource_id|service_id|agent_id|appointment_id|client_external_id|"
    r"slot_id|user_id|chat_id|template_id|lookup_staff_id|new_staff_id|new_resource_id)\s*=\s*\S+",
    re.IGNORECASE,
)


def _clean_plain_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip().replace("#", "").replace("*", "")
    cleaned = _TEMPLATE_VAR_RE.sub("технические данные скрыты", cleaned)
    cleaned = _INTERNAL_ASSIGNMENT_RE.sub("технические данные скрыты", cleaned)
    return cleaned.strip()


async def improve_prompt_with_ai(current_prompt: str) -> str:
    """
    Turn a rough role description into a structured system prompt.
    """
    instruction = IMPROVE_PROMPT_INSTRUCTION.format(current_prompt=current_prompt)
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": instruction}],
        temperature=1.0,
    )
    return (response.choices[0].message.content or "").strip()


async def generate_welcome_with_ai(system_prompt: str) -> str:
    """
    Generate a short welcome message based on an agent's system prompt.
    """
    prompt = WELCOME_GENERATION_INSTRUCTION.format(system_prompt=system_prompt)
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()


def _polish_answer(raw_answer: str | None) -> str:
    text = (raw_answer or "").strip()
    if not text:
        return AI_AUTHORING_EMPTY_ANSWER_FALLBACK
    cleaned = _clean_plain_text(text)
    return cleaned or AI_AUTHORING_EMPTY_ANSWER_FALLBACK


async def generate_answer_with_context(
    question: str,
    context_list: list,
    system_prompt: str,
    *,
    chat_model: str | None = None,
    temperature: float = 0.3,
    memory_context: str | None = None,
) -> str:
    if not context_list:
        context_text = None
    else:
        context_text = format_rag_chunks_for_prompt(context_list)

    base_system = build_rag_answer_system_prompt(system_prompt)
    user_prompt = build_chat_turn_user_prompt(
        client_message=question,
        rag_context_text=context_text,
        memory_context=(memory_context or "").strip() or None,
    )
    model = (chat_model or "deepseek-chat").strip() or "deepseek-chat"

    response = await ai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=max(0.0, min(1.0, float(temperature))),
    )
    return _polish_answer(response.choices[0].message.content)
