"""Agent routes: core."""
from fastapi import APIRouter

from .shared import *  # noqa: F403

router = APIRouter()

@router.get("")
async def read_agent(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            resolved_channel = None
            if agent_id is not None:
                found_agent = await agent_dao.find_one_by_filter(id=agent_id)
            else:
                found_agent, resolved_channel = await _find_agent_by_lookup_id(
                    session=session,
                    agent_dao=agent_dao,
                    lookup_id=bot_id,
                )
            if not found_agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and found_agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            await _ensure_external_api_key(found_agent, agent_dao)
            await _ensure_single_primary_flag(session=session, agent_id=found_agent.id)
            from ..services.agent_billing import enforce_expired_maintenance

            await enforce_expired_maintenance(agent_dao, found_agent)
            channels = await _list_agent_channels(session, found_agent.id)
            crm_connections = await _list_agent_crm_connections(session, found_agent.id)
            http_integrations = await _list_agent_http_integrations(session, found_agent.id)
            billing_user = await _resolve_billing_user(session, found_agent, current_user)
            payload = _serialize_agent(
                found_agent,
                user=billing_user,
                include_external_api_key=True,
                include_encrypted_token=internal,
            )
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            payload["crm_connections"] = [_serialize_crm_connection(item) for item in crm_connections]
            payload["http_integrations"] = [_serialize_http_integration(item) for item in http_integrations]
            if internal and resolved_channel and resolved_channel.encrypted_credentials:
                # Internal webhook lookup by Telegram Bot ID must return that bot token.
                payload["encrypted_token"] = resolved_channel.encrypted_credentials
            return JSONResponse(
                content=payload,
                status_code=status.HTTP_200_OK,
            )



@router.get("/allBy_tgID")
async def read_all_agents(
    tg_id: int | None = Query(default=None, alias="id"),
    project_id: int | None = Query(default=None, description="Filter agents by project_id"),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        async with session.begin():
            if current_user:
                user = await user_dao.find_one_by_filter(load_relations=True, id=current_user.id)
            else:
                if tg_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Query parameter 'id' is required for internal requests",
                    )
                user = await user_dao.find_one_by_filter(load_relations=True, telegram_id=tg_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            from ..services.agent_billing import enforce_expired_maintenance

            serialized_agents = []
            
            # Use DAO method for project filtering
            if project_id is not None:
                agents = await agent_dao.find_all_by_user_id_and_project(user.id, project_id)
            else:
                agents = user.agents or []
            
            for agent in agents:
                await enforce_expired_maintenance(agent_dao, agent)
                serialized_agents.append(
                    _serialize_agent(agent, user=user, include_encrypted_token=internal)
                )
            return JSONResponse(
                content=serialized_agents,
                status_code=status.HTTP_200_OK,
            )



@router.post("")
async def create_empty_agent(
    payload: CreateEmptyAgent,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)

        async with session.begin():
            # Keep legacy project linkage optional only when explicitly provided.
            # New agents are no longer auto-attached to a default project.
            project_id = payload.project_id
            if project_id is not None:
                from ..dao.project_dao import ProjectDAO
                project_dao = ProjectDAO(session)
                # Validate that project exists and belongs to user
                project = await project_dao.get_by_id(session, project_id)
                if not project or project.user_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid project_id",
                    )
            
            template_type = _normalize_template_type(payload.template_type)
            template_config = _normalize_template_config(template_type, payload.template_config)
            external_api_key = generate_agent_external_api_key()
            
            agent_data = {
                "user_id": current_user.id,
                "bot_id": None,
                "primary_provider": "none",
                "template_type": template_type,
                "template_config": template_config,
                "encrypted_token": encrypt_token(f"agent:{current_user.id}:{datetime.utcnow().timestamp()}"),
                "encrypted_external_api_key": encrypt_token(external_api_key),
                "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                "bot_username": None,
                "system_prompt": payload.system_prompt.strip(),
                "is_active": True,
                **_initial_agent_billing_fields(template_type, user=current_user),
            }
            
            # Add project_id if determined
            if project_id:
                agent_data["project_id"] = project_id
            
            created_agent = await agent_dao.add(agent_data)
            await session.flush()
            if template_type == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(payload.system_prompt or "").strip(),
                    template_config_json=template_config,
                )
            return JSONResponse(
                content=_serialize_agent(created_agent, user=current_user, include_external_api_key=True),
                status_code=status.HTTP_201_CREATED,
            )



@router.post("/ByUserWith_tgID")
async def create_agent_by_tg_id(
    new_agent: NewAgent_byUserWith_tgID,
    background_tasks: BackgroundTasks,
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=new_agent.tg_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            if user.is_banned:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=new_agent.bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован",
                )

            payload = new_agent.model_dump()
            payload["template_type"] = _normalize_template_type(payload.get("template_type"))
            payload["template_config"] = _normalize_template_config(
                payload["template_type"],
                payload.get("template_config"),
            )
            payload["user_id"] = user.id
            del payload["tg_id"]
            payload["primary_provider"] = "telegram_bot"
            external_api_key = generate_agent_external_api_key()
            payload["encrypted_external_api_key"] = encrypt_token(external_api_key)
            payload["external_api_key_hash"] = hash_agent_external_api_key(external_api_key)
            created_agent = await agent_dao.add(payload)
            await session.flush()
            if payload["template_type"] == "sales_manager":
                background_tasks.add_task(
                    _schedule_sales_trigger_words_generation,
                    agent_id=int(created_agent.id),
                    system_prompt=str(payload.get("system_prompt") or "").strip(),
                    template_config_json=payload.get("template_config"),
                )
            await channel_connection_dao.add(
                {
                    "agent_id": created_agent.id,
                    "provider": "telegram_bot",
                    "connection_type": "bot",
                    "external_id": str(created_agent.bot_id),
                    "encrypted_credentials": created_agent.encrypted_token,
                    "is_primary": True,
                    "is_active": True,
                }
            )
    return Response(status_code=status.HTTP_201_CREATED)



