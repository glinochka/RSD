import asyncio
import json
import math
from logging import getLogger
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta
from collections import defaultdict

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import Date, cast, func, select

from .dao import AgentChannelConnectionDAO, AgentCrmConnectionDAO, AgentDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentAnalyticsMessage, AgentChannelConnection, AgentCrmConnection, AgentFrozenUser
from ..config import settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_users.dao import UserDAO
from ..channels.message_processor import (
    Channel as RuntimeChannel,
    MessageRequest as RuntimeMessageRequest,
    get_message_processor,
)
from ..services.ai_authoring import generate_welcome_with_ai, improve_prompt_with_ai
from ..services.crm import build_provider
from ..services.template_runtime import get_template_runtime
from ..utils.api_keys import generate_agent_external_api_key, hash_agent_external_api_key
from ..utils.JWT import get_user_from_access_token
from ..utils.convert import convert_to_dict
from ..utils.crypto import decrypt_crm_credentials, decrypt_token, encrypt_crm_credentials, encrypt_token
from ..utils.internal_auth import is_internal_request, is_request_secure, verify_internal_signature
from ..utils.pii import redact_pii_text
from ..utils.rate_limit import rate_limit
from ..utils.whatsapp_session import decode_whatsapp_session_bundle

logger = getLogger(__name__)
router = APIRouter(prefix="/api/agents")
http_bearer = HTTPBearer(auto_error=False)
MAX_INT32 = 2_147_483_647
USERBOT_AUTH_TOKEN_TTL_MINUTES = 10
LEGACY_TEMPLATE_TYPE_ALIASES = {
    "function_calling": "crm_admin",
}
SUPPORTED_TEMPLATE_TYPES = {"qa", "crm_admin", "lead_generation", "content_factory", "sales_manager"}
CRM_PROVIDERS = {"amocrm", "bitrix24"}
CRM_CONFIRMATION_POLICIES = {"always_confirm", "confirm_risky", "never_confirm"}
CRM_FALLBACK_MODES = {"ask_clarifying_question", "text_only"}
DEFAULT_CRM_ALLOWED_TOOLS = [
    "find_contact",
    "create_contact",
    "find_lead",
    "create_lead",
    "update_lead",
    "add_note",
    "create_task",
    "assign_owner",
]
SALES_MODES = {"draft_only", "semi_auto", "auto"}
SALES_ALLOWED_LANGUAGES = {"ru", "en"}
SALES_CONFIRMATION_POLICIES = {"always_confirm", "confirm_risky", "never_confirm"}
SALES_DEFAULT_ALLOWED_TOOLS = [
    "schedule_dm",
    "skip_lead",
    "record_lead_signal",
    "create_crm_lead",
    "mark_contacted",
]
SALES_DEFAULT_CONFIG = {
    "mode": "draft_only",
    "qualification_model": "deepseek-chat",
    "generation_model": "deepseek-chat",
    "min_confidence": 0.75,
    "scan_scope": {
        "include_chat_ids": [],
        "exclude_chat_ids": [],
    },
    "dm_limits": {
        "per_minute": 3,
        "per_hour": 25,
        "per_day": 120,
        "per_source_chat_per_day": 40,
    },
    "cooldown_days": 14,
    "dedup_window_days": 30,
    "allowed_languages": ["ru", "en"],
    "quiet_hours_local": "22:00-09:00",
    "offer_profile_id": None,
    "confirmation_policy": "confirm_risky",
    "allowed_tools": list(SALES_DEFAULT_ALLOWED_TOOLS),
}


def _assert_https_for_sensitive_endpoint(request: Request) -> None:
    if not is_request_secure(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTPS is required for this endpoint",
        )


def _summarize_tool_event_for_log(event: dict) -> str:
    tool_name = str(event.get("tool_name") or "unknown")
    tool_status = str(event.get("tool_status") or "unknown")
    latency_ms = int(event.get("latency_ms") or 0)
    provider = str(event.get("crm_provider") or "unknown")
    replay = bool(event.get("idempotent_replay"))
    error = redact_pii_text(str(event.get("error") or "")).strip()
    parts = [
        f"tool={tool_name}",
        f"status={tool_status}",
        f"latency_ms={latency_ms}",
        f"crm_provider={provider}",
        f"idempotent_replay={str(replay).lower()}",
    ]
    if error:
        parts.append(f"error={error}")
    return " ".join(parts)


def _normalize_template_type(template_type: str | None) -> str:
    raw = (template_type or "qa").strip().lower()
    normalized = LEGACY_TEMPLATE_TYPE_ALIASES.get(raw, raw)
    if normalized not in SUPPORTED_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported template_type: {template_type}",
        )
    return normalized


