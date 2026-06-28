"""Agent routes: channels whatsapp."""
from fastapi import APIRouter

from ..shared import *  # noqa: F403

router = APIRouter()

@router.post("/whatsapp_userbot/request_code")
async def request_whatsapp_userbot_code(
    payload: WhatsAppUserbotRequestCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    phone_number = payload.phone_number.strip()
    if len([ch for ch in phone_number if ch.isdigit()]) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер WhatsApp",
        )

    result = await _wa_userbot_bridge_post(
        "auth/request_code",
        {
            "phone_number": phone_number,
        },
    )
    bridge_auth_id = str(result.get("auth_id") or result.get("session_id") or "").strip()
    if not bridge_auth_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WhatsApp userbot bridge не вернул auth_id",
        )

    auth_token = _create_whatsapp_userbot_auth_token(
        user_id=current_user.id,
        phone_number=phone_number,
        bridge_auth_id=bridge_auth_id,
    )
    return JSONResponse(
        content={
            "auth_token": auth_token,
            "phone_number": phone_number,
            "delivery": result.get("delivery"),
            "hint": result.get("hint"),
            "qr_data_url": result.get("qr_data_url"),
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/whatsapp_userbot/verify_code")
async def verify_whatsapp_userbot_code(
    payload: WhatsAppUserbotVerifyCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_whatsapp_userbot_auth_token(payload.auth_token.strip())
    if int(token_data["user_id"]) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Токен подтверждения WhatsApp userbot принадлежит другому пользователю",
        )
    phone_number = str(token_data.get("phone_number") or "").strip()
    bridge_auth_id = decrypt_token(token_data["encrypted_bridge_auth_id"])
    code = payload.code.strip() if payload.code else ""

    try:
        result = await _wa_userbot_bridge_post(
            "auth/verify_code",
            {
                "auth_id": bridge_auth_id,
                "phone_number": phone_number,
                "code": code or None,
            },
        )
    except HTTPException as exc:
        if _wa_userbot_bridge_http_status(exc) == 404:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Сессия подтверждения не найдена или истекла. Запросите новый QR-код.",
            ) from exc
        raise
    session_string = str(result.get("session_string") or "").strip()
    normalized_phone = str(result.get("phone_number") or phone_number).strip()
    normalized_phone, _ = _validate_whatsapp_session_string(
        session_string=session_string,
        expected_phone=normalized_phone,
    )

    return JSONResponse(
        content={
            "session_string": session_string,
            "phone_number": normalized_phone,
            "external_user_id": result.get("external_user_id"),
            "display_name": result.get("display_name"),
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/whatsapp_userbot/auth_status")
async def whatsapp_userbot_auth_status(
    payload: WhatsAppUserbotAuthStatus, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_whatsapp_userbot_auth_token(payload.auth_token.strip())
    if int(token_data["user_id"]) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Токен подтверждения WhatsApp userbot принадлежит другому пользователю",
        )
    bridge_auth_id = decrypt_token(token_data["encrypted_bridge_auth_id"])
    try:
        result = await _wa_userbot_bridge_post(
            "auth/status",
            {
                "auth_id": bridge_auth_id,
            },
        )
    except HTTPException as exc:
        if _wa_userbot_bridge_http_status(exc) == 404:
            return JSONResponse(
                content={
                    "status": "expired",
                    "qr_data_url": None,
                    "last_error": "Сессия подтверждения не найдена или истекла",
                    "last_disconnect_code": None,
                },
                status_code=status.HTTP_200_OK,
            )
        raise
    return JSONResponse(
        content={
            "status": result.get("status") or "pending",
            "qr_data_url": result.get("qr_data_url"),
            "last_error": result.get("last_error"),
            "last_disconnect_code": result.get("last_disconnect_code"),
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/channels/by_whatsapp_business_api")
async def add_agent_whatsapp_business_api_channel(
    payload: AddWhatsAppBusinessApiChannel,
    current_user=Depends(get_current_user_required),
):
    phone_number_id = payload.phone_number_id.strip()
    access_token = payload.access_token.strip()
    business_account_id = payload.business_account_id.strip() if payload.business_account_id else None
    verify_token = payload.verify_token.strip() if payload.verify_token else None
    if not phone_number_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phone Number ID должен содержать только цифры",
        )
    try:
        waba_phone_info = await _waba_get_phone_number_info(phone_number_id, access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось проверить доступ к WhatsApp Business API. Проверьте access token и phone_number_id",
        )
    resolved_phone_number_id = str(waba_phone_info.get("id") or "").strip()
    if not resolved_phone_number_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Meta Graph API не вернул id номера. Проверьте access token и phone_number_id",
        )
    phone_number_id = resolved_phone_number_id

    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "phone_number_id": phone_number_id,
                "access_token": access_token,
                "business_account_id": business_account_id,
                "verify_token": verify_token,
                "display_phone_number": waba_phone_info.get("display_phone_number"),
                "verified_name": waba_phone_info.get("verified_name"),
                "quality_rating": waba_phone_info.get("quality_rating"),
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_whatsapp_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "whatsapp_business_api",
                    AgentChannelConnection.connection_type == "api",
                )
            )
            if existing_whatsapp_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен канал WhatsApp Business API",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="whatsapp_business_api",
                external_id=phone_number_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот WhatsApp phone_number_id уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "whatsapp_business_api",
                    "connection_type": "api",
                    "external_id": phone_number_id,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )



@router.post("/channels/by_whatsapp_userbot")
async def add_agent_whatsapp_userbot_channel(
    payload: AddWhatsAppUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    normalized_phone = payload.phone_number.strip()
    session_string = payload.session_string.strip()
    client_label = payload.client_label.strip() if payload.client_label else None
    if len([ch for ch in normalized_phone if ch.isdigit()]) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер WhatsApp userbot",
        )

    normalized_phone, _ = _validate_whatsapp_session_string(
        session_string=session_string,
        expected_phone=normalized_phone,
    )
    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "phone_number": normalized_phone,
                "session_string": session_string,
                "client_label": client_label,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing_whatsapp_userbot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "whatsapp_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_whatsapp_userbot_channel and str(agent.template_type or "").strip().lower() != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен WhatsApp userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="whatsapp_userbot",
                external_id=normalized_phone,
            )
            if duplicate_connection:
                if int(duplicate_connection.agent_id) == int(agent.id):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Этот WhatsApp userbot уже подключен к текущему агенту",
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот WhatsApp userbot уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "whatsapp_userbot",
                    "connection_type": "userbot",
                    "external_id": normalized_phone,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )



@router.post("/whatsapp_userbot/send_to_user")
async def whatsapp_userbot_send_to_user_as_owner(
    payload: AgentWhatsappUserbotSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    to_jid = _whatsapp_user_external_to_jid(payload.user_external_id)
    ext_id = payload.user_external_id.strip()
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            wa_channel = await _get_whatsapp_userbot_channel_for_agent(session, agent.id)
            if not wa_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала WhatsApp userbot",
                )
            connection_id = int(wa_channel.id)
            agent_pk = int(agent.id)
            analytics_namespace_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
            encrypted_credentials = str(wa_channel.encrypted_credentials or "")

    # Убедимся что сессия активна в wa_bridge перед отправкой
    await _ensure_whatsapp_userbot_session(connection_id, encrypted_credentials)

    await _wa_userbot_bridge_post(
        "session/send",
        {
            "connection_id": str(connection_id),
            "to_jid": to_jid,
            "text": text,
        },
    )

    async with async_session_maker() as log_session:
        async with log_session.begin():
            await _log_analytics_message_for_agent_ids(
                session=log_session,
                agent_id=agent_pk,
                telegram_bot_id=analytics_namespace_id,
                role="operator",
                message_text=text,
                channel="whatsapp_userbot",
                user_external_id=ext_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)