@router.get("/channels")
async def list_agent_channels(
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
            await _ensure_single_primary_flag(session=session, agent_id=agent.id)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/channels/add-telephony")
async def add_agent_telephony_channel(
    payload: AddTelephonyChannel,
    current_user=Depends(get_current_user_required),
):
    if not settings.TELEPHONY_WEBHOOK_BASE_URL.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_WEBHOOK_BASE_URL не настроен на сервере",
        )
    require_platform_telephony_config()
    creds = await validate_telephony_credentials_input(payload)
    external_id = telephony_external_id(creds.phone_number_e164, creds.routing_extension)
    encrypted_bundle = build_encrypted_telephony_bundle(creds, encrypt_token)

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        channel_connection_dao = AgentChannelConnectionDAO(session)
        async with session.begin():
            if creds.routing_extension:
                conflict = await scan_extension_conflict_in_db(
                    session,
                    creds.routing_extension,
                )
                if conflict is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Добавочный {creds.routing_extension} уже занят",
                    )
            lookup_agent_id, lookup_bot_id = _resolve_lookup(payload)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=False,
            )
            existing = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.agent_id == agent.id,
                    AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
                )
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключена телефония",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider=TELEPHONY_CHANNEL_PROVIDER,
                external_id=external_id,
            )
            if duplicate_connection:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Добавочный {creds.routing_extension} уже занят другим агентом",
                )

            now = datetime.utcnow()
            created_connection = await channel_connection_dao.add(
                {
                    "agent_id": agent.id,
                    "provider": TELEPHONY_CHANNEL_PROVIDER,
                    "connection_type": "api",
                    "external_id": external_id,
                    "encrypted_credentials": encrypted_bundle,
                    "is_primary": bool(payload.make_primary),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.flush()
            await sync_channel_routes(
                connection_id=int(created_connection.id),
                agent_id=int(agent.id),
                creds=creds,
            )
            if payload.make_primary:
                await _set_primary_channel(
                    session=session,
                    agent_id=agent.id,
                    connection_id=created_connection.id,
                )
            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            extra = telephony_connect_response_extra(int(created_connection.id))
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                    "telephony_routing": telephony_routing_public_fields(creds),
                    "telephony_platform": platform_telephony_public_fields(),
                    **extra,
                },
                status_code=status.HTTP_201_CREATED,
            )



@router.delete("/channels")
async def delete_agent_channel(
    payload: DeleteAgentChannel = Depends(),
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
            channel = await session.scalar(
                select(AgentChannelConnection).where(
                    AgentChannelConnection.id == payload.connection_id,
                    AgentChannelConnection.agent_id == agent.id,
                )
            )
            if not channel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Канал подключения не найден")

            channels_before = await _list_agent_channels(session, agent.id)
            if len(channels_before) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Нельзя удалить единственный канал агента. Подключите новый канал сначала.",
                )

            if channel.provider == "telegram_bot" and channel.encrypted_credentials:
                bot_token = decrypt_token(channel.encrypted_credentials)
                try:
                    await _sync_telegram_bot_webhook(bot_token, int(channel.external_id), enabled=False)
                except HTTPException:
                    # Do not block channel deletion if webhook is already detached.
                    pass
            await _terminate_channel_session_if_supported(channel)

            deleting_primary = bool(channel.is_primary)
            await session.delete(channel)
            await session.flush()

            channels_after = await _list_agent_channels(session, agent.id)
            if deleting_primary and channels_after:
                channels_after[0].is_primary = True
                channels_after[0].updated_at = datetime.utcnow()

            await _sync_agent_primary_fields(agent=agent, agent_dao=agent_dao, session=session)
            channels = await _list_agent_channels(session, agent.id)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "channels": [_serialize_channel_connection(item) for item in channels],
                },
                status_code=status.HTTP_200_OK,
            )



@router.patch("/by_botID")
async def update_by_bot_id(
    new_data: UpdateAgent,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(new_data)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            updates = new_data.model_dump(exclude_none=True)
            updates.pop("bot_id", None)
            updates.pop("agent_id", None)
            if "yookassa_api_key" in updates:
                raw_yookassa_key = str(updates.pop("yookassa_api_key") or "").strip()
                if raw_yookassa_key:
                    if ":" not in raw_yookassa_key:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="yookassa_api_key must be in format shop_id:secret_key",
                        )
                    shop_id_part, secret_part = raw_yookassa_key.split(":", 1)
                    if not shop_id_part.strip() or not secret_part.strip():
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="yookassa_api_key must include both shop_id and secret_key",
                        )
                    updates["encrypted_booking_payment_api_key"] = encrypt_booking_payment_secret(raw_yookassa_key)
                else:
                    updates["encrypted_booking_payment_api_key"] = None
            if "external_webhook_url" in updates:
                updates["external_webhook_url"] = _normalize_external_webhook_url(updates["external_webhook_url"])
            if "template_type" in updates:
                updates["template_type"] = _normalize_template_type(updates["template_type"])
                if "template_config" not in updates:
                    if updates["template_type"] == "crm_admin":
                        updates["template_config"] = _normalize_template_config("crm_admin", None)
                    else:
                        updates["template_config"] = None
            if "template_config" in updates:
                normalized_type = _normalize_template_type(updates.get("template_type") or agent.template_type)
                updates["template_type"] = normalized_type
                updates["template_config"] = _normalize_template_config(
                    normalized_type,
                    updates.get("template_config"),
                )
                if normalized_type == "sales_manager":
                    try:
                        normalized_config = json.loads(updates["template_config"] or "{}")
                    except Exception:
                        normalized_config = {}
                    lead_generation_enabled = bool(normalized_config.get("lead_generation_enabled", True))
                    neuro_commenting_enabled = bool(normalized_config.get("neuro_commenting_enabled", False))
                    live_chat_simulation_enabled = bool(
                        normalized_config.get("live_chat_simulation_enabled", False)
                    )
                    if (
                        not lead_generation_enabled
                        and not neuro_commenting_enabled
                        and not live_chat_simulation_enabled
                    ):
                        updates["is_active"] = False
            await agent_dao.update(agent, updates)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.patch("/toggle_status")
