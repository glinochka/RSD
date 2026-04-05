import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from logging import getLogger

logger = getLogger(__name__)

from ..config import get_auth_data
from ..alembic.models import User
from ..router_users.dao import UserDAO

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=30)

    to_encode.update({"exp": expire})
    
    auth_data = get_auth_data()
    secret_key = auth_data['secret_key']
    algorithm = auth_data['algorithm']

    # PyJWT принимает ключ как строку или байты; оставим преобразование для совместимости
    if isinstance(secret_key, str):
        secret_key = secret_key.encode('utf-8')

    encode_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encode_jwt

async def get_user_from_access_token(token: str, user_dao: UserDAO) -> User:
    try:
        auth_data = get_auth_data()
        secret_key = auth_data['secret_key']
        algorithm = auth_data['algorithm']

        if isinstance(secret_key, str):
            secret_key = secret_key.encode('utf-8')

        # Декодируем токен; PyJWT сам проверяет срок действия (exp)
        data = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id = data.get('user_id')

    except InvalidTokenError as e:
        logger.info(f'Токен не валиден: {e}')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не валиден"
        )

    if not user_id:
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

    user = await user_dao.find_one_by_filter(id=int(user_id))

    if not user:
        logger.info(f'Пользователь не найден (id = {user_id})')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    logger.info("Токен пользователя обработан (id=%s)", user_id)
    return user
