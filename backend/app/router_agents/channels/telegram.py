"""Agent routes: channels telegram."""
from fastapi import APIRouter

from ..shared import *  # noqa: F403

router = APIRouter()

@router.post("/by_token")
async def create_agent_by_token(
    new_agent: NewAgent_byToken,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_value = new_agent.bot_token.strip()

    try:
        me = await _telegram_get_me(token_value)
    except Exception as exc:
        _raise_telegram_token_check_http_exception(exc)

    if not me or me.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный API ключ Telegram бота",
        )

    result = me.get("result") or {}
    bot_id = result.get("id")
    bot_username = result.get("username")
    if bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram не вернул bot id по указанному токену",
        )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(new_agent.template_type)
            template_config = _normalize_template_config(template_type, new_agent.template_config)
            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован",
                )
            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": bot_id,
                    "primary_provider": "telegram_bot",
                    "template_type": template_type,
                    "template_config": template_config,
                    "encrypted_token": encrypt_token(token_value),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": bot_username,
                    "system_prompt": new_agent.system_prompt.strip(),
                    # New agents should be immediately usable via Telegram webhook.
                    "is_active": True,
                }
            )
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(new_agent.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(bot_id),
                    "encrypted_credentials": created_agent.encrypted_token,
                    "is_primary": True,
                    "is_active": True,
                }
            )

    try:
        await _sync_telegram_bot_webhook(token_value, bot_id, enabled=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return JSONResponse(content={"bot_id": bot_id}, status_code=status.HTTP_201_CREATED)



@router.post("/by_userbot_session")
async def create_agent_by_userbot_session(
    new_agent: NewAgent_byUserbotSession,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    api_id, api_hash = _resolve_userbot_api_pair(new_agent.api_id, new_agent.api_hash)
    session_string = new_agent.session_string.strip()
    me = await _validate_userbot_session(api_id=api_id, api_hash=api_hash, session_string=session_string)

    telegram_user_id = getattr(me, "id", None)
    if telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telethon не вернул идентификатор userbot",
        )

    username = getattr(me, "username", None)
    if username:
        bot_username = username
    else:
        first_name = (getattr(me, "first_name", "") or "").strip()
        last_name = (getattr(me, "last_name", "") or "").strip()
        fallback_name = " ".join(part for part in [first_name, last_name] if part).strip()
        bot_username = fallback_name or f"user_{telegram_user_id}"

    userbot_bundle = encrypt_token(
        json.dumps(
            {
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string,
                "phone_number": None,
                "telegram_user_id": telegram_user_id,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(new_agent.template_type)
            template_config = _normalize_template_config(template_type, new_agent.template_config)
            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=telegram_user_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже зарегистрирован",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_userbot",
                external_id=str(telegram_user_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже подключен к другому агенту",
                )

            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": telegram_user_id,
                    "primary_provider": "telegram_userbot",
                    "template_type": template_type,
                    "template_config": template_config,
                    "encrypted_token": encrypt_token(session_string),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": bot_username,
                    "system_prompt": new_agent.system_prompt.strip(),
                    "is_active": True,
                }
            )
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(new_agent.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_userbot",
                    "connection_type": "userbot",
                    "external_id": str(telegram_user_id),
                    "encrypted_credentials": userbot_bundle,
                    "is_primary": True,
                    "is_active": True,
                }
            )

    return JSONResponse(
        content={"bot_id": telegram_user_id, "connection_type": "telegram_userbot"},
        status_code=status.HTTP_201_CREATED,
    )



@router.post("/userbot/request_code")
async def request_userbot_code(
    payload: UserbotRequestCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    phone_number = payload.phone_number.strip()

    try:
        from telethon.errors import FloodWaitError
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client, api_id, api_hash = create_telegram_client(
        api_id=payload.api_id,
        api_hash=payload.api_hash.strip() if payload.api_hash else None,
        prefer_desktop=True,
    )
    phone_code_hash = None
    pending_session_string = ""
    try:
        await client.connect()
        sent = await client.send_code_request(phone=phone_number)
        phone_code_hash = getattr(sent, "phone_code_hash", None)
        if not phone_code_hash:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telegram не вернул phone_code_hash",
            )
        pending_session_string = client.session.save()
    except FloodWaitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много попыток. Подождите {exc.seconds} сек",
        )
    except HTTPException:
        raise
    except Exception as exc:
        detail = f"Не удалось отправить код подтверждения Telegram: {exc}"
        if "api_id/api_hash combination is invalid" in str(exc).lower():
            detail = (
                "Telegram отклонил API-ключи. Попробуйте вход по QR-код "
                "или задайте TELEGRAM_USERBOT_API_ID и TELEGRAM_USERBOT_API_HASH в .env "
                "(пара с my.telegram.org)."
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )
    finally:
        await client.disconnect()

    auth_token = _create_userbot_auth_token(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        phone_code_hash=phone_code_hash,
        encrypted_pending_session=encrypt_token(pending_session_string),
    )
    return JSONResponse(content={"auth_token": auth_token}, status_code=status.HTTP_200_OK)