async def toggle_status(
    agent_id: Agent_by_botID,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(agent_id)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            from ..services.agent_billing import enforce_expired_maintenance

            await enforce_expired_maintenance(agent_dao, agent)
            new_status = not agent.is_active
            billing_user = await _resolve_billing_user(session, agent, current_user)
            if new_status:
                from ..agent_template_pricing import (
                    PAYMENT_KIND_AGENT_MAINTENANCE,
                    build_agent_billing_state,
                    get_agent_template_pricing,
                    is_activation_paid,
                    is_maintenance_current,
                    user_has_free_agent_activation,
                )

                pricing = get_agent_template_pricing(agent.template_type)
                if (
                    pricing
                    and (
                        pricing.setup_rub_min <= 0
                        or user_has_free_agent_activation(billing_user)
                    )
                    and not is_activation_paid(agent, user=billing_user)
                ):
                    await agent_dao.update(
                        agent,
                        {"activation_paid_at": datetime.now(timezone.utc).replace(tzinfo=None)},
                    )
                    agent = await agent_dao.find_one_by_filter(id=agent.id)
                if pricing and pricing.monthly_maintenance_rub_min > 0 and not is_maintenance_current(agent):
                    billing = build_agent_billing_state(agent, user=billing_user)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "message": "Для активации агента требуется оплата подписки",
                            "billing": billing,
                            "payment_kind": PAYMENT_KIND_AGENT_MAINTENANCE,
                        },
                    )
                if not is_activation_paid(agent, user=billing_user):
                    billing = build_agent_billing_state(agent, user=billing_user)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "message": "Для активации агента требуется оплата",
                            "billing": billing,
                            "payment_kind": "agent_activation",
                        },
                    )
            await agent_dao.update(agent, {"is_active": new_status})

            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            if telegram_channel and telegram_channel.encrypted_credentials:
                agent_token = decrypt_token(telegram_channel.encrypted_credentials)
                try:
                    await _sync_telegram_bot_webhook(
                        agent_token,
                        int(telegram_channel.external_id),
                        enabled=new_status,
                    )
                except HTTPException as exc:
                    if not new_status and exc.status_code == status.HTTP_502_BAD_GATEWAY:
                        # Webhook may already be removed; do not block deactivation.
                        pass
                    else:
                        raise

            channels = await _list_agent_channels(session, agent.id)
            payload = _serialize_agent(
                agent,
                user=billing_user,
                include_external_api_key=True,
                include_encrypted_token=internal,
            )
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            return JSONResponse(
                content=payload,
                status_code=status.HTTP_200_OK,
            )



@router.patch("/autopay")
async def update_agent_autopay(
    payload: AgentAutopayUpdateRequest,
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
            from ..agent_template_pricing import build_agent_billing_state, get_agent_template_pricing

            pricing = get_agent_template_pricing(agent.template_type)
            if not pricing or pricing.monthly_maintenance_rub_min <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Автопродление доступно только для платных агентов",
                )
            if payload.enabled and not getattr(agent, "yookassa_payment_method_id", None):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Сначала оплатите подписку с включённым автопродлением, "
                        "чтобы сохранить способ оплаты"
                    ),
                )
            updates: dict[str, object] = {
                "autopay_enabled": payload.enabled,
                "autopay_last_error": None if payload.enabled else agent.autopay_last_error,
            }
            await agent_dao.update(agent, updates)
            agent = await agent_dao.find_one_by_filter(id=agent.id)
            billing_user = await _resolve_billing_user(session, agent, current_user)
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "autopay_enabled": bool(agent.autopay_enabled),
                    "billing": build_agent_billing_state(agent, user=billing_user),
                },
                status_code=status.HTTP_200_OK,
            )



@router.delete("")
async def delete_by_bot_id(
    agent_id: Agent_by_botID = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            lookup_agent_id, lookup_bot_id = _resolve_lookup(agent_id)
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=lookup_agent_id,
                bot_id=lookup_bot_id,
                session=session,
                current_user=current_user,
                internal=internal,
            )
            vector_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id
            is_deleted_vectors = await delete_agent_vectors(vector_namespace_id)
            if not is_deleted_vectors:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Qdrant deleting error",
                )
            channels = await _list_agent_channels(session, agent.id)
            for channel in channels:
                await _terminate_channel_session_if_supported(channel)
            await agent_dao.delete(agent)
    return Response(status_code=status.HTTP_200_OK)



def _extract_json_object(raw_text: str) -> dict:
    content = (raw_text or "").strip()
    if not content:
        raise ValueError("Empty AI response")
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group(0)
    return json.loads(content)


def _sanitize_agent_ai_draft(payload: AgentAIDraftRequest, draft_raw: dict) -> AgentAIDraftResponse:
    suggested_name = str(draft_raw.get("suggested_name") or "").strip()
    template_type = str(draft_raw.get("template_type") or "qa").strip().lower()
    system_prompt = str(draft_raw.get("system_prompt") or "").strip()
    welcome_message = str(draft_raw.get("welcome_message") or "").strip()
    template_config_raw = draft_raw.get("template_config")

    if not suggested_name:
        suggested_name = "ИИ-ассистент"

    normalized_template = _normalize_template_type(template_type)
    if normalized_template not in {"qa", "crm_admin", "sales_manager"}:
        normalized_template = "qa"

    if len(system_prompt) < 80:
        context = payload.project_context.strip() if payload.project_context else "вашего бизнеса"
        system_prompt = (
            f"Ты — AI-агент для {context}. Твоя задача: {payload.brief.strip()}. "
            "Отвечай по делу, уточняй детали, предлагай следующий шаг, не выдумывай факты."
        )
    if len(system_prompt) > 5000:
        system_prompt = system_prompt[:5000]

    # Remove unresolved placeholders from model output.
    system_prompt = re.sub(r"\{\{[^}]+\}\}", "", system_prompt)
    system_prompt = re.sub(r"\$\{[^}]+\}", "", system_prompt)
    system_prompt = re.sub(r"\s{2,}", " ", system_prompt).strip()

    if not welcome_message:
        welcome_message = "Здравствуйте! Чем могу помочь?"
    if len(welcome_message) > 500:
        welcome_message = welcome_message[:500]

    if isinstance(template_config_raw, dict):
        normalized_config_json = _normalize_template_config(normalized_template, template_config_raw)
    else:
        normalized_config_json = _normalize_template_config(normalized_template, {})
    template_config = json.loads(normalized_config_json) if normalized_config_json else None

    return AgentAIDraftResponse(
        suggested_name=suggested_name[:100],
        template_type=normalized_template,
        system_prompt=system_prompt,
        welcome_message=welcome_message,
        template_config=template_config,
    )


