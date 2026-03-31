import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc, select

from .dao import TelegramLinkChallengeDAO, UserDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import TelegramLinkChallenge
from ..config import settings
from ..router_agents.dao import AgentDAO
from ..utils.convert import convert_to_dict
from ..utils.internal_auth import verify_internal_key
from ..utils.JWT import create_access_token, get_user_from_access_token
from ..utils.security import get_password_hash, verify_password

logger = getLogger(__name__)

router = APIRouter(prefix="/api/users")

http_bearer = HTTPBearer(auto_error=False)
LINK_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
LINK_CODE_LENGTH = 8
LINK_CODE_TTL_MINUTES = 10
LINK_CODE_MAX_ATTEMPTS = 5


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_link_code(raw_code: str) -> str:
    return "".join(ch for ch in raw_code.upper().strip() if ch.isalnum())


def _format_link_code(raw_code: str) -> str:
    return f"{raw_code[:4]}-{raw_code[4:]}"


def _generate_link_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def _hash_link_code(raw_code: str) -> str:
    normalized_code = _normalize_link_code(raw_code)
    peppered_code = f"{settings.SECRET_KEY}:{normalized_code}"
    return hashlib.sha256(peppered_code.encode("utf-8")).hexdigest()


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
            user_dict = convert_to_dict(user)
            # для json сериализации
            user_dict.pop("registered", None)
            sub_time: datetime | None = user_dict.get("subscription_end_date")
            user_dict["subscription_end_date"] = sub_time.isoformat() if sub_time else None

            user_dict.pop("password", None)

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
            user_dict = convert_to_dict(user)
            # для json сериализации
            user_dict.pop("registered", None)
            sub_time: datetime | None = user_dict.get("subscription_end_date")
            user_dict["subscription_end_date"] = sub_time.isoformat() if sub_time else None

            user_dict.pop("password", None)


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






@router.post("/registration")
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
        
    logger.info(f"{new_user.name} был добавлен")

    return JSONResponse(content={
            "access_token": create_access_token({"user_id": str(user.id)}),
            "token_type": "bearer"
        },
        status_code=status.HTTP_201_CREATED)

@router.post("/login")
async def user_login(login_user: LoginUser):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            user = await user_dao.find_one_by_filter(name=login_user.name)

    if not user:
        logger.info(f"{login_user.name} отсутствует в базе данных")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден"
        )

    if (not user.password) or (not verify_password(login_user.password, user.password)):
        logger.info(f"{login_user.name} выдан неверный пароль")
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный пароль"
        )

    logger.info(f"{login_user.name} вошел в систему")

    access_token = create_access_token({"user_id": str(user.id)})
    return {
            "access_token": access_token,
            "token_type": "bearer"
        }


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
async def start_telegram_link(current_user=Depends(get_current_user_required)):
    if current_user.telegram_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram already linked",
        )

    code = _generate_link_code()
    code_hash = _hash_link_code(code)
    now_utc = _utc_now_naive()
    expires_at = now_utc + timedelta(minutes=LINK_CODE_TTL_MINUTES)

    async with async_session_maker() as session:
        challenge_dao = TelegramLinkChallengeDAO(session)
        async with session.begin():
            stale_result = await session.execute(
                select(TelegramLinkChallenge).where(
                    TelegramLinkChallenge.user_id == current_user.id,
                    TelegramLinkChallenge.status == "pending",
                )
            )
            stale_challenges = stale_result.scalars().all()
            for challenge in stale_challenges:
                await challenge_dao.update(challenge, {"status": "expired"})

            await challenge_dao.add(
                {
                    "user_id": current_user.id,
                    "code_hash": code_hash,
                    "expires_at": expires_at,
                    "attempts_left": LINK_CODE_MAX_ATTEMPTS,
                    "status": "pending",
                }
            )

    return JSONResponse(
        content={
            "code": _format_link_code(code),
            "expires_at": expires_at.isoformat(),
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
        challenge_dao = TelegramLinkChallengeDAO(session)
        async with session.begin():
            challenge_result = await session.execute(
                select(TelegramLinkChallenge)
                .where(
                    TelegramLinkChallenge.code_hash == code_hash,
                    TelegramLinkChallenge.status == "pending",
                )
                .order_by(desc(TelegramLinkChallenge.id))
                .limit(1)
            )
            challenge = challenge_result.scalar_one_or_none()
            if not challenge:
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

            linked_user = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
            if linked_user and linked_user.id != challenge.user_id:
                await challenge_dao.update(
                    challenge,
                    {"attempts_left": max(0, challenge.attempts_left - 1)},
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Telegram ID already linked to another account",
                )

            user = await user_dao.find_one_by_filter(id=challenge.user_id)
            if not user:
                await challenge_dao.update(challenge, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User for link code not found",
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

            stale_result = await session.execute(
                select(TelegramLinkChallenge).where(
                    TelegramLinkChallenge.user_id == user.id,
                    TelegramLinkChallenge.status == "pending",
                    TelegramLinkChallenge.id != challenge.id,
                )
            )
            stale_challenges = stale_result.scalars().all()
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

