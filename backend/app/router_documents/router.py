import os
import hashlib
import tempfile
from logging import getLogger

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .dao import DocumentDAO
from .schemas import *
from ..alembic.database import async_session_maker
from ..alembic.models import AgentDocument
from ..config import settings
from ..qdrant.indexer import (
    extract_text,
    get_chunk_limit_by_plan,
    get_current_chunks_count,
    process_document,
    text_splitter,
)
from ..qdrant.search_service import delete_document_vectors, search_knowledge_base
from ..router_agents.dao import AgentDAO
from ..router_users.dao import UserDAO
from ..utils.JWT import get_user_from_access_token
from ..utils.convert import convert_to_dict

logger = getLogger(__name__)
router = APIRouter(prefix="/api/documents")
http_bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        return None
    token = http_credentials.credentials
    async with async_session_maker() as session:
        # Token contains `user_id`, so we must query the users table (UserDAO).
        # Using AgentDAO here makes user lookup fail and causes 401 redirects.
        user_dao = UserDAO(session)
        async with session.begin():
            user = await get_user_from_access_token(token, user_dao)
            return user


def is_internal_request(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> bool:
    configured_key = settings.INTERNAL_API_KEY.strip()
    # If internal key is not configured, allow internal traffic only when header is present.
    if not configured_key:
        return x_internal_api_key is not None
    return x_internal_api_key == configured_key


def _assert_access(current_user, internal: bool) -> None:
    if current_user is None and not internal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def _serialize_document(document) -> dict:
    data = convert_to_dict(document)
    data.pop("registered", None)
    # Convert date/datetime to ISO strings for JSONResponse.
    return jsonable_encoder(data)

def _save_upload_to_temp_with_hash(file: UploadFile, suffix: str) -> tuple[str, str]:
    hasher = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            temp_file.write(chunk)
        return temp_file.name, hasher.hexdigest()


@router.get("/allBy_botID")
async def read_all_documents(
    agent: Agent_by_botID = Depends(),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            found_agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=agent.bot_id)
            if not found_agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and found_agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            return JSONResponse(
                content=[_serialize_document(doc) for doc in (found_agent.documents or [])],
                status_code=status.HTTP_200_OK,
            )


# Must be registered before GET /{doc_id}, otherwise "getContextBy_agentID" is parsed as doc_id.
@router.api_route("/getContextBy_agentID", methods=["GET", "POST"])
async def get_context(
    agent_id: int,
    query: str,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(bot_id=agent_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    context = await search_knowledge_base(query, agent_id=agent_id)
    return JSONResponse(content=context, status_code=status.HTTP_200_OK)


@router.get("/{doc_id}")
async def read_document(
    doc_id: int,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        document_dao = DocumentDAO(session)
        async with session.begin():
            document = await document_dao.find_one_by_filter(id=doc_id, load_relations=True)
            if not document:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            if current_user and document.agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            return JSONResponse(content=_serialize_document(document), status_code=status.HTTP_200_OK)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    async with async_session_maker() as session:
        document_dao = DocumentDAO(session)
        async with session.begin():
            document = await document_dao.find_one_by_filter(id=doc_id, load_relations=True)
            if not document:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            if current_user and document.agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
            is_deleted = await delete_document_vectors(doc_id)
            if not is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Qdrant deleting error",
                )
            agent_id = document.agent_id
            await document_dao.delete(document)
            return JSONResponse(content={"agent_id": agent_id}, status_code=status.HTTP_200_OK)


@router.post("")
async def upload_document(
    background_tasks: BackgroundTasks,
    agent_data: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(get_current_user_optional),
    internal: bool = Depends(is_internal_request),
):
    _assert_access(current_user, internal)
    agent_by_id = Agent_by_botID.model_validate_json(agent_data)
    agent_id = agent_by_id.bot_id

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(load_relations=True, bot_id=agent_id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            if current_user and agent.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
            user = agent.user
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for this agent")

    current_plan = user.subscription_type
    limit = get_chunk_limit_by_plan(current_plan)

    temp_path, content_hash = _save_upload_to_temp_with_hash(
        file=file,
        suffix=os.path.splitext(file.filename)[1],
    )

    existing_doc = None
    async with async_session_maker() as session:
        async with session.begin():
            existing_doc = await session.scalar(
                select(AgentDocument).where(
                    AgentDocument.agent_id == agent.id,
                    AgentDocument.content_hash == content_hash,
                )
            )

    if existing_doc:
        if existing_doc.status == "error":
            async with async_session_maker() as session:
                doc_dao = DocumentDAO(session)
                async with session.begin():
                    found_doc = await doc_dao.find_one_by_filter(id=existing_doc.id)
                    await doc_dao.update(
                        found_doc,
                        {"status": "processing", "file_name": file.filename},
                    )
            background_tasks.add_task(
                process_document,
                file_path=temp_path,
                agent_id=agent_id,
                document_id=existing_doc.id,
                content_hash=content_hash,
            )
            data = {
                "status": "reprocessing",
                "document_id": existing_doc.id,
                "new_chunks_count": 0,
                "current_plan": current_plan,
                "limit": limit,
            }
            return JSONResponse(content=data, status_code=status.HTTP_200_OK)

        if os.path.exists(temp_path):
            os.remove(temp_path)
        data = {
            "status": "duplicate",
            "document_id": existing_doc.id,
            "document_status": existing_doc.status,
            "new_chunks_count": 0,
            "current_plan": current_plan,
            "limit": limit,
        }
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)

    text = await extract_text(temp_path)

    chunks = text_splitter.split_text(text)
    new_chunks_count = len(chunks)
    current_count = await get_current_chunks_count(agent_id)

    if current_count + new_chunks_count > limit:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        data = {
            "status": "limit_error",
            "current_plan": current_plan,
            "limit": limit,
            "current_count": current_count,
            "new_chunks_count": new_chunks_count,
        }
    else:
        doc = None
        try:
            async with async_session_maker() as session:
                doc_dao = DocumentDAO(session)
                async with session.begin():
                    doc_data = {
                        "agent_id": agent.id,
                        "file_name": file.filename,
                        "content_hash": content_hash,
                        "status": "processing",
                    }
                    doc = await doc_dao.add(doc_data)
                    await session.flush()
        except IntegrityError:
            async with async_session_maker() as session:
                async with session.begin():
                    existing_doc = await session.scalar(
                        select(AgentDocument).where(
                            AgentDocument.agent_id == agent.id,
                            AgentDocument.content_hash == content_hash,
                        )
                    )
            data = {
                "status": "duplicate",
                "document_id": existing_doc.id if existing_doc else None,
                "document_status": existing_doc.status if existing_doc else None,
                "new_chunks_count": 0,
                "current_plan": current_plan,
                "limit": limit,
            }
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return JSONResponse(content=data, status_code=status.HTTP_200_OK)

        background_tasks.add_task(
            process_document,
            file_path=temp_path,
            agent_id=agent_id,
            document_id=doc.id,
            content_hash=content_hash,
        )
        data = {
            "status": "limit_ok",
            "new_chunks_count": new_chunks_count,
            "current_plan": current_plan,
            "limit": limit,
            "current_count": current_count,
        }

    return JSONResponse(content=data, status_code=status.HTTP_200_OK)