@router.post(
    "/ai/generate-draft",
    response_model=AgentAIDraftResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="agent_ai_generate_draft"))],
)
async def ai_generate_draft(
    payload: AgentAIDraftRequest,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    context_line = f"Контекст проекта: {payload.project_context.strip()}" if payload.project_context else ""
    system_prompt = (
        "Ты senior AI architect. Сгенерируй JSON для создания одного агента.\n"
        "Только valid JSON, без markdown.\n"
        "template_type выбирай только из: qa, crm_admin, sales_manager.\n"
        "system_prompt: 400-1800 символов, русский язык, без {{placeholders}}.\n"
        "welcome_message: 1-2 коротких предложения.\n"
        "template_config: объект под выбранный template_type (можно пустой объект).\n"
    )
    user_prompt = (
        f"Задача пользователя:\n{payload.brief.strip()}\n\n"
        f"{context_line}\n\n"
        "Верни JSON формата:\n"
        "{\n"
        '  "suggested_name": "...",\n'
        '  "template_type": "qa|crm_admin|sales_manager",\n'
        '  "system_prompt": "...",\n'
        '  "welcome_message": "...",\n'
        '  "template_config": {}\n'
        "}"
    )

    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=1800,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or ""
        parsed = _extract_json_object(raw_content)
        return _sanitize_agent_ai_draft(payload, parsed)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to generate AI draft for agent")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось сгенерировать заготовку агента через ИИ",
        )


@router.post("/ai/improve_prompt")
async def ai_improve_prompt(
    payload: AgentAIAction,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )

            try:
                improved_prompt = await improve_prompt_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось улучшить системный промпт через ИИ",
                )

            await agent_dao.update(agent, {"system_prompt": improved_prompt})
            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "system_prompt": improved_prompt},
                status_code=status.HTTP_200_OK,
            )



@router.post("/ai/generate_welcome")
async def ai_generate_welcome(
    payload: AgentAIAction,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )

            try:
                welcome_message = await generate_welcome_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось сгенерировать приветствие через ИИ",
                )

            await agent_dao.update(agent, {"welcome_message": welcome_message})
            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "welcome_message": welcome_message},
                status_code=status.HTTP_200_OK,
            )



@router.post("/external/regenerate_key")
async def regenerate_external_api_key(
    payload: Agent_by_botID,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            await _regenerate_external_api_key(agent, agent_dao)
            billing_user = await _resolve_billing_user(session, agent, current_user)
            return JSONResponse(
                content=_serialize_agent(
                    agent,
                    user=billing_user,
                    include_external_api_key=True,
                    include_encrypted_token=internal,
                ),
                status_code=status.HTTP_200_OK,
            )



@router.post("/analytics/messages/log")
async def log_analytics_message(
    request: Request,
    payload: AgentAnalyticsMessageLog,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    if internal:
        await verify_internal_signature(request)
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
                internal=internal,
            )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role=payload.role,
                message_text=payload.message_text,
                channel=payload.channel,
                user_external_id=payload.user_external_id,
                user_display_name=payload.user_display_name,
                telegram_peer_access_hash=payload.telegram_peer_access_hash,
                tool_name=payload.tool_name,
                tool_args_hash=payload.tool_args_hash,
                tool_status=payload.tool_status,
                latency_ms=payload.latency_ms,
                crm_provider=payload.crm_provider,
            )
    return Response(status_code=status.HTTP_201_CREATED)