@router.post("/userbot/verify_code")
async def verify_userbot_code(
    payload: UserbotVerifyCode, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    phone_number = token_data["phone_number"]
    phone_code_hash = token_data["phone_code_hash"]
    pending_session_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_session_enc) if pending_session_enc else ""

    code = "".join(ch for ch in payload.code.strip() if ch.isdigit())
    password = payload.password.strip() if payload.password else None
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Введите код подтверждения (цифры из Telegram)",
        )

    try:
        from telethon.errors import (
            PhoneCodeExpiredError,
            PhoneCodeInvalidError,
            SessionPasswordNeededError,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client, api_id, api_hash = create_telegram_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=pending_session or "",
        prefer_desktop=True,
    )
    try:
        await client.connect()
        try:
            await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Для этого аккаунта включен пароль 2FA. Передайте поле password.",
                )
            await client.sign_in(password=password)
        except PhoneCodeInvalidError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неверный код подтверждения Telegram",
            )
        except PhoneCodeExpiredError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Код подтверждения Telegram истек. Запросите новый код.",
            )

        me = await client.get_me()
        if not me:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telethon не смог получить профиль пользователя после входа",
            )
        session_string = client.session.save()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("userbot verify_code failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось подтвердить код Telegram: {exc}",
        )
    finally:
        await client.disconnect()

    return JSONResponse(
        content={
            "session_string": session_string,
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_number": phone_number,
            "telegram_id": getattr(me, "id", None),
            "username": getattr(me, "username", None),
            "first_name": getattr(me, "first_name", None),
            "last_name": getattr(me, "last_name", None),
        },
        status_code=status.HTTP_200_OK,
    )



@router.post("/userbot/qr/start")
async def userbot_qr_start(
    payload: UserbotQrStart, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    api_id, api_hash = _resolve_userbot_api_pair(
        payload.api_id,
        payload.api_hash.strip() if payload.api_hash else None,
        prefer_desktop=True,
    )
    try:
        result = await start_qr_login(api_id=api_id, api_hash=api_hash)
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось начать QR-вход Telegram: {exc}",
        ) from exc

    auth_token = _create_userbot_qr_auth_token(
        api_id=api_id,
        api_hash=api_hash,
        auth_id=str(result["auth_id"]),
        encrypted_pending_session=encrypt_token(str(result.get("pending_session_string") or "")),
    )
    content: dict[str, Any] = {
        "auth_token": auth_token,
        "qr_url": result.get("qr_url") or "",
        "qr_data_url": result.get("qr_data_url") or "",
        "already_authorized": bool(result.get("already_authorized")),
    }
    if result.get("already_authorized"):
        content["session_string"] = str(result.get("pending_session_string") or "")
        content["api_id"] = result.get("api_id", api_id)
        content["api_hash"] = result.get("api_hash", api_hash)
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)



