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
from app.qdrant.embeddings import get_active_dense_model_name, get_dense_vector_size
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
    active_dense_model = get_active_dense_model_name()
    expected_vector_size = get_dense_vector_size()
    
    try:
        collections = client.get_collections().collections
        print(f"✅ Коллекция {collection_name} проверяется")
        exists = any(c.name == collection_name for c in collections)
        if not exists:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=expected_vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"✅ Коллекция {collection_name} создана")
        else:
            collection_info = client.get_collection(collection_name)
            vectors_cfg = collection_info.config.params.vectors
            if isinstance(vectors_cfg, dict):
                first_vec_cfg = next(iter(vectors_cfg.values()), None)
                current_vector_size = getattr(first_vec_cfg, "size", None)
            else:
                current_vector_size = getattr(vectors_cfg, "size", None)
            has_sparse_vectors = bool(getattr(collection_info.config.params, "sparse_vectors", None))

            if current_vector_size != expected_vector_size or has_sparse_vectors:
                print(
                    f"⚠️ Обнаружена несовместимая схема коллекции "
                    f"(size={current_vector_size}, sparse={has_sparse_vectors}). "
                    f"Пересоздаем под {active_dense_model}."
                )
                client.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=expected_vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                print(f"✅ Коллекция {collection_name} пересоздана")

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