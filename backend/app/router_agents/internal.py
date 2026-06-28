"""Agent routes: internal."""
from fastapi import APIRouter

from .shared import *  # noqa: F403

router = APIRouter()

@router.get("/internal/userbot_clients")
async def list_userbot_clients(request: Request, internal: bool = Depends(is_internal_request)):
    """List active userbot channel configs for bot service (internal only)."""
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(request)

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(
                            Agent.id.label("agent_id"),
                            Agent.bot_id,
                            Agent.system_prompt,
                            Agent.welcome_message,
                            Agent.process_start_with_llm,
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "telegram_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )

    payload = []
    for row in rows:
        resolved_lookup_id = row["bot_id"] if row["bot_id"] is not None else row["agent_id"]
        payload.append(
            {
                "agent_id": int(row["agent_id"]),
                "bot_id": int(resolved_lookup_id),
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "process_start_with_llm": bool(row["process_start_with_llm"]),
                "encrypted_userbot_bundle": row["encrypted_credentials"],
            }
        )

    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)



@router.get("/internal/whatsapp_userbot_clients")
async def list_whatsapp_userbot_clients(request: Request, internal: bool = Depends(is_internal_request)):
    """List active WhatsApp userbot channel configs for bot service (internal only)."""
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(request)

    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(
                            Agent.id.label("agent_id"),
                            Agent.bot_id,
                            Agent.system_prompt,
                            Agent.welcome_message,
                            Agent.process_start_with_llm,
                            AgentChannelConnection.id.label("connection_id"),
                            AgentChannelConnection.external_id.label("phone_number"),
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "whatsapp_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )

    payload = []
    for row in rows:
        resolved_lookup_id = row["bot_id"] if row["bot_id"] is not None else row["agent_id"]
        payload.append(
            {
                "agent_id": int(row["agent_id"]),
                "bot_id": int(resolved_lookup_id),
                "connection_id": int(row["connection_id"]),
                "phone_number": row["phone_number"] or "",
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "process_start_with_llm": bool(row["process_start_with_llm"]),
                "encrypted_credentials": row["encrypted_credentials"],
            }
        )

    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)



@router.post("/internal/process_message")
async def internal_process_message(
    http_request: Request,
    payload: InternalProcessMessageRequest,
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(http_request)

    try:
        channel = RuntimeChannel(payload.channel)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported channel",
        )

    query_text = (payload.query or "").strip()
    runtime_ctx: dict[str, object] = {}

    if payload.voice_base64:
        raw_voice = (payload.voice_base64 or "").strip()
        try:
            audio_bytes = base64.b64decode(raw_voice, validate=True)
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid voice_base64")
        if len(audio_bytes) > int(settings.VOICE_MAX_BYTES):
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="voice payload too large")
        if is_voice_stt_configured():
            transcript = await transcribe_voice_bytes(
                audio_bytes,
                mime_type=(payload.voice_mime_type or "audio/ogg"),
            )
            if transcript:
                query_text = (
                    f"{query_text}\n\nТекст голосового сообщения: {transcript}".strip()
                    if query_text
                    else f"Текст голосового сообщения: {transcript}"
                )
            elif not query_text:
                query_text = "Пользователь прислал голосовое сообщение, но текст распознать не удалось."
        elif not query_text:
            return JSONResponse(
                content={
                    "text": (
                        "Голосовые сообщения недоступны: не настроено распознавание речи "
                        "(установите faster-whisper и модель, либо задайте OPENAI_API_KEY; DeepSeek аудио не принимает). "
                        "Напишите, пожалуйста, текстом."
                    ),
                    "status": RuntimeProcessingStatus.SUCCESS.value,
                },
                status_code=status.HTTP_200_OK,
            )

    query_text = query_text.strip()
    if not query_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty query after processing")

    runtime_request = RuntimeMessageRequest(
        bot_id=payload.bot_id,
        query=query_text,
        user_external_id=payload.user_external_id.strip(),
        channel=channel,
        system_prompt=(payload.system_prompt or "").strip(),
        welcome_message=payload.welcome_message,
        process_start_with_llm=bool(payload.process_start_with_llm),
        user_display_name=(payload.user_display_name or "").strip() or None,
        telegram_peer_access_hash=payload.telegram_peer_access_hash,
        runtime_context=runtime_ctx or None,
    )
    response = await get_message_processor().process(runtime_request)
    return JSONResponse(
        content={
            "text": response.text,
            "status": response.status.value,
            "reply": response.delivers_reply(),
        },
        status_code=status.HTTP_200_OK,
    )


