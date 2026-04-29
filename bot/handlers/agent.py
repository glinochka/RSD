from aiogram import Router, types

from core.message_processor import Channel, MessageProcessor, MessageRequest, get_message_processor

agent_router = Router()


@agent_router.message()
async def handle_agent_message(message: types.Message, agent_config: dict):
    """
    Handle incoming message from Telegram agent bot.
    
    Uses unified MessageProcessor for consistent behavior across channels.
    agent_config is injected by AgentContextMiddleware.
    """
    query = message.text
    if query is None or not str(query).strip():
        await message.answer("Напишите, пожалуйста, текстовое сообщение.")
        return

    query = str(query).strip()

    # Extract user information
    from_user = message.from_user
    user_external_id = str(from_user.id) if from_user and from_user.id else None
    user_display_name = None
    if from_user:
        user_display_name = (from_user.full_name or from_user.username or "").strip() or None

    if not user_external_id:
        await message.answer("Не удалось определить вашу учетную запись.")
        return

    # Prepare request for unified processor
    request = MessageRequest(
        bot_id=int(agent_config["bot_id"]),
        query=query,
        user_external_id=user_external_id,
        channel=Channel.TELEGRAM,
        system_prompt=agent_config.get("system_prompt", ""),
        welcome_message=agent_config.get("welcome_message"),
        process_start_with_llm=bool(agent_config.get("process_start_with_llm", False)),
        user_display_name=user_display_name,
        telegram_peer_access_hash=None,  # Not available in webhook Telegram bot
    )

    # Process message using unified service
    processor = get_message_processor()
    response = await processor.process(request)

    # Send response
    await message.answer(response.text)