@router.post("/userbot/qr/status")
async def userbot_qr_status(
    payload: UserbotQrStatus, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_qr_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    auth_id = str(token_data["auth_id"])
    qr_state = await get_qr_status(auth_id=auth_id)

    response: dict[str, Any] = {
        "status": qr_state.get("status") or "pending",
        "error": qr_state.get("error"),
        "api_id": api_id,
        "api_hash": api_hash,
    }
    if qr_state.get("status") == "success":
        session_string = str(qr_state.get("session_string") or "").strip()
        if not session_string:
            pending_enc = token_data.get("encrypted_pending_session")
            if pending_enc:
                session_string = decrypt_token(pending_enc)
        if qr_state.get("api_id"):
            response["api_id"] = int(qr_state["api_id"])
        if qr_state.get("api_hash"):
            response["api_hash"] = str(qr_state["api_hash"])
        me = qr_state.get("me") if isinstance(qr_state.get("me"), dict) else {}
        response.update(
            {
                "session_string": session_string,
                "telegram_id": me.get("telegram_id"),
                "username": me.get("username"),
                "first_name": me.get("first_name"),
                "last_name": me.get("last_name"),
                "phone_number": me.get("phone_number"),
            }
        )
    elif qr_state.get("status") == "need_2fa":
        pending_enc = token_data.get("encrypted_pending_session")
        if qr_state.get("session_string"):
            response["pending_session_string"] = qr_state.get("session_string")
        elif pending_enc:
            response["pending_session_string"] = decrypt_token(pending_enc)
    return JSONResponse(content=response, status_code=status.HTTP_200_OK)



@router.post("/userbot/qr/verify_2fa")
async def userbot_qr_verify_2fa(
    payload: UserbotQrVerify2fa, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_data = _decode_userbot_qr_auth_token(payload.auth_token.strip())
    api_id = int(token_data["api_id"])
    api_hash = decrypt_token(token_data["encrypted_api_hash"])
    pending_enc = token_data.get("encrypted_pending_session")
    pending_session = decrypt_token(pending_enc) if pending_enc else ""

    qr_state = await get_qr_status(auth_id=str(token_data["auth_id"]))
    if qr_state.get("session_string"):
        pending_session = str(qr_state["session_string"])

    try:
        result = await complete_qr_2fa(
            api_id=api_id,
            api_hash=api_hash,
            session_string=pending_session,
            password=payload.password,
        )
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось подтвердить 2FA Telegram: {exc}",
        ) from exc

    return JSONResponse(content=result, status_code=status.HTTP_200_OK)



@router.post("/userbot/import_session")
async def userbot_import_session(
    session_file: UploadFile = File(...),
    api_id: int | None = Form(default=None),
    api_hash: str | None = Form(default=None),
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
        custom_hash = api_hash.strip() if api_hash else None
        custom_id = int(api_id) if api_id is not None and int(api_id) > 0 else None
        result = await import_session_file(
            api_id=custom_id,
            api_hash=custom_hash,
            filename=session_file.filename or "upload",
            content=raw,
        )
    except TelegramUserbotAuthError as exc:
        raise _userbot_auth_http_error(exc) from exc
    except Exception as exc:
        logger.warning("userbot import_session failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось импортировать сессию: {exc}",
        ) from exc

    return JSONResponse(content=result, status_code=status.HTTP_200_OK)



@router.post("/channels/by_youtube_oauth_start")
async def start_agent_youtube_oauth(
    payload: YouTubeOAuthStartPayload,
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
            redirect_uri = str(payload.redirect_uri or settings.YOUTUBE_OAUTH_REDIRECT_URI or "").strip()
            if not redirect_uri:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="YouTube OAuth redirect_uri не настроен",
                )
            state = _create_youtube_oauth_state(
                user_id=current_user.id,
                agent_id=agent.id,
                redirect_uri=redirect_uri,
            )
            auth_url = get_youtube_client().build_oauth_authorization_url(
                state=state,
                redirect_uri=redirect_uri,
            )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "auth_url": auth_url,
                    "state": state,
                    "redirect_uri": redirect_uri,
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/channels/by_youtube_oauth_callback")
async def complete_agent_youtube_oauth(payload: YouTubeOAuthCallbackPayload):
    code = payload.code.strip()
    state = payload.state.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Пустой OAuth code YouTube")
    token_data = _decode_youtube_oauth_state(state)
    agent_id = int(token_data["agent_id"])
    user_id = int(token_data["user_id"])
    redirect_uri = str(token_data.get("redirect_uri") or "").strip()

    youtube_client = get_youtube_client()
    token_bundle = await youtube_client.exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)
    health = await youtube_client.health_check(token_bundle=token_bundle)
    effective_bundle = health.get("token_bundle") or token_bundle
    external_id = str(health.get("external_id") or "").strip() or "youtube"

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            agent = await session.scalar(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.user_id == user_id,
                )
            )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found for OAuth state")

            duplicate_connection = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.provider == "youtube",
                    AgentChannelConnection.external_id == external_id,
                    AgentChannelConnection.agent_id != agent.id,
                )
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот YouTube канал уже подключен к другому агенту",
                )

            encrypted_bundle = encrypt_token(json.dumps(effective_bundle, ensure_ascii=False))
            existing = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "youtube",
                    AgentChannelConnection.connection_type == "oauth",
                )
            )
            now = datetime.utcnow()
            if existing:
                existing.external_id = external_id
                existing.encrypted_credentials = encrypted_bundle
                existing.is_active = True
                existing.updated_at = now
            else:
                await channel_connection_dao.add(
                    {
                        "agent_id": agent.id,
                        "provider": "youtube",
                        "connection_type": "oauth",
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_bundle,
                        "is_primary": False,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                    "youtube_health": {
                        "ok": bool(health.get("ok")),
                        "provider": "youtube",
                        "external_id": external_id,
                        "details": health.get("details") or {},
                    },
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/channels/youtube/health")
async def youtube_health(
    payload: YouTubeHealthPayload = Depends(),
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
            channel = await _get_youtube_oauth_channel_for_agent(session, agent.id)
            if not channel or not channel.encrypted_credentials:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="YouTube OAuth канал не подключен",
                )
            try:
                bundle_raw = decrypt_token(channel.encrypted_credentials)
                bundle = json.loads(bundle_raw)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Поврежденный bundle YouTube OAuth в канале",
                )
            health = await get_youtube_client().health_check(token_bundle=bundle)
            updated_bundle = health.get("token_bundle") or bundle
            channel.encrypted_credentials = encrypt_token(json.dumps(updated_bundle, ensure_ascii=False))
            channel.external_id = str(health.get("external_id") or channel.external_id or "youtube")
            channel.updated_at = datetime.utcnow()
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "connection": _serialize_channel_connection(channel),
                    "health": {
                        "ok": bool(health.get("ok")),
                        "provider": "youtube",
                        "external_id": channel.external_id,
                        "details": health.get("details") or {},
                    },
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/channels/by_token")
async def add_agent_telegram_bot_channel(
    payload: AddTelegramBotChannel,
    current_user=Depends(get_current_user_required),
):
    token_value = payload.bot_token.strip()
    try:
        me = await _telegram_get_me(token_value)
    except Exception as exc:
        _raise_telegram_token_check_http_exception(exc)
    if not me or me.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный API ключ Telegram бота",
        )
    result = me.get("result") or {}
    telegram_bot_id = result.get("id")
    bot_username = result.get("username")
    if telegram_bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram не вернул bot id по указанному токену",
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
            existing_bot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "telegram_bot",
                    AgentChannelConnection.connection_type == "bot",
                )
            )
            if existing_bot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен Telegram бот-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_bot",
                external_id=str(telegram_bot_id),
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(telegram_bot_id),
                    "encrypted_credentials": encrypt_token(token_value),
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

            if agent.is_active:
                await _sync_telegram_bot_webhook(token_value, int(created_connection.external_id), enabled=True)

            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_201_CREATED,
            )