def _normalize_template_config(template_type: str, template_config: dict | None) -> str | None:
    raw = template_config or {}
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config must be a JSON object",
        )
    if template_type == "sales_manager":
        mode = str(raw.get("mode") or SALES_DEFAULT_CONFIG["mode"]).strip().lower()
        if mode not in SALES_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.mode must be one of: draft_only, semi_auto, auto",
            )

        qualification_model = str(
            raw.get("qualification_model") or SALES_DEFAULT_CONFIG["qualification_model"]
        ).strip()
        generation_model = str(
            raw.get("generation_model") or SALES_DEFAULT_CONFIG["generation_model"]
        ).strip()
        if not qualification_model or not generation_model:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config qualification_model/generation_model must be non-empty",
            )

        min_confidence_raw = raw.get("min_confidence", SALES_DEFAULT_CONFIG["min_confidence"])
        try:
            min_confidence = float(min_confidence_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.min_confidence must be a number",
            ) from None
        if min_confidence < 0.0 or min_confidence > 1.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.min_confidence must be between 0 and 1",
            )

        scan_scope_raw = raw.get("scan_scope")
        if scan_scope_raw is None:
            scan_scope_raw = SALES_DEFAULT_CONFIG["scan_scope"]
        if not isinstance(scan_scope_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.scan_scope must be an object",
            )

        def _normalize_chat_ids(value: list | None) -> list[int]:
            if value is None:
                return []
            if not isinstance(value, list):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="scan_scope chat ids must be arrays",
                )
            normalized_ids: list[int] = []
            for item in value:
                try:
                    chat_id = int(str(item).strip())
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="scan_scope chat ids must contain integers",
                    ) from None
                if chat_id not in normalized_ids:
                    normalized_ids.append(chat_id)
            return normalized_ids

        include_chat_ids = _normalize_chat_ids(scan_scope_raw.get("include_chat_ids"))
        exclude_chat_ids = _normalize_chat_ids(scan_scope_raw.get("exclude_chat_ids"))
        scan_scope = {
            "include_chat_ids": include_chat_ids,
            "exclude_chat_ids": exclude_chat_ids,
        }

        dm_limits_raw = raw.get("dm_limits")
        if dm_limits_raw is None:
            dm_limits_raw = SALES_DEFAULT_CONFIG["dm_limits"]
        if not isinstance(dm_limits_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.dm_limits must be an object",
            )

        def _normalize_positive_int(name: str, default_value: int, max_value: int) -> int:
            value = dm_limits_raw.get(name, default_value)
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"template_config.dm_limits.{name} must be an integer",
                ) from None
            if normalized < 1 or normalized > max_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"template_config.dm_limits.{name} must be between 1 and {max_value}",
                )
            return normalized

        dm_limits = {
            "per_minute": _normalize_positive_int("per_minute", 3, 60),
            "per_hour": _normalize_positive_int("per_hour", 25, 600),
            "per_day": _normalize_positive_int("per_day", 120, 5000),
            "per_source_chat_per_day": _normalize_positive_int("per_source_chat_per_day", 40, 2000),
        }

        cooldown_days_raw = raw.get("cooldown_days", SALES_DEFAULT_CONFIG["cooldown_days"])
        dedup_window_days_raw = raw.get("dedup_window_days", SALES_DEFAULT_CONFIG["dedup_window_days"])
        try:
            cooldown_days = int(cooldown_days_raw)
            dedup_window_days = int(dedup_window_days_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.cooldown_days/dedup_window_days must be integers",
            ) from None
        if cooldown_days < 1 or cooldown_days > 365:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.cooldown_days must be between 1 and 365",
            )
        if dedup_window_days < 1 or dedup_window_days > 365:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.dedup_window_days must be between 1 and 365",
            )

        allowed_languages_raw = raw.get("allowed_languages")
        if allowed_languages_raw is None:
            allowed_languages = list(SALES_DEFAULT_CONFIG["allowed_languages"])
        elif isinstance(allowed_languages_raw, list):
            allowed_languages = []
            for item in allowed_languages_raw:
                lang = str(item or "").strip().lower()
                if lang in SALES_ALLOWED_LANGUAGES and lang not in allowed_languages:
                    allowed_languages.append(lang)
            if not allowed_languages:
                allowed_languages = list(SALES_DEFAULT_CONFIG["allowed_languages"])
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.allowed_languages must be an array of strings",
            )

        quiet_hours_local = str(raw.get("quiet_hours_local") or SALES_DEFAULT_CONFIG["quiet_hours_local"]).strip()
        if quiet_hours_local != "22:00-09:00":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.quiet_hours_local currently supports only: 22:00-09:00",
            )

        offer_profile_raw = raw.get("offer_profile_id")
        offer_profile_id = None
        if offer_profile_raw is not None:
            offer_profile_value = str(offer_profile_raw).strip()
            offer_profile_id = offer_profile_value or None

        confirmation_policy = str(
            raw.get("confirmation_policy") or SALES_DEFAULT_CONFIG["confirmation_policy"]
        ).strip().lower()
        if confirmation_policy not in SALES_CONFIRMATION_POLICIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.confirmation_policy must be one of: always_confirm, confirm_risky, never_confirm",
            )

        allowed_tools_raw = raw.get("allowed_tools")
        if allowed_tools_raw is None:
            allowed_tools = list(SALES_DEFAULT_ALLOWED_TOOLS)
        elif isinstance(allowed_tools_raw, list):
            allowed_tools = []
            for item in allowed_tools_raw:
                tool = str(item or "").strip()
                if tool and tool in SALES_DEFAULT_ALLOWED_TOOLS and tool not in allowed_tools:
                    allowed_tools.append(tool)
            if not allowed_tools:
                allowed_tools = list(SALES_DEFAULT_ALLOWED_TOOLS)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.allowed_tools must be an array of strings",
            )

        normalized_config = {
            "mode": mode,
            "qualification_model": qualification_model,
            "generation_model": generation_model,
            "min_confidence": min_confidence,
            "scan_scope": scan_scope,
            "dm_limits": dm_limits,
            "cooldown_days": cooldown_days,
            "dedup_window_days": dedup_window_days,
            "allowed_languages": allowed_languages,
            "quiet_hours_local": quiet_hours_local,
            "offer_profile_id": offer_profile_id,
            "confirmation_policy": confirmation_policy,
            "allowed_tools": allowed_tools,
        }
        return json.dumps(normalized_config, ensure_ascii=False)

    if template_type != "crm_admin":
        return None

    crm_provider = str(raw.get("crm_provider") or "amocrm").strip().lower()
    if crm_provider not in CRM_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.crm_provider must be one of: amocrm, bitrix24",
        )

    confirmation_policy = str(raw.get("confirmation_policy") or "confirm_risky").strip().lower()
    if confirmation_policy not in CRM_CONFIRMATION_POLICIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.confirmation_policy is invalid",
        )

    fallback_mode = str(raw.get("fallback_mode") or "ask_clarifying_question").strip().lower()
    if fallback_mode not in CRM_FALLBACK_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.fallback_mode is invalid",
        )

    allowed_tools_raw = raw.get("allowed_tools")
    if allowed_tools_raw is None:
        allowed_tools = list(DEFAULT_CRM_ALLOWED_TOOLS)
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = []
        for item in allowed_tools_raw:
            tool = str(item or "").strip()
            if tool and tool not in allowed_tools:
                allowed_tools.append(tool)
        if not allowed_tools:
            allowed_tools = list(DEFAULT_CRM_ALLOWED_TOOLS)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_config.allowed_tools must be an array of strings",
        )

    field_mapping_raw = raw.get("field_mapping")
    field_mapping = None
    if field_mapping_raw is not None:
        if not isinstance(field_mapping_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template_config.field_mapping must be an object",
            )
        normalized_mapping = {}
        for key, value in field_mapping_raw.items():
            k = str(key or "").strip()
            v = str(value or "").strip()
            if k and v:
                normalized_mapping[k] = v
        field_mapping = normalized_mapping or None

    normalized_config = {
        "crm_provider": crm_provider,
        "allowed_tools": allowed_tools,
        "confirmation_policy": confirmation_policy,
        "fallback_mode": fallback_mode,
        "field_mapping": field_mapping,
    }
    return json.dumps(normalized_config, ensure_ascii=False)