@router.get("/whatsapp_userbot/broadcast_recipients")
async def whatsapp_userbot_broadcast_recipients(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id)
            if not recipients:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "whatsapp_userbot_users_total": 0,
                        "frozen_among_whatsapp_userbot": 0,
                        "eligible_when_skip_frozen": 0,
                    },
                    status_code=status.HTTP_200_OK,
                )
            recipient_ids = [r["user_external_id"] for r in recipients]
            frozen_rows = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(recipient_ids),
                )
            )
            frozen_set = set(frozen_rows.all())
            frozen_among = len([r for r in recipients if r["user_external_id"] in frozen_set])
            eligible = len([r for r in recipients if r["user_external_id"] not in frozen_set])
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "whatsapp_userbot_users_total": len(recipients),
                    "frozen_among_whatsapp_userbot": frozen_among,
                    "eligible_when_skip_frozen": eligible,
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/whatsapp_userbot/broadcast")
async def whatsapp_userbot_broadcast_as_owner(
    payload: AgentWhatsappUserbotBroadcastPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    max_n = payload.max_recipients

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            recipients = await _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id)
            agent_pk = agent.id
            telegram_bot_id = analytics_namespace_id
            wa_channel = await _get_whatsapp_userbot_channel_for_agent(session, agent.id)
            if not wa_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала WhatsApp userbot для рассылки",
                )
            connection_id = int(wa_channel.id)
            encrypted_credentials = str(wa_channel.encrypted_credentials or "")

    # Убедимся что сессия активна в wa_bridge перед началом рассылки
    await _ensure_whatsapp_userbot_session(connection_id, encrypted_credentials)

    recipient_ids = [r["user_external_id"] for r in recipients]
    frozen_set: set[str] = set()
    if payload.skip_frozen and recipient_ids:
        async with async_session_maker() as session:
            async with session.begin():
                frozen_rows = await session.scalars(
                    select(AgentFrozenUser.user_external_id).where(
                        AgentFrozenUser.agent_id == agent_pk,
                        AgentFrozenUser.user_external_id.in_(recipient_ids),
                    )
                )
                frozen_set = set(frozen_rows.all())

    skipped_frozen = sum(
        1 for recipient in recipients
        if payload.skip_frozen and recipient["user_external_id"] in frozen_set
    )
    eligible_recipients = [
        recipient
        for recipient in recipients
        if not (payload.skip_frozen and recipient["user_external_id"] in frozen_set)
    ]
    to_send = eligible_recipients[:max_n]
    truncated_over_limit = max(0, len(eligible_recipients) - max_n)

    sent = 0
    failed = 0
    errors: list[dict] = []
    throttle_seconds = 0.35

    for recipient in to_send:
        uid = recipient["user_external_id"]
        channel = recipient["channel"]
        try:
            to_jid = _whatsapp_user_external_to_jid(uid)
            await _wa_userbot_bridge_post(
                "session/send",
                {
                    "connection_id": str(connection_id),
                    "to_jid": to_jid,
                    "text": text,
                },
            )
            sent += 1
            async with async_session_maker() as log_session:
                async with log_session.begin():
                    await _log_analytics_message_for_agent_ids(
                        session=log_session,
                        agent_id=agent_pk,
                        telegram_bot_id=telegram_bot_id,
                        role="operator",
                        message_text=text,
                        channel="dashboard",
                        user_external_id=uid,
                        user_display_name=None,
                    )
        except HTTPException as exc:
            failed += 1
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": detail})
        except Exception as exc:
            failed += 1
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "channel": channel, "detail": str(exc)})
        await asyncio.sleep(throttle_seconds)

    return JSONResponse(
        content={
            "ok": True,
            "sent": sent,
            "failed": failed,
            "skipped_frozen": skipped_frozen,
            "truncated_over_limit": truncated_over_limit,
            "attempted": len(to_send),
            "errors": errors,
        },
        status_code=status.HTTP_200_OK,
    )