@router.post("/channels/by_userbot_session")
async def add_agent_userbot_channel(
    payload: AddTelegramUserbotChannel,
    current_user=Depends(get_current_user_required),
):
    api_id, api_hash = _resolve_userbot_api_pair(
        payload.api_id,
        payload.api_hash.strip() if payload.api_hash else None,
    )
    session_string = payload.session_string.strip()
    me = await _validate_userbot_session(api_id=api_id, api_hash=api_hash, session_string=session_string)

    telegram_user_id = getattr(me, "id", None)
    if telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telethon не вернул идентификатор userbot",
        )

    userbot_bundle = encrypt_token(
        json.dumps(
            {
                "api_id": api_id,
                "api_hash": api_hash,
                "session_string": session_string,
                "phone_number": None,
                "telegram_user_id": telegram_user_id,
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
            existing_userbot_channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == "telegram_userbot",
                    AgentChannelConnection.connection_type == "userbot",
                )
            )
            if existing_userbot_channel and str(agent.template_type or "").strip().lower() != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен Telegram userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="telegram_userbot",
                external_id=str(telegram_user_id),
            )
            if duplicate_connection:
                if int(duplicate_connection.agent_id) == int(agent.id):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Этот Telegram userbot уже подключен к текущему агенту",
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram userbot уже подключен к другому агенту",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": "telegram_userbot",
                    "connection_type": "userbot",
                    "external_id": str(telegram_user_id),
                    "encrypted_credentials": userbot_bundle,
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



