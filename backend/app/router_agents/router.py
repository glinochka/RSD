from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from logging import getLogger

from .schemas import *
from .dao import AgentDAO

from ..router_users.dao import UserDAO
from ..alembic.database import async_session_maker
from ..utils.convert import convert_to_dict

logger = getLogger(__name__)

router = APIRouter(prefix='/api/agents')

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

    return JSONResponse(
        content=dict_agent,
        status_code=status.HTTP_200_OK
        )
@router.get('/allBy_tgID')
async def readAllAgents(user: User_by_agent_or_tgID = Depends()):
    async with async_session_maker() as session:
        userDAO = UserDAO(session)
        async with session.begin():
            finded_user = await userDAO.find_one_by_filter(load_relations = True, telegram_id = user.id)
            if not finded_user:
                logger.error(f'пользователь с tg ID {user.id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            list_agents = finded_user.agents
            json_respose = []

            if list_agents:
                for agent in list_agents:
                    json_respose.append(convert_to_dict(agent))

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

    return JSONResponse(status_code=status.HTTP_201_CREATED)

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


    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)

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



    return JSONResponse(
        status_code=status.HTTP_200_OK
        )