async def get_current_user_optional(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        return None

    token = http_credentials.credentials
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await get_user_from_access_token(token, user_dao)
            return await user_dao.find_one_by_filter(load_relations=True, id=user.id)


async def get_current_user_required(
    current_user=Depends(get_current_user_optional),
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


def _assert_access(current_user, internal: bool) -> None:
    if current_user is None and not internal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


async def _ensure_external_api_key(agent, agent_dao: AgentDAO) -> str:
    if agent.encrypted_external_api_key and agent.external_api_key_hash:
        return decrypt_token(agent.encrypted_external_api_key)

    raw_key = generate_agent_external_api_key()
    await agent_dao.update(
        agent,
        {
            "encrypted_external_api_key": encrypt_token(raw_key),
            "external_api_key_hash": hash_agent_external_api_key(raw_key),
        },
    )
    return raw_key


async def _regenerate_external_api_key(agent, agent_dao: AgentDAO) -> str:
    raw_key = generate_agent_external_api_key()
    await agent_dao.update(
        agent,
        {
            "encrypted_external_api_key": encrypt_token(raw_key),
            "external_api_key_hash": hash_agent_external_api_key(raw_key),
        },
    )
    return raw_key


def _serialize_agent(agent, *, include_external_api_key: bool = False, include_encrypted_token: bool = False) -> dict:
    data = convert_to_dict(agent)
    data.pop("registered", None)
    data.pop("encrypted_external_api_key", None)
    data.pop("external_api_key_hash", None)
    try:
        data["template_type"] = _normalize_template_type(data.get("template_type"))
    except HTTPException:
        data["template_type"] = "qa"
    raw_template_config = data.get("template_config")
    if isinstance(raw_template_config, str) and raw_template_config.strip():
        try:
            data["template_config"] = json.loads(raw_template_config)
        except Exception:
            data["template_config"] = None
    else:
        data["template_config"] = None
    if not include_encrypted_token:
        data.pop("encrypted_token", None)
    if include_external_api_key:
        if agent.encrypted_external_api_key:
            data["external_api_key"] = decrypt_token(agent.encrypted_external_api_key)
        else:
            data["external_api_key"] = None
    return data


def _serialize_channel_connection(connection: AgentChannelConnection) -> dict:
    return {
        "id": connection.id,
        "provider": connection.provider,
        "connection_type": connection.connection_type,
        "external_id": connection.external_id,
        "is_primary": bool(connection.is_primary),
        "is_active": bool(connection.is_active),
        "created_at": _safe_iso(connection.created_at),
        "updated_at": _safe_iso(connection.updated_at),
    }


def _serialize_crm_connection(connection: AgentCrmConnection) -> dict:
    return {
        "id": connection.id,
        "provider": connection.provider,
        "external_id": connection.external_id,
        "is_active": bool(connection.is_active),
        "last_checked_at": _safe_iso(connection.last_checked_at),
        "created_at": _safe_iso(connection.created_at),
        "updated_at": _safe_iso(connection.updated_at),
    }


def _normalize_crm_base_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="account_base_url is required",
        )
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raw = f"https://{raw}"
    return raw


def _decode_template_config(raw_template_config: str | None) -> dict | None:
    if not raw_template_config or not str(raw_template_config).strip():
        return None
    try:
        loaded = json.loads(raw_template_config)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return None
    return None


def _normalize_external_webhook_url(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) > 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_webhook_url must be at most 1024 chars",
        )
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_webhook_url must start with http:// or https://",
        )
    return raw


