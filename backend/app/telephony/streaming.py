"""Streaming LLM tokens → sentence chunks for early TTS (stage 5)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from ..services.ai_authoring import ai_client, _polish_answer

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_sentences(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = _SENTENCE_END.split(raw)
    return [p.strip() for p in parts if p.strip()]


def extract_complete_sentences(buffer: str) -> tuple[list[str], str]:
    """Return completed sentences and remaining buffer tail."""
    if not buffer.strip():
        return [], buffer
    parts = _SENTENCE_END.split(buffer)
    if len(parts) <= 1:
        return [], buffer
    complete = [p.strip() for p in parts[:-1] if p.strip()]
    tail = parts[-1]
    return complete, tail


async def stream_answer_sentences(
    *,
    question: str,
    context_list: list,
    system_prompt: str,
    chat_model: str | None = None,
    min_chunk_chars: int = 12,
    call_db_id: int | None = None,
) -> AsyncIterator[str]:
    """Stream LLM completion and yield text chunks at sentence boundaries."""
    if not context_list:
        context_text = "Информации в базе знаний не найдено."
    else:
        context_parts = [
            f"Источник: {c.get('source', 'Unknown')}\nТекст: {c.get('text', '')}" for c in context_list
        ]
        context_text = "\n\n---\n\n".join(context_parts)

    base_system = (
        f"{system_prompt}\n\n"
        "ВАЖНО: Отвечай только чистым текстом.\n"
        "ЗАПРЕЩЕНО использовать markdown-форматирование.\n"
        "ЗАПРЕЩЕНО показывать названия переменных/шаблонов и их значения."
    )
    user_prompt = f"КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:\n{context_text}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}"
    model = (chat_model or "deepseek-chat").strip() or "deepseek-chat"

    stream = await ai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        stream=True,
    )

    from .stream_cancel import is_cancelled

    buffer = ""
    async for chunk in stream:
        if call_db_id is not None and is_cancelled(call_db_id):
            break
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue
        buffer += delta
        complete, buffer = extract_complete_sentences(buffer)
        for sentence in complete:
            polished = _polish_answer(sentence)
            if len(polished) >= min_chunk_chars:
                yield polished

    tail = _polish_answer(buffer)
    if tail:
        yield tail


async def collect_streamed_answer(
    *,
    question: str,
    context_list: list,
    system_prompt: str,
    chat_model: str | None = None,
    call_db_id: int | None = None,
) -> tuple[str, list[str]]:
    """Collect full answer and sentence chunks from streaming generation."""
    chunks: list[str] = []
    async for sentence in stream_answer_sentences(
        question=question,
        context_list=context_list,
        system_prompt=system_prompt,
        chat_model=chat_model,
        call_db_id=call_db_id,
    ):
        chunks.append(sentence)
    full = " ".join(chunks).strip()
    if not full and chunks:
        full = chunks[-1]
    return full, chunks
