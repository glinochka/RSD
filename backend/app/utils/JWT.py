import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from logging import getLogger
from typing import Literal
from sqlalchemy import select

logger = getLogger(__name__)

from ..config import get_auth_data, settings, sales_staff_token_expire_delta
from ..alembic.models import User, UserAuthSession
from ..router_users.dao import UserDAO

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    token_kind: Literal["user", "admin", "sales_staff"] = "user",
) -> str:
    to_encode = data.copy()
    if token_kind == "user" and to_encode.get("admin_web") is True:
        token_kind = "admin"

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    elif token_kind == "sales_staff":
        expire = datetime.now(timezone.utc) + sales_staff_token_expire_delta()
    else:
        expire_minutes = (
            settings.ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES
            if token_kind == "admin"
            else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    to_encode.update({"exp": expire, "token_kind": token_kind})

    auth_data = get_auth_data(token_kind)
    secret_key = auth_data['secret_key']
    algorithm = auth_data['algorithm']

    encode_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encode_jwt


def decode_access_token_payload(token: str, token_kind: Literal["user", "admin", "sales_staff"]) -> dict:
    try:
        auth_data = get_auth_data(token_kind)
        secret_key = auth_data["secret_key"]
        algorithm = auth_data["algorithm"]

        data = jwt.decode(token, secret_key, algorithms=[algorithm])
        if data.get("token_kind") != token_kind:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен не валиден",
            )
        return data
    except InvalidTokenError as e:
        logger.info("Токен не валиден: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не валиден",
        )


async def get_user_from_access_token(token: str, user_dao: UserDAO) -> User:
    data = decode_access_token_payload(token, "user")
    user_id = data.get("user_id")
    session_id = data.get("sid")

    if not user_id or not session_id:
        logger.info('ID пользователя не найден в токене')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID пользователя не найден в токене"
        )

    expire = data.get('exp')
    if not expire:
        logger.info('Токен истек (exp отсутствует)')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Токен истек'
        )
    try:
        expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        logger.info('Токен не валиден (exp некорректен)')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не валиден"
        )

    if expire_time < datetime.now(timezone.utc):
        logger.info(f'Токен истек (id = {user_id})')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Токен истек'
        )

    auth_session = await user_dao._session.scalar(
        select(UserAuthSession).where(
            UserAuthSession.id == str(session_id),
            UserAuthSession.user_id == int(user_id),
            UserAuthSession.revoked_at.is_(None),
        )
    )
    if not auth_session:
        logger.info("Сессия пользователя не найдена или отозвана (uid=%s, sid=%s)", user_id, session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия не активна",
        )
    if auth_session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        logger.info("Сессия пользователя истекла (uid=%s, sid=%s)", user_id, session_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла",
        )

    user = await user_dao.find_one_by_filter(id=int(user_id))

    if not user:
        logger.info(f'Пользователь не найден (id = {user_id})')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    if user.is_banned:
        logger.info("Заблокированный пользователь пытался авторизоваться (id=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован",
        )
    logger.info("Токен пользователя обработан (id=%s)", user_id)
    return user
