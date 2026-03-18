

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from logging import getLogger



from .schemas import *
from .dao import DocumentDAO

from ..router_agents.dao import AgentDAO
from ..alembic.database import async_session_maker
from ..utils.convert import convert_to_dict

logger = getLogger(__name__)

router = APIRouter(prefix='/api/documents')

@router.get('/allBy_botID')
async def readAllDocuments(agent: Agent_by_botID = Depends()):
    async with async_session_maker() as session:
        agentDAO = AgentDAO(session)
        async with session.begin():
            finded_agent = await agentDAO.find_one_by_filter(load_relations = True, bot_id = agent.bot_id)
            if not finded_agent:
                logger.error(f'агент с bot ID {agent.bot_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            list_docs = finded_agent.documents
            json_respose = []

            if list_docs:
                for doc in list_docs:
                    document_dict = convert_to_dict(doc)
                    # для json сериализации
                    document_dict.pop('registered', None)
                    json_respose.append(document_dict)

    return JSONResponse(
        content=json_respose,
        status_code=status.HTTP_200_OK
        )

@router.get('/{doc_id}')
async def readDocument(doc_id: int):
    async with async_session_maker() as session:
        documentDAO = DocumentDAO(session)
        async with session.begin():
            document = await documentDAO.find_one_by_filter(id = doc_id)
            if not document:
                logger.error(f'документ с ID {doc_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            document_json = convert_to_dict(document)
            # для json сериализации
            document_json.pop('registered', None)

    return JSONResponse(
        content=document_json,
        status_code=status.HTTP_200_OK
        )

from ..qdrant.search_service import delete_document_vectors, search_knowledge_base

@router.delete('/{doc_id}')
async def deleteDocument(doc_id: int):

    async with async_session_maker() as session:
        documentDAO = DocumentDAO(session)
        async with session.begin():
            document = await documentDAO.find_one_by_filter(id = doc_id, load_relations=True)

            
            if not document:
                logger.error(f'документ с ID {doc_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            is_deleted = await delete_document_vectors(doc_id)

            if not is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Qdrant deleting error"
                )
            agent = document.agent
            await documentDAO.delete(document)

    return JSONResponse(
        content={'agent_id': agent.id},
        status_code=status.HTTP_200_OK
        )

from ..qdrant.indexer import extract_text, text_splitter, get_current_chunks_count, CHUNK_LIMITS, process_document
import shutil
import tempfile
import os

@router.post('/getContextBy_agentID')
async def getContext(agentContext: Context_by_botID):
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id = agentContext.agent_id)
            
            if not agent:
                logger.error(f'бот с айди {agentContext.agent_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )

            
    contex = await search_knowledge_base(agentContext.query, agent_id = agentContext.agent_id)
    return JSONResponse(
        content= contex,
        status_code=status.HTTP_200_OK
        )



from ..qdrant.indexer import extract_text, text_splitter, get_current_chunks_count, CHUNK_LIMITS, process_document
import shutil
import tempfile
import os

@router.post('')
async def readAllDocuments(
    background_tasks: BackgroundTasks,
    agent_data: str = Form(...), 
    file: UploadFile = File(...)
    ):
    agentByID = Agent_by_botID.model_validate_json(agent_data)
    agent_id = agentByID.bot_id

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=agent_id)
            
            if not agent:
                logger.error(f'бот с айди {agent_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found"
                )
            user = agent.user
            if not user:
                logger.error(f'пользователь владеющий ботом с айди {agent_id} не найден')
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for this agent"
                )
            
    current_plan = user.subscription_type
    limit = CHUNK_LIMITS.get(current_plan, 100)

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        shutil.copyfileobj(file.file, temp_file)
        temp_path = temp_file.name
        
        text = await extract_text(temp_path)

    chunks = text_splitter.split_text(text)
    new_chunks_count = len(chunks)
    current_count = await get_current_chunks_count(agent_id)

    if current_count + new_chunks_count > limit:
        data = {
            'status': 'limit_error',
            'current_plan': current_plan,
            'limit': limit,
            'current_count': current_count,
            'new_chunks_count':new_chunks_count
        }
    else:
        async with async_session_maker() as session:
            doc_dao = DocumentDAO(session)
            async with session.begin():
                doc_data = {
                    'agent_id': agent_id,
                    'file_name': file.filename,
                    'status': 'processing'
                }
                doc = await doc_dao.add(doc_data)
                
        background_tasks.add_task(process_document, file_path = temp_path, agent_id = agent_id, document_id = doc.id)
        data = {
            'status': 'limit_ok',
            'new_chunks_count': new_chunks_count
        }




    return JSONResponse(
        content= data,
        status_code=status.HTTP_200_OK
        )

