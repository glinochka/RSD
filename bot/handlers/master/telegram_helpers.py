from aiogram import types
from aiogram.exceptions import TelegramBadRequest


def normalize_surrogates(text: str) -> str:
    """
    Convert valid UTF-16 surrogate pairs into proper Unicode symbols
    and drop broken surrogate code points.
    """
    if not text:
        return text
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "ignore")


def build_copy_api_key_button(external_api_key: str | None) -> types.InlineKeyboardButton:
    if not external_api_key:
        return types.InlineKeyboardButton(
            text="📋 Скопировать API ключ",
            callback_data="api_key_unavailable",
        )

    if hasattr(types, "CopyTextButton"):
        return types.InlineKeyboardButton(
            text="📋 Скопировать API ключ",
            copy_text=types.CopyTextButton(text=external_api_key),
        )

    return types.InlineKeyboardButton(
        text="📋 Скопировать API ключ",
        switch_inline_query_current_chat=external_api_key,
    )


async def safe_edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    if not callback.message:
        await callback.answer("Не удалось обновить сообщение", show_alert=True)
        return

    safe_text = normalize_surrogates(text)

    try:
        await callback.message.edit_text(
            text=safe_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as e:
        error_text = str(e).lower()
        if "message is not modified" in error_text:
            return
        if "message to edit not found" in error_text or "message can't be edited" in error_text:
            await callback.message.answer(
                text=safe_text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        raise


async def safe_callback_answer(
    callback: types.CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except RuntimeError:
        if text and callback.message:
            await callback.message.answer(text)
