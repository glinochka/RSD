from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from logging import getLogger

from .schemas import *
from .dao import AgentDAO

from ..router_users.dao import UserDAO
from ..alembic.database import async_session_maker
from ..utils.convert import convert_to_dict
from ..utils.JWT import get_user_from_access_token

logger = getLogger(__name__)

router = APIRouter(prefix='/api/agents')

http_bearer = HTTPBearer()


async def get_current_user(
    http_credentials: HTTPAuthorizationCredentials = Depends(http_bearer)
):
    """
    Returns the currently authenticated user from the Authorization: Bearer <token>.
    Also loads relations so `current_user.agents` is available.
    """
    token = http_credentials.credentials

    async with async_session_maker() as session:
        userDAO = UserDAO(session)
        async with session.begin():
            user = await get_user_from_access_token(token, userDAO)
            # Load relations (agents) explicitly, so they are available after the session ends.
            return await userDAO.find_one_by_filter(load_relations=True, id=user.id)


@router.get('')
async def readAgent(agent: Agent_by_botID = Depends()):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        
        async with session.begin():
            finded_agent = await agentDAO.find_one_by_filter(bot_id = agent.bot_id)
            if not finded_agent:
                logger.error(f'агент с ботом {agent.bot_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            dict_agent = convert_to_dict(finded_agent)
            # для json сериализации
            dict_agent.pop('registered', None)

    return JSONResponse(
        content=dict_agent,
        status_code=status.HTTP_200_OK
        )
@router.get('/allBy_tgID')
async def readAllAgents(current_user=Depends(get_current_user)):
    list_agents = current_user.agents or []
    json_respose = []

    for agent in list_agents:
        dict_agent = convert_to_dict(agent)
        # для json сериализации
        dict_agent.pop('registered', None)
        json_respose.append(dict_agent)

    return JSONResponse(
        content=json_respose,
        status_code=status.HTTP_200_OK
    )

@router.post('/ByUserWith_tgID')
async def createAgent_byTgID(newAgent: NewAgent_byUserWith_tgID):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        userDAO = UserDAO(session)
        async with session.begin():
            user = await userDAO.find_one_by_filter(telegram_id = newAgent.tg_id)
            if not user:
                logger.error(f'пользователь с tg id {newAgent.tg_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            newAgent = newAgent.model_dump()

            newAgent['user_id'] = user.id
            del newAgent['tg_id']

            await agentDAO.add(newAgent)

    return Response(status_code=status.HTTP_201_CREATED)


@router.post('/by_token')
async def createAgent_byToken(newAgent: NewAgent_byToken, current_user=Depends(get_current_user)):
    token_value = newAgent.bot_token.strip()
    token_parts = token_value.split(':', 1)
    if len(token_parts) != 2 or not token_parts[0].isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректный формат API ключа Telegram бота"
        )

    bot_id = int(token_parts[0])

    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        async with session.begin():
            duplicate_agent = await agentDAO.find_one_by_filter(bot_id=bot_id)
            if duplicate_agent:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот Telegram бот уже зарегистрирован"
                )

            await agentDAO.add(
                {
                    "user_id": current_user.id,
                    "bot_id": bot_id,
                    # Kept in the existing DB field used by the bot-service.
                    "encrypted_token": token_value,
                    "bot_username": None,
                    "system_prompt": newAgent.system_prompt.strip(),
                }
            )

    return JSONResponse(
        content={"bot_id": bot_id},
        status_code=status.HTTP_201_CREATED
    )

@router.patch('/by_botID')
async def updateBy_botID(newData: UpdateAgent):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        async with session.begin():
            agent = await agentDAO.find_one_by_filter(bot_id = newData.bot_id)
            if not agent:
                logger.error(f'агент с ботом {newData.bot_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            newData = newData.model_dump()
            del newData['bot_id']
            await agentDAO.update(agent, newData)


    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.patch('/toggle_status')
async def toggleStatus(agentID: Agent_by_botID):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        async with session.begin():
            agent = await agentDAO.find_one_by_filter(bot_id = agentID.bot_id)
            if not agent:
                logger.error(f'агент с ботом {agentID.bot_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            new_status = not agent.is_active
            await agentDAO.update(agent, {'is_active': new_status})

            agent_dict = convert_to_dict(agent)
            # для json сериализации
            agent_dict.pop('registered', None)
            
    return JSONResponse(
        content = agent_dict,
        status_code=status.HTTP_200_OK
        )

from ..qdrant.search_service import delete_agent_vectors
@router.delete('')
async def toggleStatus(agentID: Agent_by_botID = Depends()):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        async with session.begin():
            agent = await agentDAO.find_one_by_filter(bot_id = agentID.bot_id)
            if not agent:
                logger.error(f'агент с ботом {agentID.bot_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            is_deleted_vectors = await delete_agent_vectors(agentID.bot_id)
            if not is_deleted_vectors:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Qdrant deleting error"
                )
            await agentDAO.delete(agent)



    return Response(status_code=status.HTTP_200_OK)
