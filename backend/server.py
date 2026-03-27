from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from logging import getLogger
from app.logger_config import setup_logger
setup_logger()
logger = getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from app.router_users import router as users_router
from app.router_agents import router as agents_router
from app.router_documents import router as documents_router
from app.router_payments import router as payments_router
from app.router_admin import router as admin_router
from app.origins import origins
from app.config import settings
from app.services.subscription_maintenance import downgrade_expired_subscriptions_once
import uvicorn


from qdrant_client import QdrantClient
from qdrant_client.http import models

# --- ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    cron_task: asyncio.Task | None = None

    async def run_subscription_cron():
        while True:
            try:
                await downgrade_expired_subscriptions_once()
            except Exception:
                logger.exception("Subscription cron failed")
            await asyncio.sleep(3600)

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = "agent_documents"
    
    try:
        collections = client.get_collections().collections
        print(f"✅ Коллекция {collection_name} проверяется")
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

    cron_task = asyncio.create_task(run_subscription_cron())

    yield 

    if cron_task:
        cron_task.cancel()
        try:
            await cron_task
        except asyncio.CancelledError:
            pass




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
app.include_router(payments_router.router)
app.include_router(admin_router.router)


if __name__ == "__main__":

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )