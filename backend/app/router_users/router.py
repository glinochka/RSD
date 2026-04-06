import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from logging import getLogger

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .dao import TelegramLinkChallengeDAO, UserDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import UserAuthSession
from ..config import settings
from ..router_agents.dao import AgentDAO
from ..utils.convert import convert_to_dict
from ..utils.internal_auth import verify_internal_key
from ..utils.JWT import create_access_token, decode_access_token_payload, get_user_from_access_token
from ..utils.rate_limit import rate_limit
from ..utils.security import get_password_hash, verify_password

logger = getLogger(__name__)

router = APIRouter(prefix="/api/users")

http_bearer = HTTPBearer(auto_error=False)
LINK_CODE_ALPHABET = "0123456789"
LINK_CODE_LENGTH = 6
LINK_CODE_TTL_MINUTES = 5
LINK_CODE_MAX_ATTEMPTS = 5
REFRESH_TOKEN_BYTES = 48


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_link_code(raw_code: str) -> str:
    return "".join(ch for ch in raw_code.upper().strip() if ch.isalnum())


def _format_link_code(raw_code: str) -> str:
    return raw_code


def _generate_link_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def _hash_link_code(raw_code: str) -> str:
    normalized_code = _normalize_link_code(raw_code)
    peppered_code = f"{settings.SECRET_KEY}:{normalized_code}"
    return hashlib.sha256(peppered_code.encode("utf-8")).hexdigest()


def _normalize_tg_username(username: str) -> str:
    value = username.strip()
    if value.startswith("@"):
        value = value[1:]
    return value.lower()


def _build_refresh_expiry() -> datetime:
    return _utc_now_naive() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _hash_refresh_token(refresh_token: str) -> str:
    material = f"{settings.USER_JWT_SECRET_KEY}:{refresh_token.strip()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


async def _issue_user_tokens(session, user_id: int) -> tuple[str, str]:
    session_id = secrets.token_hex(16)
    refresh_token = _generate_refresh_token()
    expires_at = _build_refresh_expiry()
    session.add(
        UserAuthSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=_hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
    )
    access_token = create_access_token({"user_id": str(user_id), "sid": session_id}, token_kind="user")
    return access_token, refresh_token


def _serialize_user_public(user) -> dict:
    user_dict = convert_to_dict(user)
    # Для JSON-сериализации удаляем неиспользуемые служебные поля.
    user_dict.pop("registered", None)
    sub_time: datetime | None = user_dict.get("subscription_end_date")
    user_dict["subscription_end_date"] = sub_time.isoformat() if sub_time else None
    user_dict.pop("password", None)
    return user_dict


async def _send_master_bot_link_prompt(telegram_id: int) -> None:
    token = settings.MASTER_BOT_TOKEN.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MASTER_BOT_TOKEN is not configured on backend",
        )

    message_text = (
        "Привязка web аккаунта с bot аккаунтом.\n"
        "Введите код, указанный на сайте (6 цифр), обычным сообщением в этот чат.\n\n"
        "Если вы не начинали привязку, проигнорируйте это сообщение."
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": telegram_id,
        "text": message_text,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        response = await client.post(url, json=payload)
    if not response.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to deliver message to Telegram user",
        )