@router.get("/analytics/summary")
async def read_analytics_summary(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            total_questions = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                    )
                )
            ) or 0

            unique_users = (
                await session.scalar(
                    select(func.count(func.distinct(AgentAnalyticsMessage.user_external_id))).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                        AgentAnalyticsMessage.user_external_id.is_not(None),
                    )
                )
            ) or 0

            per_user_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.min(AgentAnalyticsMessage.created_at).label("first_at"),
                            func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                            func.count(AgentAnalyticsMessage.id).label("questions"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(AgentAnalyticsMessage.user_external_id)
                    )
                )
                .mappings()
                .all()
            )

            returning_users_over_time = 0
            for row in per_user_rows:
                first_at = row["first_at"]
                last_at = row["last_at"]
                if first_at and last_at and last_at > first_at:
                    returning_users_over_time += 1

            avg_questions_per_user = (float(total_questions) / unique_users) if unique_users > 0 else 0.0
            qualified_leads_share_percent = (
                (float(returning_users_over_time) / unique_users) * 100.0 if unique_users > 0 else 0.0
            )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "unique_users": unique_users,
                    "total_questions": total_questions,
                    "returned_over_time_users": returning_users_over_time,
                    "avg_questions_per_user": round(avg_questions_per_user, 2),
                    "qualified_leads_share_percent": round(qualified_leads_share_percent, 2),
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/analytics/timeseries")
async def read_analytics_timeseries(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=7, le=90),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            first_seen_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.min(AgentAnalyticsMessage.created_at).label("first_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(AgentAnalyticsMessage.user_external_id)
                    )
                )
                .mappings()
                .all()
            )

            # Use cast(..., Date) instead of date_trunc('day', ...): with bound parameters,
            # PostgreSQL can reject GROUP BY when SELECT and GROUP BY date_trunc texts differ.
            day_bucket = cast(AgentAnalyticsMessage.created_at, Date).label("day")
            daily_rows = (
                (
                    await session.execute(
                        select(
                            day_bucket,
                            func.count(AgentAnalyticsMessage.id).label("questions_today"),
                            func.count(func.distinct(AgentAnalyticsMessage.user_external_id)).label("users_today"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(day_bucket)
                    )
                )
                .mappings()
                .all()
            )

            today = datetime.utcnow().date()
            start_day = today - timedelta(days=days - 1)

            daily_activity = {}
            for row in daily_rows:
                day_value = row["day"]
                day_key = day_value.date() if hasattr(day_value, "date") else day_value
                daily_activity[day_key] = {
                    "questions_today": int(row["questions_today"] or 0),
                    "users_today": int(row["users_today"] or 0),
                }

            new_users_by_day = defaultdict(int)
            for row in first_seen_rows:
                first_at = row["first_at"]
                if not first_at:
                    continue
                first_day = first_at.date() if hasattr(first_at, "date") else first_at
                new_users_by_day[first_day] += 1

            timeline = []
            users_all_time = 0
            day_cursor = start_day
            while day_cursor <= today:
                users_all_time += int(new_users_by_day.get(day_cursor, 0))
                current_activity = daily_activity.get(day_cursor, {})
                timeline.append(
                    {
                        "date": day_cursor.isoformat(),
                        "users_all_time": users_all_time,
                        "users_today": int(current_activity.get("users_today", 0)),
                        "new_users": int(new_users_by_day.get(day_cursor, 0)),
                        "questions_today": int(current_activity.get("questions_today", 0)),
                    }
                )
                day_cursor += timedelta(days=1)

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "days": days,
                    "timeline": timeline,
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/analytics/crm_actions")
async def read_analytics_crm_actions(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            tool_calls_total = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name.is_not(None),
                        AgentAnalyticsMessage.tool_name != "fallback_to_text",
                    )
                )
            ) or 0
            successful_tool_calls = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name.is_not(None),
                        AgentAnalyticsMessage.tool_name != "fallback_to_text",
                        AgentAnalyticsMessage.tool_status == "success",
                    )
                )
            ) or 0
            fallback_to_text_count = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.tool_name == "fallback_to_text",
                    )
                )
            ) or 0
            total_questions = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                        AgentAnalyticsMessage.role == "user",
                    )
                )
            ) or 0

            crm_ops_errors = max(0, int(tool_calls_total) - int(successful_tool_calls))
            success_share_percent = (
                (float(successful_tool_calls) / float(tool_calls_total)) * 100.0
                if tool_calls_total > 0
                else 0.0
            )
            fallback_frequency_percent = (
                (float(fallback_to_text_count) / float(total_questions)) * 100.0
                if total_questions > 0
                else 0.0
            )
            error_rate_percent = (
                (float(crm_ops_errors) / float(tool_calls_total)) * 100.0
                if tool_calls_total > 0
                else 0.0
            )

            # Error budget is calculated against a baseline SLO success rate of 95%.
            target_error_budget_percent = 5.0
            error_budget_used_percent = (
                min(100.0, (error_rate_percent / target_error_budget_percent) * 100.0)
                if tool_calls_total > 0
                else 0.0
            )

            latency_rows = (
                (
                    await session.execute(
                        select(AgentAnalyticsMessage.latency_ms).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                            AgentAnalyticsMessage.tool_name != "fallback_to_text",
                            AgentAnalyticsMessage.latency_ms.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            latencies = sorted(int(value) for value in latency_rows if value is not None and int(value) >= 0)
            avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            if latencies:
                p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
                p95_latency_ms = int(latencies[p95_index])
            else:
                p95_latency_ms = 0

            by_tool_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.tool_name,
                            func.count(AgentAnalyticsMessage.id).label("count"),
                        )
                        .where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                            AgentAnalyticsMessage.tool_name != "fallback_to_text",
                        )
                        .group_by(AgentAnalyticsMessage.tool_name)
                        .order_by(func.count(AgentAnalyticsMessage.id).desc())
                    )
                )
                .mappings()
                .all()
            )
            by_status_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.tool_status,
                            func.count(AgentAnalyticsMessage.id).label("count"),
                        )
                        .where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.tool_name.is_not(None),
                        )
                        .group_by(AgentAnalyticsMessage.tool_status)
                        .order_by(func.count(AgentAnalyticsMessage.id).desc())
                    )
                )
                .mappings()
                .all()
            )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "tool_calls_total": int(tool_calls_total),
                    "successful_tool_calls": int(successful_tool_calls),
                    "crm_ops_errors": int(crm_ops_errors),
                    "success_share_percent": round(success_share_percent, 2),
                    "avg_latency_ms": avg_latency_ms,
                    "p95_latency_ms": p95_latency_ms,
                    "fallback_to_text_count": int(fallback_to_text_count),
                    "fallback_frequency_percent": round(fallback_frequency_percent, 2),
                    "error_budget": {
                        "target_error_budget_percent": target_error_budget_percent,
                        "used_percent": round(error_budget_used_percent, 2),
                        "remaining_percent": round(max(0.0, 100.0 - error_budget_used_percent), 2),
                    },
                    "by_tool": [
                        {"tool_name": row["tool_name"], "count": int(row["count"] or 0)}
                        for row in by_tool_rows
                    ],
                    "by_status": [
                        {"tool_status": row["tool_status"] or "unknown", "count": int(row["count"] or 0)}
                        for row in by_status_rows
                    ],
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/analytics/telephony/calls")
async def read_analytics_telephony_calls(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    include_turns: bool = Query(default=True),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            calls = await list_agent_telephony_calls(
                session,
                agent_id=int(agent.id),
                limit=limit,
                include_turns=include_turns,
            )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "calls": calls,
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/content/jobs")
async def list_content_jobs(
    payload: AgentLookup = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            query = select(AgentContentJob).where(AgentContentJob.agent_id == agent.id)
            count_query = select(func.count(AgentContentJob.id)).where(AgentContentJob.agent_id == agent.id)
            normalized_status = str(status_filter or "").strip().lower()
            if normalized_status:
                query = query.where(AgentContentJob.status == normalized_status)
                count_query = count_query.where(AgentContentJob.status == normalized_status)

            total = int((await session.scalar(count_query)) or 0)
            rows = (
                await session.execute(
                    query.order_by(AgentContentJob.created_at.desc(), AgentContentJob.id.desc()).limit(limit).offset(offset)
                )
            ).scalars().all()
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "status_filter": normalized_status or None,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "items": [_serialize_content_job(item) for item in rows],
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/content/jobs/metrics")
async def content_jobs_metrics(
    payload: AgentLookup = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            total = int(
                (await session.scalar(select(func.count(AgentContentJob.id)).where(AgentContentJob.agent_id == agent.id)))
                or 0
            )
            published = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.status == "published",
                        )
                    )
                )
                or 0
            )
            failed = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.status == "failed",
                        )
                    )
                )
                or 0
            )
            retry_jobs = int(
                (
                    await session.scalar(
                        select(func.count(AgentContentJob.id)).where(
                            AgentContentJob.agent_id == agent.id,
                            AgentContentJob.retry_count > 0,
                        )
                    )
                )
                or 0
            )
            latency_rows = (
                await session.execute(
                    select(AgentContentJob.metadata_json).where(
                        AgentContentJob.agent_id == agent.id,
                        AgentContentJob.status.in_(["rendered", "publishing", "published", "failed"]),
                        AgentContentJob.metadata_json.is_not(None),
                    )
                )
            ).scalars().all()

            latencies_seconds: list[float] = []
            for raw_meta in latency_rows:
                meta = _parse_content_job_metadata(raw_meta)
                started_raw = str(meta.get("render_started_at") or "").strip()
                finished_raw = str(meta.get("render_finished_at") or "").strip()
                if not started_raw or not finished_raw:
                    continue
                try:
                    started_dt = datetime.fromisoformat(started_raw)
                    finished_dt = datetime.fromisoformat(finished_raw)
                except Exception:
                    continue
                delta = (finished_dt - started_dt).total_seconds()
                if delta >= 0:
                    latencies_seconds.append(delta)

            avg_render_latency_seconds = (
                round(sum(latencies_seconds) / len(latencies_seconds), 2) if latencies_seconds else 0.0
            )
            retry_rate = (float(retry_jobs) / float(total)) * 100.0 if total > 0 else 0.0
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "jobs_total": total,
                    "jobs_published": published,
                    "jobs_failed": failed,
                    "avg_render_latency_seconds": avg_render_latency_seconds,
                    "retry_rate_percent": round(retry_rate, 2),
                },
                status_code=status.HTTP_200_OK,
            )