async def _send_external_webhook_message(
    *,
    webhook_url: str,
    agent,
    user_external_id: str,
    message_text: str,
) -> dict:
    body = json.dumps(
        {
            "event": "owner_message",
            "channel": "external_api",
            "agent_id": agent.id,
            "bot_id": agent.bot_id,
            "user_external_id": user_external_id,
            "message": message_text,
            "sent_at": datetime.utcnow().isoformat() + "Z",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = UrlRequest(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    def _call():
        with urlopen(request, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {"ok": True}
            try:
                decoded = json.loads(raw)
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                pass
            return {"ok": True, "raw": raw}

    try:
        return await asyncio.get_running_loop().run_in_executor(None, _call)
    except HTTPError as exc:
        detail_text = ""
        try:
            detail_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail_text = ""
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External webhook returned HTTP {exc.code}: {detail_text[:500]}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External webhook is unreachable: {exc.reason}",
        ) from exc


async def _list_agent_channels(session, agent_id: int) -> list[AgentChannelConnection]:
    rows = await session.scalars(
        select(AgentChannelConnection)
        .where(AgentChannelConnection.agent_id == agent_id)
        .order_by(AgentChannelConnection.created_at.asc(), AgentChannelConnection.id.asc())
    )
    return list(rows.all())


async def _list_agent_crm_connections(session, agent_id: int) -> list[AgentCrmConnection]:
    rows = await session.scalars(
        select(AgentCrmConnection)
        .where(AgentCrmConnection.agent_id == agent_id)
        .order_by(AgentCrmConnection.created_at.asc(), AgentCrmConnection.id.asc())
    )
    return list(rows.all())


async def _sync_agent_primary_fields(
    *,
    agent,
    agent_dao: AgentDAO,
    session,
):
    channels = await _list_agent_channels(session, agent.id)
    if not channels:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="У агента должен быть минимум один канал подключения",
        )
    primary = next((item for item in channels if item.is_primary), None) or channels[0]
    now = datetime.utcnow()
    for item in channels:
        should_be_primary = item.id == primary.id
        if bool(item.is_primary) != should_be_primary:
            item.is_primary = should_be_primary
            item.updated_at = now

    updates = {"primary_provider": primary.provider}
    primary_external_id = (primary.external_id or "").strip()
    if primary_external_id.isdigit():
        updates["bot_id"] = int(primary_external_id)
    elif primary.provider == "telegram_bot":
        updates["bot_id"] = None
    # Keep legacy field in sync for Telegram bot flow used by webhook and bot service.
    if primary.provider == "telegram_bot" and primary.encrypted_credentials:
        updates["encrypted_token"] = primary.encrypted_credentials
    await agent_dao.update(agent, updates)
    return primary


async def _ensure_single_primary_flag(
    *,
    session,
    agent_id: int,
):
    channels = await _list_agent_channels(session, agent_id)
    if not channels:
        return
    now = datetime.utcnow()
    primary = next((item for item in channels if item.is_primary), None) or channels[0]
    for item in channels:
        target = item.id == primary.id
        if bool(item.is_primary) != target:
            item.is_primary = target
            item.updated_at = now


async def _set_primary_channel(
    *,
    session,
    agent_id: int,
    connection_id: int,
):
    rows = await session.scalars(
        select(AgentChannelConnection).where(AgentChannelConnection.agent_id == agent_id)
    )
    now = datetime.utcnow()
    for row in rows.all():
        row.is_primary = row.id == connection_id
        row.updated_at = now


async def _get_telegram_bot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "telegram_bot",
            AgentChannelConnection.connection_type == "bot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_telegram_userbot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "telegram_userbot",
            AgentChannelConnection.connection_type == "userbot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


async def _get_whatsapp_userbot_channel_for_agent(session, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "whatsapp_userbot",
            AgentChannelConnection.connection_type == "userbot",
            AgentChannelConnection.is_active.is_(True),
            AgentChannelConnection.encrypted_credentials.is_not(None),
        )
    )


def _whatsapp_user_external_to_jid(user_external_id: str) -> str:
    """Полный JID из аналитики (предпочтительно) или только цифры номера (старые записи)."""
    raw = (user_external_id or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Пустой идентификатор получателя WhatsApp",
        )
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный номер или JID WhatsApp (нужны цифры номера или полный JID)",
        )
    return f"{digits}@s.whatsapp.net"


async def _ensure_whatsapp_userbot_session(connection_id: int, encrypted_credentials: str) -> None:
    """Убедиться, что wa_bridge имеет активную runtime сессию для данного connection_id.

    Менеджер (whatsapp_userbot_manager.py) обычно поддерживает сессию через polling,
    но если он не запущен или перезапускался, сессии может не быть в runtimeSessions Map.
    Эта функция вызывает session/connect чтобы гарантировать наличие сессии перед отправкой.
    """
    if not encrypted_credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Отсутствуют credentials для WhatsApp канала",
        )
    try:
        bundle = json.loads(decrypt_token(encrypted_credentials))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось расшифровать credentials WhatsApp: {exc}",
        ) from exc
    session_string = str(bundle.get("session_string") or "").strip()
    if not session_string:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Отсутствует session_string в credentials WhatsApp",
        )
    # Вызываем session/connect для установки/восстановления сессии в wa_bridge
    await _wa_userbot_bridge_post(
        "session/connect",
        {
            "connection_id": connection_id,
            "session_string": session_string,
        },
    )


