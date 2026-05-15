import base64
import io
import logging

from aiogram import Router, types

from core.config import settings
from core.message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)

agent_router = Router()


@agent_router.message()
async def handle_agent_message(message: types.Message, agent_config: dict):
    """
    Handle incoming message from Telegram agent bot.

    Uses unified MessageProcessor for consistent behavior across channels.
    agent_config is injected by AgentContextMiddleware.
    """
    bot = message.bot

    voice_b64: str | None = None
    voice_mime = "audio/ogg"
    image_b64: str | None = None
    image_mime = "image/jpeg"

    caption = (message.caption or "").strip()
    plain_text = (message.text or "").strip()

    query = caption if caption else plain_text

    try:
        if message.photo:
            photo = message.photo[-1]
            buf = io.BytesIO()
            await bot.download(photo, destination=buf)
            raw = buf.getvalue()
            if len(raw) > int(settings.IMAGE_DOWNLOAD_MAX_BYTES):
                await message.answer("Изображение слишком большое. Отправьте файл поменьше.")
                return
            image_b64 = base64.standard_b64encode(raw).decode("ascii")
            image_mime = "image/jpeg"
            if not query:
                query = "[Фото без подписи]"
        elif message.document:
            doc = message.document
            mime = (doc.mime_type or "").strip().lower()
            if mime.startswith("image/"):
                buf = io.BytesIO()
                await bot.download(doc, destination=buf)
                raw = buf.getvalue()
                if len(raw) > int(settings.IMAGE_DOWNLOAD_MAX_BYTES):
                    await message.answer("Изображение слишком большое. Отправьте файл поменьше.")
                    return
                image_b64 = base64.standard_b64encode(raw).decode("ascii")
                image_mime = doc.mime_type or "image/jpeg"
                if not query:
                    query = "[Изображение без подписи]"
            elif mime.startswith("audio/"):
                buf = io.BytesIO()
                await bot.download(doc, destination=buf)
                raw = buf.getvalue()
                if len(raw) > int(settings.VOICE_DOWNLOAD_MAX_BYTES):
                    await message.answer("Аудиофайл слишком большой.")
                    return
                voice_b64 = base64.standard_b64encode(raw).decode("ascii")
                voice_mime = doc.mime_type or "audio/mpeg"
            elif plain_text or caption:
                query = caption if caption else plain_text
            else:
                await message.answer(
                    "Пока поддерживаются текст, фото, изображения-файлы, голос и аудио. Отправьте что-то из этого."
                )
                return
        elif message.voice:
            buf = io.BytesIO()
            await bot.download(message.voice, destination=buf)
            raw = buf.getvalue()
            if len(raw) > int(settings.VOICE_DOWNLOAD_MAX_BYTES):
                await message.answer("Голосовое сообщение слишком большое.")
                return
            voice_b64 = base64.standard_b64encode(raw).decode("ascii")
            voice_mime = getattr(message.voice, "mime_type", None) or "audio/ogg"
        elif message.audio:
            buf = io.BytesIO()
            await bot.download(message.audio, destination=buf)
            raw = buf.getvalue()
            if len(raw) > int(settings.VOICE_DOWNLOAD_MAX_BYTES):
                await message.answer("Аудиосообщение слишком большое.")
                return
            voice_b64 = base64.standard_b64encode(raw).decode("ascii")
            voice_mime = getattr(message.audio, "mime_type", None) or "audio/mpeg"
        elif not plain_text and not caption:
            await message.answer(
                "Пока поддерживаются текст, фото, изображения-файлы, голос и аудио. Отправьте что-то из этого."
            )
            return
    except Exception:
        logger.exception("telegram bot: failed to download media")
        await message.answer("Не удалось загрузить вложение. Попробуйте ещё раз.")
        return

    query = (query or "").strip()

    from_user = message.from_user
    user_external_id = str(from_user.id) if from_user and from_user.id else None
    user_display_name = None
    if from_user:
        user_display_name = (from_user.full_name or from_user.username or "").strip() or None

    if not user_external_id:
        await message.answer("Не удалось определить вашу учетную запись.")
        return

    request = MessageRequest(
        bot_id=int(agent_config["bot_id"]),
        query=query,
        user_external_id=user_external_id,
        channel=Channel.TELEGRAM,
        system_prompt=agent_config.get("system_prompt", ""),
        welcome_message=agent_config.get("welcome_message"),
        process_start_with_llm=bool(agent_config.get("process_start_with_llm", False)),
        user_display_name=user_display_name,
        telegram_peer_access_hash=None,
        voice_base64=voice_b64,
        voice_mime_type=voice_mime if voice_b64 else None,
        image_base64=image_b64,
        image_mime_type=image_mime if image_b64 else None,
    )

    processor = get_message_processor()
    response = await processor.process(request)

    if response.status == ProcessingStatus.DISCARDED:
        return

    await message.answer(response.text)
