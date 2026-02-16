from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status


from logging import getLogger

logger = getLogger(__name__)


from ..config import get_auth_data
from ..alembic.models import User
from ..users.dao import UserDAO
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=30)

    to_encode.update({"exp": expire})
    auth_data = get_auth_data()
    
    encode_jwt = jwt.encode(to_encode, auth_data['secret_key'], algorithm=auth_data['algorithm'])
    return encode_jwt

async def get_user_from_access_token(token: str, user_dao: UserDAO) -> User:
    try:
        auth_data = get_auth_data()
        data = jwt.decode(token, auth_data['secret_key'], algorithms=[auth_data['algorithm']])
        user_id = data.get('user_id')

    except JWTError:
        logger.info('Токен не валиден')

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
    expire_time = datetime.fromtimestamp(int(expire), tz=timezone.utc)

    if (not expire) or (expire_time < datetime.now(timezone.utc)):
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
    logger.info(f'Обрабработан токен пользователя: \n{user}')
    return user
    