async def _list_whatsapp_userbot_broadcast_recipients(session, analytics_namespace_id: int) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id.label("uid"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                )
                .where(
                    AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                    AgentAnalyticsMessage.role == "user",
                    AgentAnalyticsMessage.channel == "whatsapp_userbot",
                    AgentAnalyticsMessage.user_external_id.is_not(None),
                )
                .group_by(AgentAnalyticsMessage.user_external_id)
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
            )
        )
        .mappings()
        .all()
    )
    recipients: list[dict] = []
    for row in rows:
        uid = row.get("uid")
        if not uid:
            continue
        uid_s = str(uid).strip()
        if not uid_s:
            continue
        recipients.append({"user_external_id": uid_s, "channel": "whatsapp_userbot"})
    return recipients


async def _telegram_get_me(bot_token: str) -> dict:
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/getMe"

    def _fetch():
        with urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


async def _sync_telegram_bot_webhook(bot_token: str, bot_id: int, enabled: bool) -> None:
    if not settings.BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BASE_URL is not configured for webhook setup",
        )
    if enabled:
        webhook_url = f"{settings.BASE_URL}/webhook/{bot_id}"
        request_url = (
            f"https://api.telegram.org/bot{quote(bot_token, safe='')}/setWebhook"
            f"?url={quote(webhook_url, safe='')}&drop_pending_updates=true"
        )
    else:
        request_url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/deleteWebhook"

    def _call():
        with urlopen(request_url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    result = await asyncio.get_running_loop().run_in_executor(None, _call)
    if not result or result.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось синхронизировать webhook Telegram: {result}",
        )


async def _waba_get_phone_number_info(phone_number_id: str, access_token: str) -> dict:
    request_url = (
        f"https://graph.facebook.com/v22.0/{quote(phone_number_id, safe='')}"
        "?fields=id,display_phone_number,verified_name,quality_rating"
    )
    request = UrlRequest(
        request_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    def _fetch():
        with urlopen(request, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return await asyncio.get_running_loop().run_in_executor(None, _fetch)


async def _map_telegram_userbot_access_hashes(
    session,
    *,
    analytics_namespace_id: int,
    user_external_ids: list[str],
) -> dict[str, int]:
    """Latest known access_hash per user for Telethon InputPeerUser (backend session has no entity cache)."""
    if not user_external_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id,
                    AgentAnalyticsMessage.telegram_peer_access_hash,
                    AgentAnalyticsMessage.created_at,
                )
                .where(
                    AgentAnalyticsMessage.bot_id == analytics_namespace_id,
                    AgentAnalyticsMessage.channel == "telegram_userbot",
                    AgentAnalyticsMessage.user_external_id.in_(user_external_ids),
                    AgentAnalyticsMessage.telegram_peer_access_hash.is_not(None),
                )
                .order_by(AgentAnalyticsMessage.created_at.desc())
            )
        )
        .all()
    )
    out: dict[str, int] = {}
    for uid, h, _ in rows:
        if not uid or h is None:
            continue
        key = str(uid)
        if key not in out:
            out[key] = int(h)
    return out


async def _latest_telegram_userbot_access_hash(
    session,
    *,
    analytics_namespace_id: int,
    user_external_id: str,
) -> int | None:
    ids = [user_external_id.strip()] if (user_external_id or "").strip() else []
    m = await _map_telegram_userbot_access_hashes(
        session, analytics_namespace_id=analytics_namespace_id, user_external_ids=ids
    )
    return m.get(ids[0]) if ids else None


async def _telegram_userbot_send_message(
    encrypted_bundle: str,
    chat_id: int,
    text: str,
    *,
    access_hash: int | None = None,
) -> None:
    from telethon.tl.types import InputPeerUser

    try:
        raw = decrypt_token(encrypted_bundle)
        data = json.loads(raw)
        api_id = int(data.get("api_id"))
        api_hash = str(data.get("api_hash") or "").strip()
        session_string = str(data.get("session_string") or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректные credentials userbot-канала: {exc}",
        )

    if not api_id or not api_hash or not session_string:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="В userbot-канале отсутствуют api_id/api_hash/session_string",
        )

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash, session_string=session_string)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Userbot session не авторизована",
            )
        if access_hash is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Нет telegram_peer_access_hash для этого пользователя. "
                    "Пусть пользователь снова напишет агенту в userbot (после обновления сервера), "
                    "чтобы сохранился access_hash для отправки."
                ),
            )
        peer = InputPeerUser(user_id=int(chat_id), access_hash=int(access_hash))
        await client.send_message(peer, text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram userbot send_message: {exc}",
        )
    finally:
        await client.disconnect()


