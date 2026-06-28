"""Agent routes: integrations."""
from fastapi import APIRouter

from .shared import *  # noqa: F403

router = APIRouter()

@router.post("/http_integration/connect")
async def http_integration_connect(
    request: Request,
    payload: HttpIntegrationConnectPayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    slug = _normalize_http_integration_slug(payload.integration_name)
    tools_manifest = []
    for item in payload.tools:
        tools_manifest.append(
            {
                "name": item.name.strip(),
                "description": item.description.strip(),
                "method": item.method,
                "path": item.path.strip(),
                "requires_confirmation": item.requires_confirmation,
                "parameters": item.parameters,
            }
        )

    bundle: dict[str, object] = {
        "base_url": payload.base_url.strip().rstrip("/"),
        "timeout_seconds": float(payload.timeout_seconds),
        "default_headers": {str(k): str(v) for k, v in (payload.default_headers or {}).items() if str(k)},
        "auth": _bundle_auth_payload_to_dict(payload.auth),
        "tools": tools_manifest,
    }
    try:
        validated = validate_integration_config_dict(bundle)
    except HttpIntegrationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    encrypted_config = encrypt_crm_credentials(json.dumps(validated, ensure_ascii=False))

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        hid = AgentHttpIntegrationDAO(session)
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
            if _normalize_template_type(agent.template_type) != "crm_admin":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Интеграции доступны только для шаблона ИИ‑администратора (crm_admin)",
                )

            existing = await hid.find_one_by_filter(agent_id=agent.id, name=slug)
            now = datetime.utcnow()
            if existing:
                await hid.update(
                    existing,
                    {
                        "encrypted_config": encrypted_config,
                        "is_active": True,
                        "updated_at": now,
                    },
                )
                row = existing
            else:
                row = await hid.add(
                    {
                        "agent_id": agent.id,
                        "name": slug,
                        "encrypted_config": encrypted_config,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                await session.flush()

            return JSONResponse(
                content={
                    "agent_id": agent.id,
                    "bot_id": agent.bot_id,
                    "http_integration": _serialize_http_integration(row),
                },
                status_code=status.HTTP_200_OK,
            )



@router.post("/http_integration/deactivate")
async def http_integration_deactivate(
    request: Request,
    payload: HttpIntegrationDeactivatePayload,
    current_user=Depends(get_current_user_required),
):
    _assert_https_for_sensitive_endpoint(request)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        hid = AgentHttpIntegrationDAO(session)
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
            row = await hid.find_one_by_filter(agent_id=agent.id, id=payload.integration_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
            now = datetime.utcnow()
            await hid.update(
                row,
                {
                    "is_active": False,
                    "updated_at": now,
                },
            )
            return JSONResponse(
                content={"http_integration": _serialize_http_integration(row)},
                status_code=status.HTTP_200_OK,
            )