async def get_current_user_required(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = http_credentials.credentials
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            return await get_user_from_access_token(token, user_dao)


@router.post("")
async def create_user(user_by_tg: User_from_tg, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            double_user = await user_dao.find_one_by_filter(name=user_by_tg.name)
            if double_user:
                logger.info(f"{user_by_tg.name} уже есть в базе данных")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует"
                )
            
            dict_new_user = user_by_tg.model_dump()
            await user_dao.add(dict_new_user)

    logger.info(f"{user_by_tg.name} был добавлен")

    return Response(status_code=status.HTTP_201_CREATED)


@router.get("/by_agentID")
async def user_by_agentID(user_by_agent: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=user_by_agent.id)
            
            if not agent:
                logger.error(f"бот с айди {user_by_agent.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            user = agent.user
            if not user:
                logger.error(f"пользователь владеющий ботом с айди {user_by_agent.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this agent"
                )
            user_dict = _serialize_user_public(user)

    logger.info(f"запрос с {user_by_agent.id} был обработан")
    return JSONResponse(
        content=user_dict,
        status_code=status.HTTP_200_OK
        )

@router.get("/by_tgID")
async def user_by_tgID(user_by_tg: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.id)
            
            if not user:
                logger.error(f"пользователь с tg айди {user_by_tg.id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            user_dict = _serialize_user_public(user)


    logger.info(f"запрос с {user_by_tg.id} был обработан")
    return JSONResponse(
        content=user_dict,
        status_code=status.HTTP_200_OK
        )
@router.patch("/by_tgID")
async def UpdateUser_by_tgID(user_by_tg: Update_userSubscription, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.telegram_id)
            
            if not user:
                logger.error(f"пользователь с tg айди {user_by_tg.telegram_id} не найден")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            update_dict = user_by_tg.model_dump()
            del update_dict["telegram_id"]

            await user_dao.update(user, update_dict)

    logger.info(f"запрос с {user_by_tg.telegram_id} был обработан")
    return Response(
        status_code=status.HTTP_204_NO_CONTENT
        )






@router.post("/registration", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_registration"))])
async def user_registration(new_user: NewUser):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            double_user = await user_dao.find_one_by_filter(name=new_user.name)
            if double_user:
                logger.info(f"{new_user.name} уже есть в базе данных")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует"
                )
            
            dict_new_user = new_user.model_dump()
            dict_new_user["password"] = get_password_hash(dict_new_user["password"])

            user = await user_dao.add(dict_new_user)
            await session.flush()
            access_token, refresh_token = await _issue_user_tokens(session, user.id)
        
    logger.info(f"{new_user.name} был добавлен")

    return JSONResponse(content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        },
        status_code=status.HTTP_201_CREATED)

@router.post("/login", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="users_login"))])
async def user_login(login_user: LoginUser):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            user = await user_dao.find_one_by_filter(name=login_user.name)

    if not user or (not user.password) or (not verify_password(login_user.password, user.password)):
        logger.info("Неуспешная попытка входа для имени: %s", login_user.name)
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
        )
    if user.is_banned:
        logger.info("Заблокированный пользователь попытался войти: %s", login_user.name)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован",
        )

    logger.info(f"{login_user.name} вошел в систему")

    async with async_session_maker() as session:
        async with session.begin():
            access_token, refresh_token = await _issue_user_tokens(session, user.id)

    return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


@router.post("/refresh", dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="users_refresh"))])
async def refresh_user_tokens(payload: RefreshTokenRequest):
    refresh_token = payload.refresh_token.strip()
    refresh_token_hash = _hash_refresh_token(refresh_token)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            auth_session = await session.scalar(
                select(UserAuthSession).where(UserAuthSession.refresh_token_hash == refresh_token_hash)
            )
            if not auth_session or auth_session.revoked_at is not None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid")
            if auth_session.expires_at < now_utc:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is expired")

            user = await user_dao.find_one_by_filter(id=auth_session.user_id)
            if not user:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            if user.is_banned:
                auth_session.revoked_at = now_utc
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Пользователь заблокирован")

            new_refresh_token = _generate_refresh_token()
            auth_session.refresh_token_hash = _hash_refresh_token(new_refresh_token)
            auth_session.expires_at = _build_refresh_expiry()
            auth_session.last_refreshed_at = now_utc

            access_token = create_access_token(
                {"user_id": str(user.id), "sid": auth_session.id},
                token_kind="user",
            )

    return JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/logout")
