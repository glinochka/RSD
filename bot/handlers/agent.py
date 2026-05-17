import base64
import io
import logging

from aiogram import Router, types

from core.config import settings
from core.message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)

agent_router = Router()

_UNSUPPORTED_MEDIA_REPLY = (
    "Спасибо, что написали! Пока я лучше всего понимаю текст и голосовые — "
    "с картинками и файлами, к сожалению, ещё не справляюсь. "
    "Напишите, пожалуйста, словами или отправьте голосовое — с радостью помогу."
)


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

    caption = (message.caption or "").strip()
    plain_text = (message.text or "").strip()

    query = caption if caption else plain_text

    try:
        if message.photo:
            await message.answer(_UNSUPPORTED_MEDIA_REPLY)
            return
        if message.document:
            doc = message.document
            mime = (doc.mime_type or "").strip().lower()
            if mime.startswith("image/"):
                await message.answer(_UNSUPPORTED_MEDIA_REPLY)
                return
            if mime.startswith("audio/"):
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
                await message.answer(_UNSUPPORTED_MEDIA_REPLY)
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
            await message.answer(_UNSUPPORTED_MEDIA_REPLY)
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
    )

    processor = get_message_processor()
    response = await processor.process(request)

    if response.status == ProcessingStatus.DISCARDED:
        return

    await message.answer(response.text)