@router.post("/telegram/send_to_user")
async def telegram_send_to_user_as_owner(
    payload: AgentTelegramSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    try:
        chat_id = int(payload.user_external_id.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный Telegram user id",
        )
    if chat_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный Telegram user id",
        )
    text = payload.message.strip()
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
            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            userbot_channel = await _get_telegram_userbot_channel_for_agent(session, agent.id)
            preferred_channel = (payload.preferred_channel or "").strip().lower()
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            send_errors: list[str] = []
            delivered = False
            delivered_channel: str | None = None
            if preferred_channel in {"", "telegram"}:
                if telegram_channel and telegram_channel.encrypted_credentials:
                    try:
                        bot_token = decrypt_token(telegram_channel.encrypted_credentials)
                        await _telegram_api_send_message(bot_token, chat_id, text)
                        delivered = True
                        delivered_channel = "telegram"
                    except HTTPException as exc:
                        send_errors.append(str(exc.detail))
                elif preferred_channel == "telegram":
                    send_errors.append("bot-канал не подключен")
            if (not delivered) and preferred_channel in {"", "telegram_userbot"}:
                if userbot_channel and userbot_channel.encrypted_credentials:
                    try:
                        peer_hash = await _latest_telegram_userbot_access_hash(
                            session,
                            analytics_namespace_id=analytics_namespace_id,
                            user_external_id=payload.user_external_id.strip(),
                        )
                        await _telegram_userbot_send_message(
                            userbot_channel.encrypted_credentials,
                            chat_id,
                            text,
                            access_hash=peer_hash,
                        )
                        delivered = True
                        delivered_channel = "telegram_userbot"
                    except HTTPException as exc:
                        send_errors.append(str(exc.detail))
                elif preferred_channel == "telegram_userbot":
                    send_errors.append("userbot-канал не подключен")
            if not delivered:
                joined_errors = "; ".join([err for err in send_errors if err]) or "каналы недоступны"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Не удалось отправить сообщение через bot/userbot: {joined_errors}",
                )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="operator",
                message_text=text,
                channel=delivered_channel or "dashboard",
                user_external_id=str(chat_id),
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)



@router.get("/telegram/broadcast_recipients")
async def telegram_broadcast_recipients(
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
            recipients = await _list_telegram_broadcast_recipient_ids(session, analytics_namespace_id)
            if not recipients:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "telegram_users_total": 0,
                        "frozen_among_telegram": 0,
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
                    "telegram_users_total": len(recipients),
                    "frozen_among_telegram": frozen_among,
                    "eligible_when_skip_frozen": eligible,
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/telegram/broadcast")
async def telegram_broadcast_as_owner(
    payload: AgentTelegramBroadcastPayload,
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
            recipients = await _list_telegram_broadcast_recipient_ids(session, analytics_namespace_id)
            agent_pk = agent.id
            telegram_bot_id = analytics_namespace_id
            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            userbot_channel = await _get_telegram_userbot_channel_for_agent(session, agent.id)
            bot_token = (
                decrypt_token(telegram_channel.encrypted_credentials)
                if telegram_channel and telegram_channel.encrypted_credentials
                else None
            )
            userbot_bundle = (
                userbot_channel.encrypted_credentials
                if userbot_channel and userbot_channel.encrypted_credentials
                else None
            )
            if not bot_token and not userbot_bundle:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="У агента нет активного Telegram bot/userbot канала для рассылки",
                )

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

    userbot_uids = [r["user_external_id"] for r in to_send if r["channel"] == "telegram_userbot"]
    userbot_access: dict[str, int] = {}
    if userbot_uids:
        async with async_session_maker() as session:
            async with session.begin():
                userbot_access = await _map_telegram_userbot_access_hashes(
                    session,
                    analytics_namespace_id=telegram_bot_id,
                    user_external_ids=userbot_uids,
                )

    sent = 0
    failed = 0
    errors: list[dict] = []
    throttle_seconds = 0.05

    for recipient in to_send:
        uid = recipient["user_external_id"]
        channel = recipient["channel"]
        chat_id = int(uid)
        try:
            if channel == "telegram":
                if not bot_token:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="bot-канал не подключен",
                    )
                await _telegram_api_send_message(bot_token, chat_id, text)
            elif channel == "telegram_userbot":
                if not userbot_bundle:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="userbot-канал не подключен",
                    )
                peer_hash = userbot_access.get(uid)
                await _telegram_userbot_send_message(
                    userbot_bundle,
                    chat_id,
                    text,
                    access_hash=peer_hash,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Неподдерживаемый канал рассылки: {channel}",
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