async def _find_agent_with_access(
    agent_dao: AgentDAO,
    *,
    agent_id: int | None = None,
    bot_id: int | None = None,
    session=None,
    current_user,
    internal: bool,
):
    agent = None
    if agent_id is not None:
        agent = await agent_dao.find_one_by_filter(id=agent_id)
    elif bot_id is not None:
        if session is not None:
            agent, _ = await _find_agent_by_lookup_id(
                session=session,
                agent_dao=agent_dao,
                lookup_id=bot_id,
            )
        else:
            agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            if not agent and 0 < bot_id <= MAX_INT32:
                agent = await agent_dao.find_one_by_filter(id=bot_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if current_user and agent.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if current_user is None and not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return agent


async def _find_agent_by_lookup_id(
    *,
    session,
    agent_dao: AgentDAO,
    lookup_id: int,
):
    agent = await agent_dao.find_one_by_filter(bot_id=lookup_id)
    resolved_channel: AgentChannelConnection | None = None
    if not agent and 0 < lookup_id <= MAX_INT32:
        agent = await agent_dao.find_one_by_filter(id=lookup_id)
    if not agent:
        resolved_channel = await session.scalar(
            select(AgentChannelConnection).where(
                AgentChannelConnection.provider == "telegram_bot",
                AgentChannelConnection.connection_type == "bot",
                AgentChannelConnection.external_id == str(lookup_id),
                AgentChannelConnection.is_active.is_(True),
            )
        )
        if resolved_channel:
            agent = await agent_dao.find_one_by_filter(id=resolved_channel.agent_id)
    return agent, resolved_channel


def _resolve_lookup(agent_lookup: AgentLookup) -> tuple[int | None, int | None]:
    return agent_lookup.agent_id, agent_lookup.bot_id


def _safe_iso(value):
    if not value:
        return None
    try:
        return value.isoformat(sep=" ", timespec="seconds")
    except Exception:
        return str(value)


def _create_userbot_auth_token(
    *,
    api_id: int,
    api_hash: str,
    phone_number: str,
    phone_code_hash: str,
    encrypted_pending_session: str,
) -> str:
    now = datetime.utcnow()
    payload = {
        "scope": "userbot_auth",
        "api_id": api_id,
        "encrypted_api_hash": encrypt_token(api_hash),
        "phone_number": phone_number,
        "phone_code_hash": phone_code_hash,
        "encrypted_pending_session": encrypted_pending_session,
        "exp": now + timedelta(minutes=USERBOT_AUTH_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_userbot_auth_token(auth_token: str) -> dict:
    try:
        data = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен подтверждения userbot",
        )
    if data.get("scope") != "userbot_auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope токена подтверждения userbot",
        )
    return data


def _create_whatsapp_userbot_auth_token(
    *,
    user_id: int,
    phone_number: str,
    bridge_auth_id: str,
) -> str:
    now = datetime.utcnow()
    payload = {
        "scope": "whatsapp_userbot_auth",
        "user_id": int(user_id),
        "phone_number": phone_number,
        "encrypted_bridge_auth_id": encrypt_token(bridge_auth_id),
        "exp": now + timedelta(minutes=USERBOT_AUTH_TOKEN_TTL_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_whatsapp_userbot_auth_token(auth_token: str) -> dict:
    try:
        data = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или просроченный токен подтверждения WhatsApp userbot",
        )
    if data.get("scope") != "whatsapp_userbot_auth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный scope токена подтверждения WhatsApp userbot",
        )
    token_user_id = data.get("user_id")
    if not isinstance(token_user_id, int) or token_user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен подтверждения WhatsApp userbot не привязан к пользователю",
        )
    return data


async def _wa_userbot_bridge_post(path: str, payload: dict) -> dict:
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp userbot bridge не настроен на сервере",
        )

    url = f"{base}/{path.lstrip('/')}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    bridge_api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not bridge_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp userbot bridge API key не настроен на сервере",
        )
    headers["X-API-Key"] = bridge_api_key
    request = UrlRequest(url, data=body, headers=headers, method="POST")

    def _post():
        from urllib.error import HTTPError, URLError

        try:
            with urlopen(request, timeout=float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = str(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WhatsApp userbot bridge HTTP {exc.code}: {detail}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"WhatsApp userbot bridge transport error: {exc}",
            ) from exc

    result = await asyncio.get_running_loop().run_in_executor(None, _post)
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WhatsApp userbot bridge вернул неожиданный ответ",
        )
    return result


def _validate_whatsapp_session_string(
    *,
    session_string: str,
    expected_phone: str | None = None,
) -> tuple[str, dict]:
    normalized = (session_string or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сессия WhatsApp userbot пуста",
        )
    try:
        bundle = decode_whatsapp_session_bundle(normalized, settings.WA_USERBOT_SESSION_SECRET)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректная сессия WhatsApp userbot: {exc}",
        ) from exc

    bundle_phone = str(bundle.get("phone_number") or "").strip()
    if expected_phone and bundle_phone and bundle_phone != expected_phone.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Номер телефона в сессии не совпадает с указанным",
        )
    return bundle_phone or (expected_phone or "").strip(), bundle


def _create_telethon_client(api_id: int, api_hash: str, session_string: str = ""):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    return TelegramClient(StringSession(session_string), api_id, api_hash)


async def _validate_userbot_session(api_id: int, api_hash: str, session_string: str):
    try:
        import telethon  # noqa: F401
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash, session_string=session_string)
    try:
        await client.connect()
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="StringSession не авторизована. Сначала подтвердите вход через код Telegram.",
            )
        me = await client.get_me()
        if not me:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telethon не смог получить профиль пользователя",
            )
        return me
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось проверить userbot-сессию через Telethon: {exc}",
        )
    finally:
        await client.disconnect()


