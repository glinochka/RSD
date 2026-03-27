import asyncio
import json
from logging import getLogger
from urllib.parse import quote
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .dao import AgentDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..config import settings
from ..qdrant.search_service import delete_agent_vectors
from ..router_users.dao import UserDAO
from ..services.ai_authoring import generate_welcome_with_ai, improve_prompt_with_ai
from ..utils.JWT import get_user_from_access_token
from ..utils.convert import convert_to_dict
from ..utils.crypto import encrypt_token, decrypt_token

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
    # If internal key is not configured, allow internal traffic only when header is present.
    if not configured_key:
        return x_internal_api_key is not None
    return x_internal_api_key == configured_key


def _assert_access(current_user, internal: bool) -> None:
    if current_user is None and not internal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


def _serialize_agent(agent) -> dict:
    data = convert_to_dict(agent)
    data.pop("registered", None)
    return data


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
            return JSONResponse(content=_serialize_agent(found_agent), status_code=status.HTTP_200_OK)


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
                content=[_serialize_agent(agent) for agent in (user.agents or [])],
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
            await agent_dao.add(payload)
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
        async with session.begin():
            duplicate_agent = await agent_dao.find_one_by_filter(bot_id=bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован",
                )
            await agent_dao.add(
                {
                    "user_id": current_user.id,
                    "bot_id": bot_id,
                    "encrypted_token": encrypt_token(token_value),
                    "bot_username": bot_username,
                    "system_prompt": new_agent.system_prompt.strip(),
                    # New agents should be immediately usable via Telegram webhook.
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

            return JSONResponse(content=_serialize_agent(agent), status_code=status.HTTP_200_OK)


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
