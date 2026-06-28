"""Agent routes: channels max."""
from fastapi import APIRouter

from ..shared import *  # noqa: F403

router = APIRouter()

@router.post("/channels/by_max_bot")
async def add_agent_max_bot_channel(
    payload: AddMaxBotChannel,
    current_user=Depends(get_current_user_required),
):
    bot_token = payload.bot_token.strip()
    try:
        me = await _max_bot_get_me(bot_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось связаться с MAX API для проверки токена: {exc}",
        )

    max_bot_id = me.get("user_id")
    if max_bot_id is None or not str(max_bot_id).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX API не вернул user_id бота",
        )
    is_bot = me.get("is_bot")
    if is_bot is not None and not bool(is_bot):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Переданный токен не принадлежит чат-боту MAX",
        )
    bot_username = (
        str(me.get("username") or "").strip()
        or str(me.get("first_name") or "").strip()
        or str(me.get("name") or "").strip()
        or f"max_bot_{max_bot_id}"
    )

    encrypted_bundle = encrypt_token(
        json.dumps(
            {
                "max_bot_token": bot_token,
                "max_bot_user_id": str(max_bot_id).strip(),
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
            existing_max_bot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "max_bot",
                    AgentChannelConnection.connection_type == "bot",
                )
            )
            if existing_max_bot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен MAX bot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="max_bot",
                external_id=str(max_bot_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот MAX бот уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "max_bot",
                    "connection_type": "bot",
                    "external_id": str(max_bot_id),
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
                await agent_dao.update(agent, {"bot_username": bot_username or agent.bot_username})
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



@router.get("/channels/telephony/platform")
async def get_telephony_platform_config(
    current_user=Depends(get_current_user_required),
):
    """Публичные настройки общего номера (без секретов Voximplant)."""
    _ = current_user
    return platform_telephony_public_fields()



@router.patch("/channels/telephony/routing")
async def update_agent_telephony_routing(
    payload: UpdateTelephonyRouting,
    current_user=Depends(get_current_user_required),
):
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
            connection = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
                    AgentChannelConnection.is_active.is_(True),
                )
            )
            if connection is None or not connection.encrypted_credentials:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Телефонный канал не найден",
                )
            previous = parse_telephony_credentials(decrypt_token(connection.encrypted_credentials))
            updated = previous.model_copy(
                update={
                    "routing_extension": payload.routing_extension.strip(),
                    "inbound_numbers": [],
                }
            )
            if updated.routing_extension:
                conflict = await scan_extension_conflict_in_db(
                    session,
                    updated.routing_extension,
                    exclude_connection_id=int(connection.id),
                )
                if conflict is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Добавочный {updated.routing_extension} уже занят",
                    )
            connection.encrypted_credentials = encrypt_token(updated.to_encrypted_payload())
            connection.updated_at = datetime.utcnow()
            await sync_channel_routes(
                connection_id=int(connection.id),
                agent_id=int(agent.id),
                creds=updated,
                previous=previous,
            )
            channels = await _list_agent_channels(session, agent.id)
            return {
                "agent_id": agent.id,
                "telephony_routing": telephony_routing_public_fields(updated),
                "channels": [_serialize_channel_connection(item) for item in channels],
            }



@router.post("/channels/telephony/validate")
async def validate_agent_telephony_channel(
    payload: ValidateTelephonyChannel,
    current_user=Depends(get_current_user_required),
):
    _ = current_user
    if not settings.TELEPHONY_WEBHOOK_BASE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_WEBHOOK_BASE_URL не настроен на сервере",
        )
    platform = require_platform_telephony_config()
    try:
        await validate_voximplant_channel_setup(
            account_id=platform.account_id,
            api_key=platform.api_key,
            phone_number_e164=platform.shared_pool_e164,
            application_id=platform.application_id,
            rule_id=platform.rule_id,
        )
    except VoximplantApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ext = (payload.routing_extension or "").strip()
    if ext:
        async with async_session_maker() as session:
            conflict = await scan_extension_conflict_in_db(session, ext)
            if conflict is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Добавочный {ext} уже занят",
                )

    return {
        "ok": True,
        "provider": TELEPHONY_CHANNEL_PROVIDER,
        "phone_number_e164": platform.shared_pool_e164,
        "routing_extension": ext or None,
        "message": "Общий номер Voximplant доступен",
        **platform_telephony_public_fields(),
    }



