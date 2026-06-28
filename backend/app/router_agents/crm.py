"""Agent routes: crm."""
from fastapi import APIRouter

from .shared import *  # noqa: F403

router = APIRouter()

@router.post("/crm/connect")
async def connect_crm(
    request: Request,
    payload: AgentCrmConnectPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_name = (payload.provider or "").strip().lower()
    base_url = _normalize_crm_base_url(payload.account_base_url)
    access_token = payload.access_token.strip()

    provider = build_provider(provider_name, base_url=base_url, access_token=access_token)
    try:
        health = await provider.validate_connection()
    except Exception:
        logger.exception("CRM credentials validation failed during connect (provider=%s)", provider_name)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CRM credentials validation failed",
        )

    now = datetime.utcnow()
    external_id = (health.external_id or "").strip() or base_url
    encrypted_credentials = encrypt_crm_credentials(
        json.dumps(
            {
                "base_url": base_url,
                "access_token": access_token,
                "account_external_id": external_id,
            },
            ensure_ascii=False,
        )
    )

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        crm_connection_dao = AgentCrmConnectionDAO(session)
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

            existing_for_agent = await crm_connection_dao.find_one_by_filter(
                agent_id=agent.id,
                provider=provider_name,
            )
            existing_global = await crm_connection_dao.find_one_by_filter(
                provider=provider_name,
                external_id=external_id,
            )
            if existing_global and existing_global.agent_id != agent.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот CRM аккаунт уже подключен к другому агенту",
                )

            if existing_for_agent:
                await crm_connection_dao.update(
                    existing_for_agent,
                    {
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_credentials,
                        "is_active": True,
                        "last_checked_at": now,
                        "updated_at": now,
                    },
                )
                connection = existing_for_agent
            else:
                connection = await crm_connection_dao.add(
                    {
                        "agent_id": agent.id,
                        "provider": provider_name,
                        "external_id": external_id,
                        "encrypted_credentials": encrypted_credentials,
                        "is_active": True,
                        "last_checked_at": now,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                await session.flush()

            if _normalize_template_type(agent.template_type) == "crm_admin":
                current_config = _decode_template_config(
                    agent.template_config,
                    template_type=agent.template_type,
                ) or {}
                current_config["crm_provider"] = provider_name
                await agent_dao.update(
                    agent,
                    {
                        "template_config": _normalize_template_config("crm_admin", current_config),
                    },
                )

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "crm_connection": _serialize_crm_connection(connection),
                    "health": {
                        "ok": health.ok,
                        "provider": health.provider,
                        "external_id": health.external_id,
                        "details": health.details,
                    },
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/crm/validate")
async def validate_crm_connection(
    request: Request,
    payload: AgentCrmValidatePayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_name = (payload.provider or "").strip().lower()
    base_url = _normalize_crm_base_url(payload.account_base_url)
    access_token = payload.access_token.strip()

    try:
        provider = build_provider(provider_name, base_url=base_url, access_token=access_token)
        health = await provider.validate_connection()
    except Exception:
        logger.exception("CRM credentials validation failed (provider=%s)", provider_name)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CRM credentials validation failed",
        )

    return JSONResponse(
        content={
            "ok": bool(health.ok),
            "provider": health.provider,
            "external_id": health.external_id,
            "details": health.details,
        },
        status_code=status.HTTP_200_OK,
    )



@router.get("/crm/health")
async def crm_health(
    request: Request,
    agent_id: int | None = Query(default=None),
    bot_id: int | None = Query(default=None),
    provider: str | None = Query(default=None),
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    if agent_id is None and bot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query parameter 'agent_id' or 'bot_id' is required",
        )

    provider_filter = (provider or "").strip().lower() or None
    if provider_filter and provider_filter not in CRM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supported providers: amocrm, bitrix24",
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
            rows = (
                (
                    await session.execute(
                        select(AgentCrmConnection).where(
                            AgentCrmConnection.agent_id == agent.id,
                            AgentCrmConnection.is_active.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if provider_filter:
                rows = [row for row in rows if (row.provider or "").strip().lower() == provider_filter]
            if not rows:
                return JSONResponse(
                    content={
                        "agent_id": agent.id,
                        "bot_id": agent.bot_id,
                        "connections": [],
                    },
                    status_code=status.HTTP_200_OK,
                )

            now = datetime.utcnow()
            results = []
            for row in rows:
                try:
                    decrypted_payload, needs_rotation = decrypt_crm_credentials(row.encrypted_credentials)
                    bundle = json.loads(decrypted_payload)
                    if needs_rotation:
                        row.encrypted_credentials = encrypt_crm_credentials(
                            json.dumps(bundle, ensure_ascii=False)
                        )
                    provider_impl = build_provider(
                        row.provider,
                        base_url=str(bundle.get("base_url") or ""),
                        access_token=str(bundle.get("access_token") or ""),
                    )
                    health = await provider_impl.validate_connection()
                    row.last_checked_at = now
                    row.updated_at = now
                    results.append(
                        {
                            "connection": _serialize_crm_connection(row),
                            "health": {
                                "ok": health.ok,
                                "provider": health.provider,
                                "external_id": health.external_id,
                                "details": health.details,
                            },
                        }
                    )
                except Exception as exc:
                    logger.exception("CRM health check failed for connection_id=%s", row.id)
                    results.append(
                        {
                            "connection": _serialize_crm_connection(row),
                            "health": {
                                "ok": False,
                                "provider": row.provider,
                                "external_id": row.external_id,
                                "details": {"error": redact_pii_text(str(exc))},
                            },
                        }
                    )
            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "connections": results,
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/crm/rotate_secret")
async def rotate_crm_secret(
    request: Request,
    payload: AgentCrmRotateSecretPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    provider_filter = (payload.provider or "").strip().lower() or None

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        crm_connection_dao = AgentCrmConnectionDAO(session)
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
            rows = (
                (
                    await session.execute(
                        select(AgentCrmConnection).where(
                            AgentCrmConnection.agent_id == agent.id,
                            AgentCrmConnection.is_active.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if provider_filter:
                rows = [row for row in rows if (row.provider or "").strip().lower() == provider_filter]

            now = datetime.utcnow()
            rotated_count = 0
            for row in rows:
                try:
                    decrypted_payload, _ = decrypt_crm_credentials(row.encrypted_credentials)
                    row.encrypted_credentials = encrypt_crm_credentials(decrypted_payload)
                    row.updated_at = now
                    await crm_connection_dao.update(
                        row,
                        {
                            "encrypted_credentials": row.encrypted_credentials,
                            "updated_at": row.updated_at,
                        },
                    )
                    rotated_count += 1
                except Exception:
                    logger.exception("CRM secret rotation failed for connection_id=%s", row.id)

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "provider": provider_filter,
                    "rotated": rotated_count,
                    "total_candidates": len(rows),
                },
                status_code=status.HTTP_200_OK,
            )