@router.get("/content/jobs/{job_id}")
async def content_job_detail(
    job_id: int,
    payload: AgentLookup = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            row = await session.scalar(
                select(AgentContentJob).where(
                    AgentContentJob.id == int(job_id),
                    AgentContentJob.agent_id == agent.id,
                )
            )
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content job not found")
            return JSONResponse(content=_serialize_content_job(row), status_code=status.HTTP_200_OK)



@router.get("/analytics/frozen/check")
async def analytics_frozen_check(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    user_external_id: str = Query(..., max_length=128),
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            if agent_id is not None:
                agent = await agent_dao.find_one_by_filter(id=agent_id)
            else:
                agent, _ = await _find_agent_by_lookup_id(
                    session=session,
                    agent_dao=agent_dao,
                    lookup_id=bot_id,
                )
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            uid = user_external_id.strip()
            row_id = await session.scalar(
                select(AgentFrozenUser.id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id == uid,
                )
            )
            return JSONResponse(content={"frozen": bool(row_id)}, status_code=status.HTTP_200_OK)



@router.post("/analytics/frozen")
async def analytics_set_user_frozen(
    payload: AgentFreezeUserPayload,
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
            uid = payload.user_external_id.strip()
            if payload.frozen:
                exists = await session.scalar(
                    select(AgentFrozenUser.id).where(
                        AgentFrozenUser.agent_id == agent.id,
                        AgentFrozenUser.user_external_id == uid,
                    )
                )
                if not exists:
                    session.add(
                        AgentFrozenUser(
                            agent_id=agent.id,
                            user_external_id=uid,
                        )
                    )
            else:
                row = await session.scalar(
                    select(AgentFrozenUser).where(
                        AgentFrozenUser.agent_id == agent.id,
                        AgentFrozenUser.user_external_id == uid,
                    )
                )
                if row:
                    await session.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/external/send_to_user")
async def external_send_to_user_as_owner(
    payload: AgentExternalApiSendToUserPayload,
    current_user=Depends(get_current_user_required),
):
    user_external_id = payload.user_external_id.strip()
    if not user_external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_external_id is required",
        )
    text = payload.message.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сообщение пустое",
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
            webhook_url = _normalize_external_webhook_url(agent.external_webhook_url)
            if not webhook_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="external_webhook_url is not configured for this agent",
                )
            webhook_result = await _send_external_webhook_message(
                webhook_url=webhook_url,
                agent=agent,
                user_external_id=user_external_id,
                message_text=text,
            )
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="operator",
                message_text=text,
                channel="external_api",
                user_external_id=user_external_id,
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True, "webhook_result": webhook_result}, status_code=status.HTTP_200_OK)



@router.post(
    "/sales_manager/contacts/excel-upload",
    dependencies=[Depends(rate_limit(max_requests=15, window_seconds=60, scope="sales_manager_excel_upload"))],
)
async def sales_manager_contacts_excel_upload(
    background_tasks: BackgroundTasks,
    agent_id: int = Form(..., gt=0),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user_required),
):
    """Загрузка Excel-базы для sales_manager: парсинг, сохранение, фоновый outreach."""
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")

    from ..services.sales.agent_excel_import import import_agent_contacts_from_excel

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=None,
                session=session,
                current_user=current_user,
                internal=False,
            )
            if agent.template_type != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Загрузка Excel доступна только для шаблона sales_manager",
                )
            try:
                stats = await import_agent_contacts_from_excel(
                    session,
                    agent_id=int(agent.id),
                    file_bytes=raw,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

    batch_id = str(stats.get("import_batch_id") or "")
    if batch_id and (int(stats.get("imported") or 0) + int(stats.get("updated") or 0)) > 0:
        background_tasks.add_task(
            _run_sales_manager_excel_outreach,
            agent_id=int(agent.id),
            import_batch_id=batch_id,
        )

    msg_parts = [
        f"Добавлено контактов: {stats.get('imported', 0)}",
        f"обновлено: {stats.get('updated', 0)}",
    ]
    if stats.get("skipped_no_messenger"):
        msg_parts.append(f"без мессенджера/канала: {stats['skipped_no_messenger']}")
    if stats.get("skipped_duplicate"):
        msg_parts.append(f"пропущено (уже в работе): {stats['skipped_duplicate']}")
    msg_parts.append("Рассылка первых сообщений запущена в фоне.")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            **stats,
            "message": ". ".join(msg_parts),
            "outreach_scheduled": bool(batch_id),
        },
    )



