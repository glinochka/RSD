from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer

from logging import getLogger
from datetime import datetime
from .schemas import *
from .dao import UserDAO

from ..router_agents.dao import AgentDAO
from ..alembic.database import async_session_maker
from ..utils.security import get_password_hash, verify_password
from ..utils.JWT import create_access_token
from ..utils.convert import convert_to_dict
from ..utils.internal_auth import verify_internal_key

logger = getLogger(__name__)

router = APIRouter(prefix='/api/users')

http_bearer = HTTPBearer()


@router.post("")
async def create_user(user_by_tg: User_from_tg, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)

        async with session.begin():
            double_user = await user_dao.find_one_by_filter(name=user_by_tg.name)
            if double_user:
                logger.info(f'{user_by_tg.name} уже есть в базе данных')
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует"
                )
            
            dict_new_user = user_by_tg.model_dump()
            await user_dao.add(dict_new_user)
        
    logger.info(f'{user_by_tg.name} был добавлен')
    
    return Response(status_code=status.HTTP_201_CREATED)


@router.get("/by_agentID")
async def user_by_agentID(user_by_agent: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=user_by_agent.id)
            
            if not agent:
                logger.error(f'бот с айди {user_by_agent.id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            user = agent.user
            if not user:
                logger.error(f'пользователь владеющий ботом с айди {user_by_agent.id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this agent"
                )
            user_dict = convert_to_dict(user)
            # для json сериализации
            user_dict.pop('registered', None)
            sub_time: datetime = user_dict['subscription_end_date']
            user_dict['subscription_end_date'] = sub_time.isoformat()
            
            user_dict.pop('password', None)

    logger.info(f'запрос с {user_by_agent.id} был обработан')
    return JSONResponse(
        content = user_dict,
        status_code=status.HTTP_200_OK
        )

@router.get("/by_tgID")
async def user_by_tgID(user_by_tg: User_by_agent_or_tgID = Depends(), _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.id)
            
            if not user:
                logger.error(f'пользователь с tg айди {user_by_tg.id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            user_dict = convert_to_dict(user)
            # для json сериализации
            user_dict.pop('registered', None)
            sub_time: datetime = user_dict['subscription_end_date']
            user_dict['subscription_end_date'] = sub_time.isoformat()

            user_dict.pop('password', None)


    logger.info(f'запрос с {user_by_tg.id} был обработан')
    return JSONResponse(
        content = user_dict,
        status_code=status.HTTP_200_OK
        )
@router.patch("/by_tgID")
async def UpdateUser_by_tgID(user_by_tg: Update_userSubscription, _internal=Depends(verify_internal_key)):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(telegram_id=user_by_tg.telegram_id)
            
            if not user:
                logger.error(f'пользователь с tg айди {user_by_tg.telegram_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this tg ID"
                )
            update_dict = user_by_tg.model_dump()
            del update_dict['telegram_id']

            await user_dao.update(user, update_dict)

    logger.info(f'запрос с {user_by_tg.telegram_id} был обработан')
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

