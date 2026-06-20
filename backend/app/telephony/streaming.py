"""Streaming LLM tokens → syntagma chunks for early TTS (stage 5)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from ..config import settings
from ..services.ai_authoring import _polish_answer

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_SYNTAGMA_END = re.compile(r"(?<=[,.\!?…])\s+")


def split_sentences(text: str) -> list[str]:
    return split_syntagmas(text)


def split_syntagmas(text: str, *, min_chars: int | None = None) -> list[str]:
    """Split on punctuation (, . ! ? …) respecting minimum syntagma length."""
    raw = (text or "").strip()
    if not raw:
        return []
    min_len = max(1, int(min_chars or settings.TELEPHONY_SYNTAGMA_MIN_CHARS))
    parts = _SYNTAGMA_END.split(raw)
    out: list[str] = []
    buf = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if buf:
            buf = f"{buf} {piece}"
        else:
            buf = piece
        if len(buf) >= min_len and _ends_clause(buf):
            out.append(buf)
            buf = ""
    if buf.strip():
        if out and len(buf) < min_len:
            out[-1] = f"{out[-1]} {buf}".strip()
        else:
            out.append(buf.strip())
    return out


def _ends_clause(text: str) -> bool:
    return bool(text) and text[-1] in ",.!?…"


def extract_complete_sentences(buffer: str) -> tuple[list[str], str]:
    """Backward-compatible sentence split."""
    return extract_complete_syntagmas(buffer)


def extract_complete_syntagmas(
    buffer: str,
    *,
    min_chars: int | None = None,
) -> tuple[list[str], str]:
    """Return completed syntagmas and remaining buffer tail."""
    if not buffer.strip():
        return [], buffer
    min_len = max(1, int(min_chars or settings.TELEPHONY_SYNTAGMA_MIN_CHARS))
    parts = _SYNTAGMA_END.split(buffer)
    if len(parts) <= 1:
        return [], buffer
    complete: list[str] = []
    pending = ""
    for part in parts[:-1]:
        piece = part.strip()
        if not piece:
            continue
        pending = f"{pending} {piece}".strip() if pending else piece
        if len(pending) >= min_len and _ends_clause(pending):
            complete.append(_polish_answer(pending))
            pending = ""
    tail = parts[-1]
    if pending:
        tail = f"{pending} {tail}".strip() if tail.strip() else pending
    return complete, tail


def _llm_client() -> AsyncOpenAI:
    mode = (getattr(settings, "TELEPHONY_LLM_MODE", None) or "chat").strip().lower()
    if mode == "groq":
        api_key = (getattr(settings, "GROQ_API_KEY", None) or "").strip()
        if api_key:
            return AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    if mode == "xai":
        api_key = (getattr(settings, "XAI_API_KEY", None) or "").strip()
        if api_key:
            return AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    if mode == "openrouter":
        api_key = (getattr(settings, "OPENROUTER_API_KEY", None) or "").strip()
        if api_key:
            return AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    return AsyncOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )


def _llm_model(chat_model: str | None = None) -> str:
    mode = (getattr(settings, "TELEPHONY_LLM_MODE", None) or "chat").strip().lower()
    if mode == "groq":
        return (getattr(settings, "TELEPHONY_GROQ_MODEL", None) or "llama-3.1-8b-instant").strip()
    if mode == "xai":
        return (getattr(settings, "TELEPHONY_XAI_MODEL", None) or "grok-2-latest").strip()
    if mode == "openrouter":
        return (getattr(settings, "TELEPHONY_OPENROUTER_MODEL", None) or "meta-llama/llama-3.3-70b-instruct").strip()
    default_model = (getattr(settings, "TELEPHONY_LLM_DEEPSEEK_MODEL", None) or "deepseek-v4-flash").strip()
    return (chat_model or default_model).strip() or default_model


import logging
import time

logger = logging.getLogger(__name__)

async def stream_answer_sentences(
    *,
    question: str,
    context_list: list,
    system_prompt: str,
    chat_model: str | None = None,
    min_chunk_chars: int | None = None,
    call_db_id: int | None = None,
    external_call_id: str | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Stream LLM completion and yield text chunks at syntagma boundaries."""
    llm_start = time.perf_counter()
    if not context_list:
        context_text = None
    else:
        context_text = format_rag_chunks_for_prompt(context_list)

    from ..prompts.system_prompts import (
        CHAT_OPERATOR_PERSONA,
        INTERNAL_CONTEXT_USAGE_RULES,
        PLAIN_TEXT_RESPONSE_RULES_STREAMING,
        build_chat_turn_user_prompt,
    )

    base_system = (
        f"{system_prompt}\n\n{CHAT_OPERATOR_PERSONA}\n\n"
        f"{PLAIN_TEXT_RESPONSE_RULES_STREAMING}\n\n{INTERNAL_CONTEXT_USAGE_RULES}"
    )
    user_prompt = build_chat_turn_user_prompt(
        client_message=question,
        rag_context_text=context_text,
    )
    model = _llm_model(chat_model)
    mode = (getattr(settings, "TELEPHONY_LLM_MODE", None) or "chat").strip().lower()
    min_len = max(1, int(min_chunk_chars or settings.TELEPHONY_SYNTAGMA_MIN_CHARS))

    client = _llm_client()
    logger.info("llm_stream_start: mode=%s model=%s text_len=%d", mode, model, len(user_prompt))
    create_kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "stream": True,
    }
    if max_tokens is not None:
        create_kwargs["max_tokens"] = max_tokens
    # OpenRouter: route to Groq for lowest latency (model slug is OpenRouter's, not Groq's)
    if mode == "openrouter":
        create_kwargs["extra_body"] = {"provider": {"only": ["groq"]}}
    stream = await client.chat.completions.create(**create_kwargs)

    from .stream_cancel import is_cancelled, is_cancelled_call_id

    buffer = ""
    first_token = True
    async for chunk in stream:
        if external_call_id and is_cancelled_call_id(external_call_id):
            break
        if call_db_id is not None and is_cancelled(call_db_id):
            break
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue
        if first_token:
            ttft_ms = int((time.perf_counter() - llm_start) * 1000)
            logger.info("llm_first_token: mode=%s model=%s ttft_ms=%d", mode, model, ttft_ms)
            first_token = False
        buffer += delta
        complete, buffer = extract_complete_syntagmas(buffer, min_chars=min_len)
        for syntagma in complete:
            if len(syntagma) >= min_len:
                yield syntagma

    tail = _polish_answer(buffer)
    if tail and len(tail) >= min_len:
        yield tail
    elif tail:
        yield tail


async def collect_streamed_answer(
    *,
    question: str,
    context_list: list,
    system_prompt: str,
    chat_model: str | None = None,
    call_db_id: int | None = None,
    external_call_id: str | None = None,
) -> tuple[str, list[str]]:
    """Collect full answer and syntagma chunks from streaming generation."""
    chunks: list[str] = []
    async for sentence in stream_answer_sentences(
        question=question,
        context_list=context_list,
        system_prompt=system_prompt,
        chat_model=chat_model,
        call_db_id=call_db_id,
        external_call_id=external_call_id,
    ):
        chunks.append(sentence)
    full = " ".join(chunks).strip()
    if not full and chunks:
        full = chunks[-1]
    return full, chunks
