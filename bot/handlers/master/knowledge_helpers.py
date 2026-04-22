from html import escape as html_escape
from urllib.parse import urlparse

from aiogram import types


def text_is_not_command(message: types.Message) -> bool:
    """
    Не перехватывать команды (/start и др.) FSM-хендлерами ожидания ссылки —
    иначе /start обрабатывается как «не URL» и пользователь застревает в цикле ошибок.
    """
    text = (message.text or "").strip()
    return bool(text) and not text.startswith("/")


def is_public_http_url(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def handle_link_upload_result(
    message: types.Message,
    response_data: dict,
    *,
    source_label: str,
) -> None:
    if response_data.get("status") == "limit_error":
        await message.answer(
            f"🚫 <b>Лимит базы знаний превышен!</b>\n\n"
            f"Ваш тариф: <b>{html_escape(str(response_data.get('current_plan', 'unknown')))}</b> "
            f"(макс. {response_data.get('limit', 'unknown')} чанков).\n"
            f"Уже использовано: {response_data.get('current_count', 'unknown')}.\n"
            f"{source_label} добавит: {response_data.get('new_chunks_count', 'unknown')}.\n\n"
            f"Удалите старые источники или повысьте тариф в меню.",
            parse_mode="HTML",
        )
        return

    if response_data.get("status") == "duplicate":
        await message.answer(
            f"ℹ️ Источник уже добавлен ранее "
            f"(статус: {html_escape(str(response_data.get('document_status', 'ready')))}).",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"✅ Ссылка принята и обрабатывается ({response_data.get('new_chunks_count', 'unknown')} чанков).",
        parse_mode="HTML",
    )
