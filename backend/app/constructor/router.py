from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from logging import getLogger

from .schemas import NewUser, LoginUser
from .dao import UserDAO

from ..alembic.database import async_session_maker
from ..utils.security import get_password_hash, verify_password
from ..utils.JWT import create_access_token

logger = getLogger(__name__)

router = APIRouter(prefix='/api/users')

http_bearer = HTTPBearer()

@router.post("/registration")
async def user_registration(new_user: NewUser):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            double_user = await user_dao.find_one_by_filter(name=new_user.name)
            if double_user:
                logger.info(f'{new_user.name} уже есть в базе данных')
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует"
                )
            
            dict_new_user = new_user.model_dump()
            dict_new_user['password'] = get_password_hash(dict_new_user['password'])

            user = await user_dao.add(dict_new_user)
        
    logger.info(f'{new_user.name} был добавлен')
    
    return JSONResponse(content = {
            'access_token': create_access_token({'user_id':str(user.id)}),
            'token_type': 'bearer'
        },
        status_code=status.HTTP_201_CREATED)

@router.post("/login")
async def user_login(login_user: LoginUser):

    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            user = await user_dao.find_one_by_filter(name=login_user.name)

    if not user:
        logger.info(f'{login_user.name} отсутствует в базе данных')
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден"
        )
    
    if not verify_password(login_user.password, user.password):
        logger.info(f'{login_user.name} выдан неверный пароль')
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный пароль"
        )
    
    logger.info(f'{login_user.name} вошел в систему') 
    
    access_token = create_access_token({'user_id':str(user.id)})
    return {
            'access_token': access_token,
            'token_type': 'bearer'
        }


