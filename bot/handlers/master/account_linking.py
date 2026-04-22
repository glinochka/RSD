from fastapi import status

from aiogram import types

from core.backendAPI import APIcreate, get_response_status


async def respond_to_telegram_link_code(message: types.Message, raw_code: str) -> int:
    """
    Confirm a 6-digit web→Telegram link code with the backend and send a user-facing reply.
    Returns the HTTP status from the backend (or a synthetic client-side code on transport errors).
    """
    response = await APIcreate.confirmTelegramLinkCode(
        code=raw_code,
        telegram_id=message.from_user.id,
    )
    response_status = get_response_status(response)

    if response_status == status.HTTP_200_OK:
        await message.answer("✅ Telegram успешно привязан к вашему аккаунту на сайте.")
        return response_status

    if response_status == status.HTTP_409_CONFLICT:
        await message.answer("Этот Telegram уже привязан к другому аккаунту.")
        return response_status

    if response_status == status.HTTP_429_TOO_MANY_REQUESTS:
        await message.answer("Код заблокирован из-за превышения числа попыток. Сгенерируйте новый код на сайте.")
        return response_status

    if response_status == status.HTTP_400_BAD_REQUEST:
        await message.answer("Код недействителен или истек. Сгенерируйте новый код в профиле на сайте.")
        return response_status

    await message.answer("Не удалось привязать аккаунт из-за ошибки сервера. Попробуйте позже.")
    return response_status