async def user_logout(
    current_user=Depends(get_current_user_required),
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token_payload(http_credentials.credentials, "user")
    session_id = payload.get("sid")
    if not session_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    now_utc = _utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            auth_session = await session.scalar(
                select(UserAuthSession).where(
                    UserAuthSession.id == str(session_id),
                    UserAuthSession.user_id == current_user.id,
                    UserAuthSession.revoked_at.is_(None),
                )
            )
            if auth_session:
                auth_session.revoked_at = now_utc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout_all")
async def user_logout_all(current_user=Depends(get_current_user_required)):
    now_utc = _utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            sessions = (
                await session.scalars(
                    select(UserAuthSession).where(
                        UserAuthSession.user_id == current_user.id,
                        UserAuthSession.revoked_at.is_(None),
                    )
                )
            ).all()
            for auth_session in sessions:
                auth_session.revoked_at = now_utc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def user_me(current_user=Depends(get_current_user_required)):
    return JSONResponse(
        content={
            "id": current_user.id,
            "name": current_user.name,
            "telegram_id": current_user.telegram_id,
            "is_telegram_linked": current_user.telegram_id is not None,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/telegram-link/start")
async def start_telegram_link(payload: TelegramLinkStartRequest, current_user=Depends(get_current_user_required)):
    if current_user.telegram_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram already linked",
        )

    normalized_tg_username = _normalize_tg_username(payload.telegram_username)
    now_utc = _utc_now_naive()
    expires_at = now_utc + timedelta(minutes=LINK_CODE_TTL_MINUTES)
    code = ""
    target_telegram_id: int | None = None

    async with async_session_maker() as session:
        challenge_dao = TelegramLinkChallengeDAO(session)
        user_dao = UserDAO(session)
        async with session.begin():
            target_user = await user_dao.find_telegram_user_by_normalized_name(normalized_tg_username)
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Telegram user not found. Ask user to start master bot first.",
                )

            code = _generate_link_code()
            code_hash = _hash_link_code(code)
            target_telegram_id = int(target_user.telegram_id)

            stale_challenges = await challenge_dao.find_pending_by_user_id(current_user.id)
            for challenge in stale_challenges:
                await challenge_dao.update(challenge, {"status": "expired"})

            await challenge_dao.add(
                {
                    "user_id": current_user.id,
                    "target_telegram_id": target_telegram_id,
                    "code_hash": code_hash,
                    "expires_at": expires_at,
                    "attempts_left": LINK_CODE_MAX_ATTEMPTS,
                    "status": "pending",
                }
            )
    if target_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram target is not set",
        )
    await _send_master_bot_link_prompt(target_telegram_id)

    return JSONResponse(
        content={
            "code": _format_link_code(code),
            "expires_at": expires_at.replace(tzinfo=timezone.utc).isoformat(),
            "expires_in_seconds": LINK_CODE_TTL_MINUTES * 60,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/telegram-link/confirm")
async def confirm_telegram_link(payload: TelegramLinkConfirmRequest, _internal=Depends(verify_internal_key)):
    normalized_code = _normalize_link_code(payload.code)
    code_hash = _hash_link_code(normalized_code)
    now_utc = _utc_now_naive()

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        challenge_dao = TelegramLinkChallengeDAO(session)
        async with session.begin():
            challenge = await challenge_dao.find_pending_by_code_and_target(
                code_hash=code_hash,
                target_telegram_id=payload.telegram_id,
            )
            if not challenge:
                latest_challenge = await challenge_dao.find_latest_pending_by_target_telegram_id(
                    target_telegram_id=payload.telegram_id
                )
                if latest_challenge:
                    new_attempts = max(0, latest_challenge.attempts_left - 1)
                    new_status = "blocked" if new_attempts == 0 else "pending"
                    await challenge_dao.update(
                        latest_challenge,
                        {"attempts_left": new_attempts, "status": new_status},
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid link code",
                )

            if challenge.expires_at < now_utc:
                await challenge_dao.update(challenge, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Link code expired",
                )

            if challenge.attempts_left <= 0:
                await challenge_dao.update(challenge, {"status": "blocked"})
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Link code blocked",
                )

            user = await user_dao.find_one_by_filter(id=challenge.user_id)
            if not user:
                await challenge_dao.update(challenge, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User for link code not found",
                )

            linked_user = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
            if linked_user and linked_user.id != challenge.user_id:
                # Auto-resolve "telegram-only" records created by master-bot bootstrap flow.
                # Those records have no password and can safely release telegram_id
                # so it can be attached to the authenticated web account.
                if linked_user.password is None:
                    # Preserve all agents created from Telegram account before linking.
                    linked_user_agents = await agent_dao.find_all_by_user_id(linked_user.id)
                    for linked_agent in linked_user_agents:
                        linked_agent.user_id = user.id
                    await user_dao.update(linked_user, {"telegram_id": None})
                    # Ensure unique index slot is released before assigning telegram_id to target user.
                    await session.flush()
                else:
                    await challenge_dao.update(
                        challenge,
                        {"attempts_left": max(0, challenge.attempts_left - 1)},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Telegram ID already linked to another account",
                    )

            if user.telegram_id and user.telegram_id != payload.telegram_id:
                await challenge_dao.update(
                    challenge,
                    {"attempts_left": max(0, challenge.attempts_left - 1)},
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already linked to another Telegram account",
                )

            if user.telegram_id is None:
                await user_dao.update(user, {"telegram_id": payload.telegram_id})

            await challenge_dao.update(
                challenge,
                {"status": "consumed", "consumed_at": now_utc},
            )

            stale_challenges = await challenge_dao.find_pending_by_user_id_except(
                user_id=user.id,
                challenge_id=challenge.id,
            )
            for stale in stale_challenges:
                await challenge_dao.update(stale, {"status": "expired"})

    return JSONResponse(
        content={
            "status": "linked",
            "user_id": user.id,
            "name": user.name,
            "telegram_id": payload.telegram_id,
        },
        status_code=status.HTTP_200_OK,
    )