@router.post("/max_userbot/qr/start")
async def max_userbot_qr_start(
    payload: MaxUserbotQrStart,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    try:
        result = await max_start_qr_login()
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось начать QR-вход MAX: {exc}",
        ) from exc
    auth_token = _create_max_userbot_auth_token(str(result["auth_id"]))
    return JSONResponse(
        content={
            "auth_token": auth_token,
            "qr_url": result.get("qr_url") or "",
            "qr_data_url": result.get("qr_data_url") or "",
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/max_userbot/qr/status")
async def max_userbot_qr_status(
    payload: MaxUserbotQrStatus,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    auth_id = _decode_max_userbot_auth_token(payload.auth_token.strip())
    try:
        qr_state = await max_get_qr_status(auth_id=auth_id)
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    return JSONResponse(content=qr_state, status_code=status.HTTP_200_OK)



@router.post("/max_userbot/qr/verify_2fa")
async def max_userbot_qr_verify_2fa(
    payload: MaxUserbotQrVerify2fa,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    auth_id = _decode_max_userbot_auth_token(payload.auth_token.strip())
    try:
        result = await max_complete_qr_2fa(auth_id=auth_id, password=payload.password)
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    return JSONResponse(content=result, status_code=status.HTTP_200_OK)



@router.post("/max_userbot/request_code")
async def max_userbot_request_code(
    payload: MaxUserbotRequestCode,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    try:
        result = await max_request_sms_code(phone_number=payload.phone_number.strip())
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось отправить SMS-код MAX: {exc}",
        ) from exc
    auth_token = _create_max_userbot_auth_token(str(result["auth_id"]))
    return JSONResponse(
        content={
            "auth_token": auth_token,
            "phone_number": result.get("phone_number"),
            "code_length": result.get("code_length"),
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/max_userbot/verify_code")
async def max_userbot_verify_code(
    payload: MaxUserbotVerifyCode,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    auth_id = _decode_max_userbot_auth_token(payload.auth_token.strip())
    try:
        result = await max_verify_sms_code(
            auth_id=auth_id,
            code=payload.code,
            password=payload.password,
        )
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    if result.get("status") == "need_2fa":
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    return JSONResponse(content=result, status_code=status.HTTP_200_OK)



@router.post("/max_userbot/import_session")
async def max_userbot_import_session(
    session_file: UploadFile = File(...),
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    raw = await session_file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл сессии слишком большой (макс. 25 МБ)",
        )
    try:
        result = await max_import_session_file(
            filename=session_file.filename or "upload",
            content=raw,
        )
    except MaxUserbotAuthError as exc:
        raise _max_userbot_auth_http_error(exc) from exc
    except MaxUserbotSessionError as exc:
        raise _max_userbot_session_http_error(exc) from exc
    except Exception as exc:
        logger.warning("max_userbot import_session failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось импортировать сессию MAX: {exc}",
        ) from exc
    return JSONResponse(content=result, status_code=status.HTTP_200_OK)



@router.post("/channels/by_max_userbot")
async def add_agent_max_userbot_channel(
    payload: AddMaxUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    logger.info(
        "add_agent_max_userbot_channel: start user_id=%s agent_id=%s bot_id=%s",
        getattr(current_user, "id", None),
        payload.agent_id,
        payload.bot_id,
    )
    validated = await _validate_max_userbot_session_payload(payload.session_payload)
    max_account_id = str(validated.get("account_id") or validated.get("max_account_id") or "").strip()
    session_payload = str(validated.get("session_payload") or payload.session_payload.strip())
    if not max_account_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX не вернул id аккаунта для сессии",
        )
    logger.info(
        "add_agent_max_userbot_channel: session validated account_id=%s",
        max_account_id,
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
            template_type = _normalize_template_type(agent.template_type)
            if template_type == "content_factory":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MAX userbot недоступен для шаблона Контент-завод",
                )

            existing_max_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "max_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_max_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен MAX userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="max_userbot",
                external_id=max_account_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот MAX аккаунт уже подключен к другому агенту",
                )

            encrypted_bundle = encrypt_token(
                json.dumps(
                    {
                        "session_payload": session_payload,
                        "max_account_id": max_account_id,
                    },
                    ensure_ascii=False,
                )
            )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "max_userbot",
                    "connection_type": "userbot",
                    "external_id": max_account_id,
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
            logger.info(
                "add_agent_max_userbot_channel: success agent_id=%s connection_id=%s",
                agent.id,
                created_connection.id,
            )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )



@router.post("/max_userbot/send_to_user")
async def max_userbot_send_to_user_as_owner(
    payload: AgentMaxUserbotSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
        )
    user_external_id = payload.user_external_id.strip()
    if not user_external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_external_id is required",
        )

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
            max_channel = await _get_max_userbot_channel_for_agent(session, agent.id)
            if not max_channel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного канала MAX userbot",
                )
            encrypted_credentials = str(max_channel.encrypted_credentials or "")

    await _max_userbot_send_message(encrypted_credentials, text, chat_id=user_external_id)

    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message_for_agent_ids(
                session=session,
                agent_id=agent.id,
                telegram_bot_id=agent.bot_id if agent.bot_id is not None else agent.id,
                role="operator",
                message_text=text,
                channel="dashboard",
                user_external_id=user_external_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


