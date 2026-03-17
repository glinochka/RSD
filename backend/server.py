from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.logger_config import setup_logger
setup_logger()

from fastapi.middleware.cors import CORSMiddleware
from app.router_users import router as users_router
from app.router_agents import router as agents_router
from app.router_documents import router as documents_router
from app.origins import origins
from app.config import settings
import uvicorn


from qdrant_client import QdrantClient
from qdrant_client.http import models


# --- ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = "agent_documents"
    
    try:
        collections = client.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
                sparse_vectors_config={
                    "sparse-text": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=True)
                    )
                }
            )
            print(f"✅ Коллекция {collection_name} создана")

    except Exception as e:
        print(f"⚠️ Qdrant Error: {e}")


    yield 





app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_methods = ['*'],
    allow_headers = ['*'],
    allow_credentials = True
)

app.include_router(users_router.router)
app.include_router(agents_router.router)
app.include_router(documents_router.router)


if __name__ == "__main__":

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True 
    )