async def _telegram_api_send_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send a plain text message via Telegram Bot API (sync urllib in thread pool)."""
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/sendMessage"
    payload_bytes = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=False).encode("utf-8")

    def _post():
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = str(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Telegram sendMessage HTTP {exc.code}: {body}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Telegram sendMessage transport error: {exc}",
            ) from exc

    try:
        result = await asyncio.get_running_loop().run_in_executor(None, _post)
    except HTTPException:
        raise
    if not result or result.get("ok") is not True:
        detail = (result or {}).get("description") or str(result)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram sendMessage: {detail}",
        )


async def _log_analytics_message_for_agent_ids(
    *,
    session,
    agent_id: int,
    telegram_bot_id: int,
    role: str,
    message_text: str,
    channel: str = "telegram",
    user_external_id: str | None = None,
    user_display_name: str | None = None,
    telegram_peer_access_hash: int | None = None,
    tool_name: str | None = None,
    tool_args_hash: str | None = None,
    tool_status: str | None = None,
    latency_ms: int | None = None,
    crm_provider: str | None = None,
) -> None:
    normalized_text = (message_text or "").strip()
    if not normalized_text:
        return
    normalized_role = (role or "").strip().lower()
    if normalized_role not in {"user", "agent", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role must be one of: user, agent, operator",
        )
    normalized_channel = (channel or "telegram").strip().lower()
    if normalized_channel not in {
        "telegram",
        "external_api",
        "web",
        "dashboard",
        "telegram_userbot",
        "whatsapp_userbot",
        "whatsapp_business_api",
        "instagram",
        "tiktok",
        "pinterest",
    }:
        normalized_channel = "web"

    row = AgentAnalyticsMessage(
        agent_id=agent_id,
        bot_id=telegram_bot_id,
        role=normalized_role,
        channel=normalized_channel,
        user_external_id=(user_external_id or None),
        user_display_name=(user_display_name or None),
        telegram_peer_access_hash=telegram_peer_access_hash,
        tool_name=tool_name,
        tool_args_hash=tool_args_hash,
        tool_status=tool_status,
        latency_ms=latency_ms,
        crm_provider=crm_provider,
        message_text=normalized_text,
    )
    session.add(row)


async def _log_analytics_message(
    *,
    session,
    agent,
    role: str,
    message_text: str,
    channel: str = "telegram",
    user_external_id: str | None = None,
    user_display_name: str | None = None,
    telegram_peer_access_hash: int | None = None,
    tool_name: str | None = None,
    tool_args_hash: str | None = None,
    tool_status: str | None = None,
    latency_ms: int | None = None,
    crm_provider: str | None = None,
) -> None:
    resolved_channel_id = agent.bot_id if agent.bot_id is not None else agent.id
    await _log_analytics_message_for_agent_ids(
        session=session,
        agent_id=agent.id,
        telegram_bot_id=resolved_channel_id,
        role=role,
        message_text=message_text,
        channel=channel,
        user_external_id=user_external_id,
        user_display_name=user_display_name,
        telegram_peer_access_hash=telegram_peer_access_hash,
        tool_name=tool_name,
        tool_args_hash=tool_args_hash,
        tool_status=tool_status,
        latency_ms=latency_ms,
        crm_provider=crm_provider,
    )


async def _list_telegram_broadcast_recipient_ids(session, telegram_bot_id: int) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id.label("uid"),
                    AgentAnalyticsMessage.channel.label("channel"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                )
                .where(
                    AgentAnalyticsMessage.bot_id == telegram_bot_id,
                    AgentAnalyticsMessage.role == "user",
                    AgentAnalyticsMessage.channel.in_(["telegram", "telegram_userbot"]),
                    AgentAnalyticsMessage.user_external_id.is_not(None),
                )
                .group_by(AgentAnalyticsMessage.user_external_id, AgentAnalyticsMessage.channel)
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
            )
        )
        .mappings()
        .all()
    )
    recipients = []
    for row in rows:
        uid = row.get("uid")
        channel = (row.get("channel") or "").strip().lower()
        if not uid or not str(uid).isdigit():
            continue
        if channel not in {"telegram", "telegram_userbot"}:
            continue
        recipients.append({"user_external_id": str(uid), "channel": channel})
    return recipients


async def get_agent_by_external_api_key(
    x_agent_api_key: str | None = Header(default=None, alias="X-Agent-API-Key"),
):
    if not x_agent_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Agent-API-Key is required")
    api_key_hash = hash_agent_external_api_key(x_agent_api_key.strip())
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(external_api_key_hash=api_key_hash)
            if not agent:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
            return agent


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
                "encrypted_credentials": row["encrypted_credentials"],
            }
        )

    return JSONResponse(content=payload, status_code=status.HTTP_200_OK)


@router.post("/internal/process_message")
async def internal_process_message(
    request: Request,
    payload: InternalProcessMessageRequest,
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    await verify_internal_signature(request)

    try:
        channel = RuntimeChannel(payload.channel)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported channel",
        )

    request = RuntimeMessageRequest(
        bot_id=payload.bot_id,
        query=payload.query.strip(),
        user_external_id=payload.user_external_id.strip(),
        channel=channel,
        system_prompt=(payload.system_prompt or "").strip(),
        welcome_message=payload.welcome_message,
        user_display_name=(payload.user_display_name or "").strip() or None,
        telegram_peer_access_hash=payload.telegram_peer_access_hash,
    )
    response = await get_message_processor().process(request)
    return JSONResponse(
        content={
            "text": response.text,
            "status": response.status.value,
        },
        status_code=status.HTTP_200_OK,
    )


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
                current_config = _decode_template_config(agent.template_config) or {}
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
            channels = await _list_agent_channels(session, found_agent.id)
            crm_connections = await _list_agent_crm_connections(session, found_agent.id)
            payload = _serialize_agent(
                found_agent,
                include_external_api_key=True,
                include_encrypted_token=internal,
            )
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            payload["crm_connections"] = [_serialize_crm_connection(item) for item in crm_connections]
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
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
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
            return JSONResponse(
                content=[_serialize_agent(agent, include_encrypted_token=internal) for agent in (user.agents or [])],
                status_code=status.HTTP_200_OK,
            )


@router.post("")
async def create_empty_agent(
    payload: CreateEmptyAgent,
    current_user=Depends(get_current_user_required),
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            template_type = _normalize_template_type(payload.template_type)
            template_config = _normalize_template_config(template_type, payload.template_config)
            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
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
                    "is_active": False,
                }
            )
            await session.flush()
            return JSONResponse(
                content=_serialize_agent(created_agent, include_external_api_key=True),
                status_code=status.HTTP_201_CREATED,
            )


@router.post("/ByUserWith_tgID")
async def create_agent_by_tg_id(
    new_agent: NewAgent_byUserWith_tgID,
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


@router.post("/by_token")
async def create_agent_by_token(new_agent: NewAgent_byToken, current_user=Depends(get_current_user_required)):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    token_value = new_agent.bot_token.strip()

    try:
        me = await _telegram_get_me(token_value)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось связаться с Telegram для проверки токена: {e}",
        )

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
    new_agent: NewAgent_byUserbotSession, current_user=Depends(get_current_user_required)
):
    if current_user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

    api_id = new_agent.api_id
    api_hash = new_agent.api_hash.strip()
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

    api_id = payload.api_id
    api_hash = payload.api_hash.strip()
    phone_number = payload.phone_number.strip()

    try:
        from telethon.errors import FloodWaitError
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telethon не установлен на сервере: {exc}",
        )

    client = _create_telethon_client(api_id=api_id, api_hash=api_hash)
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось отправить код подтверждения Telegram: {exc}",
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

    client = _create_telethon_client(
        api_id=api_id,
        api_hash=api_hash,
        session_string=pending_session or "",
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

    result = await _wa_userbot_bridge_post(
        "auth/verify_code",
        {
            "auth_id": bridge_auth_id,
            "phone_number": phone_number,
            "code": code or None,
        },
    )
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
    result = await _wa_userbot_bridge_post(
        "auth/status",
        {
            "auth_id": bridge_auth_id,
        },
    )
    return JSONResponse(
        content={
            "status": result.get("status") or "pending",
            "qr_data_url": result.get("qr_data_url"),
            "last_error": result.get("last_error"),
            "last_disconnect_code": result.get("last_disconnect_code"),
        },
        status_code=status.HTTP_200_OK,
    )


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


@router.post("/channels/by_token")
async def add_agent_telegram_bot_channel(
    payload: AddTelegramBotChannel,
    current_user=Depends(get_current_user_required),
):
    token_value = payload.bot_token.strip()
    try:
        me = await _telegram_get_me(token_value)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось связаться с Telegram для проверки токена: {exc}",
        )
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
    api_id = payload.api_id
    api_hash = payload.api_hash.strip()
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
            if existing_userbot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен Telegram userbot-канал",
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
            if existing_whatsapp_userbot_channel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="У агента уже подключен WhatsApp userbot-канал",
                )
            duplicate_connection = await channel_connection_dao.find_one_by_filter(
                provider="whatsapp_userbot",
                external_id=normalized_phone,
            )
            if duplicate_connection:
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
            new_status = not agent.is_active
            await agent_dao.update(agent, {"is_active": new_status})

            telegram_channel = await _get_telegram_bot_channel_for_agent(session, agent.id)
            if telegram_channel and telegram_channel.encrypted_credentials:
                agent_token = decrypt_token(telegram_channel.encrypted_credentials)
                await _sync_telegram_bot_webhook(agent_token, int(telegram_channel.external_id), enabled=new_status)

            channels = await _list_agent_channels(session, agent.id)
            payload = _serialize_agent(agent, include_external_api_key=True, include_encrypted_token=internal)
            payload["channels"] = [_serialize_channel_connection(item) for item in channels]
            return JSONResponse(
                content=payload,
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
            await agent_dao.delete(agent)
    return Response(status_code=status.HTTP_200_OK)


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
            return JSONResponse(
                content=_serialize_agent(agent, include_external_api_key=True, include_encrypted_token=internal),
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
            "connection_id": connection_id,
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
                    "connection_id": connection_id,
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

            supported_chat_channels = ["telegram", "telegram_userbot", "whatsapp_userbot", "external_api"]

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

    knowledge_scope_id = agent.bot_id if agent.bot_id is not None else agent.id
    try:
        execution = await get_template_runtime().execute(
            template_type=agent.template_type,
            prompt=agent.system_prompt or "Ты — полезный ассистент.",
            user_message=message,
            knowledge_scope_id=knowledge_scope_id,
            agent_id=agent.id,
            user_external_id=external_user_id,
            template_config=_decode_template_config(agent.template_config),
            source_channel="external_api",
        )
        answer = execution.answer
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить ответ от LLM",
        )
    sources = execution.sources

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
                    crm_provider=(_decode_template_config(agent.template_config) or {}).get("crm_provider"),
                )

    return JSONResponse(
        content={
            "bot_id": agent.bot_id,
            "bot_username": agent.bot_username,
            "external_user_id": external_user_id,
            "answer": answer,
            "sources": sources,
        },
        status_code=status.HTTP_200_OK,
    )
