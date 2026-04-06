import asyncio
import json
from logging import getLogger
from secrets import compare_digest
from urllib.parse import quote
from urllib.request import urlopen
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Date, cast, func, select

from .dao import AgentChannelConnectionDAO, AgentDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import AgentAnalyticsMessage, AgentFrozenUser
from ..config import settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_users.dao import UserDAO
from ..services.ai_authoring import (
    generate_answer_with_context,
    generate_welcome_with_ai,
    improve_prompt_with_ai,
)
from ..qdrant.search_service import search_knowledge_base
from ..utils.api_keys import generate_agent_external_api_key, hash_agent_external_api_key
from ..utils.JWT import get_user_from_access_token
from ..utils.convert import convert_to_dict
from ..utils.crypto import encrypt_token, decrypt_token
from ..utils.rate_limit import rate_limit

logger = getLogger(__name__)
router = APIRouter(prefix="/api/agents")
http_bearer = HTTPBearer(auto_error=False)
MAX_INT32 = 2_147_483_647


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


def is_internal_request(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> bool:
    configured_key = settings.INTERNAL_API_KEY.strip()
    if not configured_key or not x_internal_api_key:
        return False
    return compare_digest(x_internal_api_key, configured_key)


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
    if not include_encrypted_token:
        data.pop("encrypted_token", None)
    if include_external_api_key:
        if agent.encrypted_external_api_key:
            data["external_api_key"] = decrypt_token(agent.encrypted_external_api_key)
        else:
            data["external_api_key"] = None
    return data


async def _find_agent_with_access(
    agent_dao: AgentDAO,
    *,
    bot_id: int,
    current_user,
    internal: bool,
):
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


def _safe_iso(value):
    if not value:
        return None
    try:
        return value.isoformat(sep=" ", timespec="seconds")
    except Exception:
        return str(value)


async def _telegram_api_send_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send a plain text message via Telegram Bot API (sync urllib in thread pool)."""
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/sendMessage"
    payload_bytes = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=False).encode("utf-8")

    def _post():
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    result = await asyncio.get_running_loop().run_in_executor(None, _post)
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
) -> None:
    await _log_analytics_message_for_agent_ids(
        session=session,
        agent_id=agent.id,
        telegram_bot_id=agent.bot_id,
        role=role,
        message_text=message_text,
        channel=channel,
        user_external_id=user_external_id,
        user_display_name=user_display_name,
    )


async def _list_telegram_broadcast_recipient_ids(session, telegram_bot_id: int) -> list[str]:
    rows = (
        (
            await session.execute(
                select(
                    AgentAnalyticsMessage.user_external_id.label("uid"),
                    func.max(AgentAnalyticsMessage.created_at).label("last_at"),
                )
                .where(
                    AgentAnalyticsMessage.bot_id == telegram_bot_id,
                    AgentAnalyticsMessage.role == "user",
                    AgentAnalyticsMessage.channel == "telegram",
                    AgentAnalyticsMessage.user_external_id.is_not(None),
                )
                .group_by(AgentAnalyticsMessage.user_external_id)
                .order_by(func.max(AgentAnalyticsMessage.created_at).desc())
            )
        )
        .mappings()
        .all()
    )
    return [str(r["uid"]) for r in rows if r["uid"] and str(r["uid"]).isdigit()]


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


@router.get("")
async def read_agent(
    bot_id: int = Query(...),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            found_agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            # Fallback: Telegram webhook path sometimes carries internal Agent primary key.
            # If we can't find by Telegram bot_id, try by DB id only in int32 range.
            # Agents.id is INTEGER, while Telegram bot_id can exceed int32.
            if not found_agent and 0 < bot_id <= MAX_INT32:
                found_agent = await agent_dao.find_one_by_filter(id=bot_id)
            if not found_agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and found_agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            await _ensure_external_api_key(found_agent, agent_dao)
            return JSONResponse(
                content=_serialize_agent(
                    found_agent,
                    include_external_api_key=True,
                    include_encrypted_token=internal,
                ),
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

    async def telegram_get_me(bot_token: str) -> dict:
        url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/getMe"

        def _fetch():
            with urlopen(url, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        return await asyncio.get_running_loop().run_in_executor(None, _fetch)

    try:
        me = await telegram_get_me(token_value)
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
                    "template_type": new_agent.template_type,
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

    # Configure Telegram webhook so updates reach `bot/main.py` handler.
    # If BASE_URL is not set, it's impossible to register a public webhook URL.
    if not settings.BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BASE_URL is not configured for webhook setup",
        )

    try:
        webhook_url = f"{settings.BASE_URL}/webhook/{bot_id}"
        # setWebhook accepts `url` and optional `drop_pending_updates`.
        set_webhook_url = (
            f"https://api.telegram.org/bot{quote(token_value, safe='')}/setWebhook"
            f"?url={quote(webhook_url, safe='')}&drop_pending_updates=true"
        )

        def _set_webhook():
            with urlopen(set_webhook_url, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        webhook_result = await asyncio.get_running_loop().run_in_executor(None, _set_webhook)
        if not webhook_result or webhook_result.get("ok") is not True:
            raise RuntimeError(webhook_result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось установить webhook Telegram: {e}",
        )

    return JSONResponse(content={"bot_id": bot_id}, status_code=status.HTTP_201_CREATED)


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
            agent = await agent_dao.find_one_by_filter(bot_id=new_data.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            updates = new_data.model_dump(exclude_none=True)
            updates.pop("bot_id", None)
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
            agent = await agent_dao.find_one_by_filter(bot_id=agent_id.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            new_status = not agent.is_active
            await agent_dao.update(agent, {"is_active": new_status})

            # Keep Telegram webhook in sync with `is_active`.
            if settings.BASE_URL:
                agent_token = decrypt_token(agent.encrypted_token)
                webhook_url = f"{settings.BASE_URL}/webhook/{agent.bot_id}"

                try:
                    if new_status:
                        set_webhook_url = (
                            f"https://api.telegram.org/bot{quote(agent_token, safe='')}/setWebhook"
                            f"?url={quote(webhook_url, safe='')}&drop_pending_updates=true"
                        )

                        def _set_webhook():
                            with urlopen(set_webhook_url, timeout=15) as resp:
                                return json.loads(resp.read().decode("utf-8"))

                        webhook_result = await asyncio.get_running_loop().run_in_executor(
                            None, _set_webhook
                        )
                        if not webhook_result or webhook_result.get("ok") is not True:
                            raise RuntimeError(webhook_result)
                    else:
                        delete_webhook_url = (
                            f"https://api.telegram.org/bot{quote(agent_token, safe='')}/deleteWebhook"
                        )

                        def _delete_webhook():
                            with urlopen(delete_webhook_url, timeout=15) as resp:
                                return json.loads(resp.read().decode("utf-8"))

                        delete_result = await asyncio.get_running_loop().run_in_executor(
                            None, _delete_webhook
                        )
                        if not delete_result or delete_result.get("ok") is not True:
                            raise RuntimeError(delete_result)
                except Exception as e:
                    # Rollback is complicated; fail loudly so UI won't lie about status.
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Не удалось синхронизировать webhook Telegram: {e}",
                    )

            return JSONResponse(
                content=_serialize_agent(agent, include_external_api_key=True, include_encrypted_token=internal),
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
            agent = await agent_dao.find_one_by_filter(bot_id=agent_id.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            is_deleted_vectors = await delete_agent_vectors(agent_id.bot_id)
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
            agent = await agent_dao.find_one_by_filter(bot_id=payload.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

            try:
                improved_prompt = await improve_prompt_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось улучшить системный промпт через ИИ",
                )

            await agent_dao.update(agent, {"system_prompt": improved_prompt})
            return JSONResponse(
                content={"bot_id": agent.bot_id, "system_prompt": improved_prompt},
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
            agent = await agent_dao.find_one_by_filter(bot_id=payload.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

            try:
                welcome_message = await generate_welcome_with_ai(agent.system_prompt or "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Не удалось сгенерировать приветствие через ИИ",
                )

            await agent_dao.update(agent, {"welcome_message": welcome_message})
            return JSONResponse(
                content={"bot_id": agent.bot_id, "welcome_message": welcome_message},
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
            agent = await agent_dao.find_one_by_filter(bot_id=payload.bot_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            await _regenerate_external_api_key(agent, agent_dao)
            return JSONResponse(
                content=_serialize_agent(agent, include_external_api_key=True, include_encrypted_token=internal),
                status_code=status.HTTP_200_OK,
            )


@router.post("/analytics/messages/log")
async def log_analytics_message(
    payload: AgentAnalyticsMessageLog,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=payload.bot_id,
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
            )
    return Response(status_code=status.HTTP_201_CREATED)


@router.get("/analytics/summary")
async def read_analytics_summary(
    bot_id: int = Query(...),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=bot_id,
                current_user=current_user,
                internal=internal,
            )

            total_questions = (
                await session.scalar(
                    select(func.count(AgentAnalyticsMessage.id)).where(
                        AgentAnalyticsMessage.bot_id == agent.bot_id,
                        AgentAnalyticsMessage.role == "user",
                    )
                )
            ) or 0

            unique_users = (
                await session.scalar(
                    select(func.count(func.distinct(AgentAnalyticsMessage.user_external_id))).where(
                        AgentAnalyticsMessage.bot_id == agent.bot_id,
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
                            AgentAnalyticsMessage.bot_id == agent.bot_id,
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
    bot_id: int = Query(...),
    days: int = Query(default=30, ge=7, le=90),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=bot_id,
                current_user=current_user,
                internal=internal,
            )

            first_seen_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.min(AgentAnalyticsMessage.created_at).label("first_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == agent.bot_id,
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
                            AgentAnalyticsMessage.bot_id == agent.bot_id,
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
                    "bot_id": agent.bot_id,
                    "days": days,
                    "timeline": timeline,
                },
                status_code=status.HTTP_200_OK,
            )


@router.get("/analytics/frozen/check")
async def analytics_frozen_check(
    bot_id: int = Query(...),
    user_external_id: str = Query(..., max_length=128),
    internal: bool = Depends(is_internal_request),
):
    if not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal API key required")
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
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
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=payload.bot_id,
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
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=payload.bot_id,
                current_user=current_user,
                internal=False,
            )
            bot_token = decrypt_token(agent.encrypted_token)
            await _telegram_api_send_message(bot_token, chat_id, text)
            await _log_analytics_message(
                session=session,
                agent=agent,
                role="operator",
                message_text=text,
                channel="dashboard",
                user_external_id=str(chat_id),
                user_display_name=None,
            )
    return JSONResponse(content={"ok": True}, status_code=status.HTTP_200_OK)


@router.get("/telegram/broadcast_recipients")
async def telegram_broadcast_recipients(
    bot_id: int = Query(...),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=bot_id,
                current_user=current_user,
                internal=False,
            )
            recipient_ids = await _list_telegram_broadcast_recipient_ids(session, agent.bot_id)
            if not recipient_ids:
                return JSONResponse(
                    content={
                        "bot_id": agent.bot_id,
                        "telegram_users_total": 0,
                        "frozen_among_telegram": 0,
                        "eligible_when_skip_frozen": 0,
                    },
                    status_code=status.HTTP_200_OK,
                )
            frozen_rows = await session.scalars(
                select(AgentFrozenUser.user_external_id).where(
                    AgentFrozenUser.agent_id == agent.id,
                    AgentFrozenUser.user_external_id.in_(recipient_ids),
                )
            )
            frozen_set = set(frozen_rows.all())
            frozen_among = len(frozen_set)
            eligible = len([uid for uid in recipient_ids if uid not in frozen_set])
            return JSONResponse(
                content={
                    "bot_id": agent.bot_id,
                    "telegram_users_total": len(recipient_ids),
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
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=payload.bot_id,
                current_user=current_user,
                internal=False,
            )
            recipient_ids = await _list_telegram_broadcast_recipient_ids(session, agent.bot_id)
            agent_pk = agent.id
            telegram_bot_id = agent.bot_id
            bot_token = decrypt_token(agent.encrypted_token)

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

    skipped_frozen = sum(1 for uid in recipient_ids if payload.skip_frozen and uid in frozen_set)
    eligible_ids = [uid for uid in recipient_ids if not (payload.skip_frozen and uid in frozen_set)]
    to_send = eligible_ids[:max_n]
    truncated_over_limit = max(0, len(eligible_ids) - max_n)

    sent = 0
    failed = 0
    errors: list[dict] = []
    throttle_seconds = 0.05

    for uid in to_send:
        chat_id = int(uid)
        try:
            await _telegram_api_send_message(bot_token, chat_id, text)
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
                errors.append({"user_external_id": uid, "detail": detail})
        except Exception as exc:
            failed += 1
            if len(errors) < 25:
                errors.append({"user_external_id": uid, "detail": str(exc)})
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
    bot_id: int = Query(...),
    limit_users: int = Query(default=100, ge=1, le=500),
    messages_per_user: int = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await _find_agent_with_access(
                agent_dao,
                bot_id=bot_id,
                current_user=current_user,
                internal=internal,
            )

            user_rows = (
                (
                    await session.execute(
                        select(
                            AgentAnalyticsMessage.user_external_id.label("uid"),
                            func.max(AgentAnalyticsMessage.user_display_name).label("display_name"),
                            func.count(AgentAnalyticsMessage.id).label("questions"),
                            func.max(AgentAnalyticsMessage.created_at).label("last_message_at"),
                        ).where(
                            AgentAnalyticsMessage.bot_id == agent.bot_id,
                            AgentAnalyticsMessage.role == "user",
                            AgentAnalyticsMessage.user_external_id.is_not(None),
                        ).group_by(AgentAnalyticsMessage.user_external_id).order_by(
                            func.max(AgentAnalyticsMessage.created_at).desc()
                        ).limit(limit_users)
                    )
                )
                .mappings()
                .all()
            )

            user_ids = [row["uid"] for row in user_rows if row["uid"]]
            if not user_ids:
                return JSONResponse(
                    content={"bot_id": agent.bot_id, "users": []},
                    status_code=status.HTTP_200_OK,
                )

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
                            AgentAnalyticsMessage.bot_id == agent.bot_id,
                            AgentAnalyticsMessage.user_external_id.in_(user_ids),
                        ).order_by(AgentAnalyticsMessage.created_at.asc())
                    )
                )
                .mappings()
                .all()
            )

            grouped_messages = defaultdict(list)
            for row in message_rows:
                grouped_messages[row["user_external_id"]].append(row)

            users_payload = []
            for row in user_rows:
                uid = row["uid"]
                items = grouped_messages.get(uid, [])
                if messages_per_user > 0 and len(items) > messages_per_user:
                    items = items[-messages_per_user:]

                users_payload.append(
                    {
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
                content={"bot_id": agent.bot_id, "users": users_payload},
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

    external_user_id = (payload.external_user_id or "").strip() or None
    external_user_name = (payload.external_user_name or "").strip() or None

    context = await search_knowledge_base(message, agent_id=agent.bot_id)
    try:
        answer = await generate_answer_with_context(message, context, agent.system_prompt or "Ты — полезный ассистент.")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить ответ от LLM",
        )

    sources = []
    for item in context:
        source = item.get("source")
        if source and source not in sources:
            sources.append(source)

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

    return JSONResponse(
        content={
            "bot_id": agent.bot_id,
            "bot_username": agent.bot_username,
            "answer": answer,
            "sources": sources,
        },
        status_code=status.HTTP_200_OK,
    )