@router.get("/sales_manager/contacts/import-status")
async def sales_manager_contacts_import_status(
    agent_id: int = Query(..., gt=0),
    import_batch_id: str | None = Query(None),
    current_user=Depends(get_current_user_required),
):
    """Статистика импортированных контактов и outreach для sales_manager."""
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                agent_id=agent_id,
                bot_id=None,
                session=session,
                current_user=current_user,
                internal=False,
            )
            if agent.template_type != "sales_manager":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Доступно только для sales_manager",
                )

            query = select(
                AgentSalesImportedContact.outreach_status,
                func.count(AgentSalesImportedContact.id),
            ).where(AgentSalesImportedContact.agent_id == agent.id)
            if import_batch_id:
                query = query.where(AgentSalesImportedContact.import_batch_id == import_batch_id.strip())
            query = query.group_by(AgentSalesImportedContact.outreach_status)
            rows = (await session.execute(query)).all()
            by_status = {str(status_key): int(cnt) for status_key, cnt in rows}

    return JSONResponse(
        content={
            "agent_id": agent_id,
            "import_batch_id": import_batch_id,
            "by_status": by_status,
            "total": sum(by_status.values()),
        }
    )



@router.get("/analytics/chats")
async def read_analytics_chats(
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    limit_users: int = Query(default=100, ge=1, le=500),
    messages_per_user: int = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
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
                internal=internal,
            )
            analytics_namespace_id = agent.bot_id if agent.bot_id is not None else agent.id

            supported_chat_channels = [
                "telegram",
                "telegram_userbot",
                "max_bot",
                "max_userbot",
                "whatsapp_userbot",
                "whatsapp_business_api",
                "phone",
                "external_api",
            ]

            user_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            AgentAnalyticsMessage.channel.label("channel"),
                            func.max(AgentAnalyticsMessage.user_display_name).label("display_name"),
                            func.count(AgentAnalyticsMessage.id).label("questions"),
                            func.max(AgentAnalyticsMessage.created_at).label("last_message_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                            AgentAnalyticsMessage.channel.in_(supported_chat_channels),
                        ).group_by(
                            AgentAnalyticsMessage.user_external_id,
                            AgentAnalyticsMessage.channel,
                        ).order_by(
                            func.max(AgentAnalyticsMessage.created_at).desc()
                        ).limit(limit_users)
                    )
                )
                .mappings()
                .all()
            )

            chat_keys = [
                (row["uid"], row["channel"])
                for row in user_rows
                if row["uid"] and row["channel"] in set(supported_chat_channels)
            ]
            if not chat_keys:
                return JSONResponse(
                    content={"agent_id": agent.id, "bot_id": agent.bot_id, "users": []},
                    status_code=status.HTTP_200_OK,
                )

            user_ids = list({uid for uid, _ in chat_keys})
            frozen_result = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(user_ids),
                )
            )
            frozen_ids = set(frozen_result.all())
            contact_status_by_uid: dict[str, str] = {}
            if user_ids:
                contact_rows = (
                    (
                        await session.execute(
                            select(
                                AgentSalesContact.user_external_id.label("uid"),
                                AgentSalesContact.state.label("state"),
                                AgentSalesContact.updated_at.label("updated_at"),
                            )
                            .where(
                                AgentSalesContact.agent_id == agent.id,
                                AgentSalesContact.user_external_id.in_(user_ids),
                            )
                            .order_by(AgentSalesContact.updated_at.desc(), AgentSalesContact.id.desc())
                        )
                    )
                    .mappings()
                    .all()
                )
                for item in contact_rows:
                    uid = str(item.get("uid") or "").strip()
                    state = str(item.get("state") or "").strip().upper()
                    if not uid or not state:
                        continue
                    if uid in contact_status_by_uid:
                        continue
                    contact_status_by_uid[uid] = state

            message_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id,
                            AgentAnalyticsMessage.user_display_name,
                            AgentAnalyticsMessage.role,
                            AgentAnalyticsMessage.channel,
                            AgentAnalyticsMessage.message_text,
                            AgentAnalyticsMessage.created_at,
                        ).where(
                            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                            AgentAnalyticsMessage.user_external_id.in_(user_ids),
                            AgentAnalyticsMessage.channel.in_(
                                [*supported_chat_channels, "dashboard"]
                            ),
                        ).order_by(AgentAnalyticsMessage.created_at.asc())
                    )
                )
                .mappings()
                .all()
            )

            grouped_messages = defaultdict(list)
            for row in message_rows:
                row_channel = row["channel"]
                if row_channel == "dashboard":
                    # Ответы из кабинета показываем в потоке того канала, куда писал пользователь.
                    grouped_messages[(row["user_external_id"], "telegram")].append(row)
                    grouped_messages[(row["user_external_id"], "telegram_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "max_bot")].append(row)
                    grouped_messages[(row["user_external_id"], "max_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "whatsapp_userbot")].append(row)
                    grouped_messages[(row["user_external_id"], "external_api")].append(row)
                else:
                    grouped_messages[(row["user_external_id"], row_channel)].append(row)

            users_payload = []
            for row in user_rows:
                uid = row["uid"]
                chat_channel = row["channel"]
                chat_key = f"{chat_channel}:{uid}"
                items = grouped_messages.get((uid, chat_channel), [])
                if messages_per_user > 0 and len(items) > messages_per_user:
                    items = items[-messages_per_user:]

                users_payload.append(
                    {
                        "chat_key": chat_key,
                        "chat_channel": chat_channel,
                        "user_external_id": uid,
                        "user_display_name": row["display_name"] or f"User {uid}",
                        "questions_count": int(row["questions"] or 0),
                        "last_message_at": _safe_iso(row["last_message_at"]),
                        "is_frozen": uid in frozen_ids,
                        "lead_status": contact_status_by_uid.get(str(uid), None),
                        "messages": [
                            {
                                "role": item["role"],
                                "channel": item["channel"],
                                "text": item["message_text"],
                                "created_at": _safe_iso(item["created_at"]),
                            }
                            for item in items
                        ],
                    }
                )

            return JSONResponse(
                content={"agent_id": agent.id, "bot_id": agent.bot_id, "users": users_payload},
                status_code=status.HTTP_200_OK,
            )



@router.post("/external/chat")
async def external_chat(
    payload: ExternalAgentChatRequest,
    agent=Depends(get_agent_by_external_api_key),
    _rate_limited=Depends(rate_limit(max_requests=60, window_seconds=60, scope="agents_external_chat")),
):
    if not agent.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is disabled")
    template_type = str(agent.template_type or "qa").strip().lower()
    if template_type not in WIDGET_ALLOWED_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External chat is available only for qa and crm_admin templates",
        )

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message is empty")

    external_user_id = (payload.external_user_id or "").strip() or (payload.chat_id or "").strip() or None
    external_user_name = (payload.external_user_name or "").strip() or None
    if not external_user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_user_id (or chat_id) is required for dashboard chat tracking",
        )

    async with async_session_maker() as session:
        if await is_user_frozen(session, agent.id, external_user_id):
            return JSONResponse(
                content={
                    "bot_id": agent.bot_id,
                    "bot_username": agent.bot_username,
                    "external_user_id": external_user_id,
                    "reply": False,
                    "sources": [],
                },
                status_code=status.HTTP_200_OK,
            )

    knowledge_scope_id = agent.bot_id if agent.bot_id is not None else agent.id
    template_config = _decode_template_config(
        agent.template_config,
        template_type=agent.template_type,
    )
    portrait_enabled = bool((template_config or {}).get("enable_chat_portrait", True))
    if template_type == "content_factory":
        portrait_enabled = False

    # Keep parity with channel flows: persist user message before portrait refresh
    # so portrait can use the latest user turn.
    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="user",
                channel="external_api",
                user_external_id=external_user_id,
                user_display_name=external_user_name,
                message_text=message,
            )
    chat_portrait = ""
    if portrait_enabled:
        chat_portrait = await get_template_runtime().update_chat_portrait(
            agent_id=agent.id,
            analytics_namespace_id=knowledge_scope_id,
            user_external_id=external_user_id,
            source_channel="external_api",
            user_message=message,
            base_prompt=agent.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            template_config=template_config,
        )

    try:
        execution = await get_template_runtime().execute(
            template_type=agent.template_type,
            prompt=agent.system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT,
            user_message=message,
            knowledge_scope_id=knowledge_scope_id,
            agent_id=agent.id,
            user_external_id=external_user_id,
            template_config=template_config,
            source_channel="external_api",
            chat_portrait=chat_portrait,
        )
        answer = execution.answer
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить ответ от LLM",
        )
    sources = execution.sources
    handoff_applied = False
    escalation_type_applied: str | None = None
    if execution.requires_owner_handoff and str(agent.template_type or "qa").strip().lower() == "qa":
        qa_escalation_type = (
            QAEscalationType.FREEZE_CHAT
            if execution.escalation_type == EscalationType.FREEZE_CHAT
            else QAEscalationType.NOTIFY_ONLY
        )
        await get_qa_handoff_service().escalate_to_operator(
            agent_id=agent.id,
            user_external_id=external_user_id,
            user_message=message,
            answer=answer,
            reason=execution.owner_handoff_reason,
            channel="external_api",
            user_display_name=external_user_name,
            escalation_type=qa_escalation_type,
        )
        handoff_applied = True
        escalation_type_applied = qa_escalation_type.value

    async with async_session_maker() as session:
        async with session.begin():
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="agent",
                channel="external_api",
                user_external_id=external_user_id,
                user_display_name=external_user_name,
                message_text=answer,
            )
            for event in execution.tool_events:
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=_summarize_tool_event_for_log(event),
                    tool_name=event.get("tool_name"),
                    tool_args_hash=event.get("tool_args_hash"),
                    tool_status=event.get("tool_status"),
                    latency_ms=int(event.get("latency_ms") or 0),
                    crm_provider=event.get("crm_provider"),
                )
            if execution.fallback_to_text:
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=execution.fallback_reason or "fallback_to_text",
                    tool_name="fallback_to_text",
                    tool_status="fallback",
                    crm_provider=(
                        _decode_template_config(
                            agent.template_config,
                            template_type=agent.template_type,
                        )
                        or {}
                    ).get("crm_provider"),
                )
            if handoff_applied:
                tool_status = (
                    "chat_frozen" if escalation_type_applied == "freeze_chat" else "operator_notified"
                )
                await _log_analytics_message(
                    session=session,
                    agent=agent,
                    role="operator",
                    channel="external_api",
                    user_external_id=external_user_id,
                    user_display_name=external_user_name,
                    message_text=execution.owner_handoff_reason or "qa_owner_handoff",
                    tool_name="qa_owner_handoff",
                    tool_status=tool_status,
                )

    answer_text = (answer or "").strip()
    return JSONResponse(
        content={
            "bot_id": agent.bot_id,
            "bot_username": agent.bot_username,
            "external_user_id": external_user_id,
            "answer": answer_text,
            "reply": bool(answer_text),
            "sources": sources,
        },
        status_code=status.HTTP_200_OK,
    )



@router.get("/external/widget.css")
async def external_widget_css():
    return PlainTextResponse(
        content=WIDGET_CSS,
        media_type="text/css; charset=utf-8",
    )



@router.get("/external/widget.js")
async def external_widget_js():
    return PlainTextResponse(
        content=WIDGET_JS,
        media_type="application/javascript; charset=utf-8",
    )
