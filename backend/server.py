from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from logging import getLogger
from app.logger_config import setup_logger
setup_logger()
logger = getLogger(__name__)
from app.services.error_log_service import record_error_log
from fastapi.middleware.cors import CORSMiddleware
from app.middleware import (
    CSPMiddleware,
    RateLimitMiddleware,
    SecurityAuditMiddleware,
)
from app.router_users import router as users_router
from app.router_agents import router as agents_router
from app.router_agents.public_router import router as agents_public_router
from app.router_documents import router as documents_router
from app.router_payments import router as payments_router
from app.router_referrals import router as referrals_router
from app.router_admin import router as admin_router
from app.router_sales import management_router as sales_management_router
from app.router_sales import router as sales_portal_router
from app.router_telephony import router as telephony_router
from app.router_websites.router import router as websites_router
from app.router_websites.public_router import router as websites_public_router
from app.origins import origins
from app.config import settings
from app.services.subscription_maintenance import downgrade_expired_subscriptions_once
from app.services.agent_autopay import process_agent_autopay_renewals_once
from app.services.agent_billing_maintenance import deactivate_expired_agent_maintenance_once
from app.services.onboarding_email_maintenance import send_onboarding_inactive_user_reminders_once
from app.services.reindex_jobs import run_reindex_worker_forever
from app.services.content_factory_worker import get_content_factory_worker
from app.services.sales.dm_outreach_worker import get_dm_outreach_worker
from app.services.article_publisher.worker import get_article_publisher_worker
from app.services.ai_mop import get_ai_mop_worker
from app.channels import UserbotManager, MaxBotManager, MaxUserbotManager, WhatsAppUserbotManager
from app.qdrant.embeddings import get_active_dense_model_name, get_dense_vector_size
from app.utils.internal_auth import is_request_secure
import uvicorn


from qdrant_client import QdrantClient
from qdrant_client.http import models

# --- ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    cron_task: asyncio.Task | None = None
    reindex_task: asyncio.Task | None = None
    userbot_manager: UserbotManager | None = None
    userbot_task: asyncio.Task | None = None
    max_bot_manager: MaxBotManager | None = None
    max_bot_task: asyncio.Task | None = None
    max_userbot_manager: MaxUserbotManager | None = None
    max_userbot_task: asyncio.Task | None = None
    whatsapp_userbot_manager: WhatsAppUserbotManager | None = None
    whatsapp_userbot_task: asyncio.Task | None = None
    content_factory_worker = None
    content_factory_task: asyncio.Task | None = None
    dm_outreach_worker = None
    dm_outreach_task: asyncio.Task | None = None
    article_publisher_worker = None
    article_publisher_task: asyncio.Task | None = None
    ai_mop_worker = None
    ai_mop_task: asyncio.Task | None = None

    async def run_subscription_cron():
        while True:
            try:
                await downgrade_expired_subscriptions_once()
                await process_agent_autopay_renewals_once()
                await deactivate_expired_agent_maintenance_once()
                await send_onboarding_inactive_user_reminders_once()
            except Exception as exc:
                logger.exception("Subscription cron failed")
                await record_error_log(
                    exc=exc,
                    source="cron",
                    scenario="subscription maintenance cron",
                    level="error",
                )
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
    reindex_task = asyncio.create_task(run_reindex_worker_forever())
    userbot_manager = UserbotManager()
    userbot_task = asyncio.create_task(userbot_manager.run_forever())
    max_bot_manager = MaxBotManager()
    max_bot_task = asyncio.create_task(max_bot_manager.run_forever())
    max_userbot_manager = MaxUserbotManager()
    max_userbot_task = asyncio.create_task(max_userbot_manager.run_forever())
    whatsapp_userbot_manager = WhatsAppUserbotManager()
    whatsapp_userbot_task = asyncio.create_task(whatsapp_userbot_manager.run_forever())
    if settings.CONTENT_FACTORY_ENABLED:
        content_factory_worker = get_content_factory_worker()
        content_factory_task = asyncio.create_task(content_factory_worker.run_forever())
        logger.info("ContentFactoryWorker enabled")
    else:
        logger.info("ContentFactoryWorker disabled via CONTENT_FACTORY_ENABLED")
    dm_outreach_worker = get_dm_outreach_worker()
    dm_outreach_task = asyncio.create_task(dm_outreach_worker.run_forever())
    logger.info("DmOutreachWorker enabled")
    if settings.ARTICLE_PUBLISHER_ENABLED:
        article_publisher_worker = get_article_publisher_worker()
        article_publisher_task = asyncio.create_task(article_publisher_worker.run_forever())
        logger.info("ArticlePublisherWorker enabled")
    else:
        logger.info("ArticlePublisherWorker disabled via ARTICLE_PUBLISHER_ENABLED")
    if settings.AI_MOP_ENABLED:
        ai_mop_worker = get_ai_mop_worker()
        ai_mop_task = asyncio.create_task(ai_mop_worker.run_forever())
        logger.info("AiMopWorker enabled")
    else:
        logger.info("AiMopWorker disabled via AI_MOP_ENABLED")

    yield 

    if cron_task:
        cron_task.cancel()
        try:
            await cron_task
        except asyncio.CancelledError:
            pass
    if reindex_task:
        reindex_task.cancel()
        try:
            await reindex_task
        except asyncio.CancelledError:
            pass
    if userbot_manager:
        await userbot_manager.shutdown()
    if userbot_task:
        userbot_task.cancel()
        try:
            await userbot_task
        except asyncio.CancelledError:
            pass
    if max_bot_manager:
        await max_bot_manager.shutdown()
    if max_bot_task:
        max_bot_task.cancel()
        try:
            await max_bot_task
        except asyncio.CancelledError:
            pass
    if max_userbot_manager:
        await max_userbot_manager.shutdown()
    if max_userbot_task:
        max_userbot_task.cancel()
        try:
            await max_userbot_task
        except asyncio.CancelledError:
            pass
    if whatsapp_userbot_manager:
        await whatsapp_userbot_manager.shutdown()
    if whatsapp_userbot_task:
        whatsapp_userbot_task.cancel()
        try:
            await whatsapp_userbot_task
        except asyncio.CancelledError:
            pass
    if content_factory_worker:
        await content_factory_worker.shutdown()
    if content_factory_task:
        content_factory_task.cancel()
        try:
            await content_factory_task
        except asyncio.CancelledError:
            pass
    if dm_outreach_worker:
        await dm_outreach_worker.shutdown()
    if dm_outreach_task:
        dm_outreach_task.cancel()
        try:
            await dm_outreach_task
        except asyncio.CancelledError:
            pass
    if article_publisher_worker:
        await article_publisher_worker.shutdown()
    if article_publisher_task:
        article_publisher_task.cancel()
        try:
            await article_publisher_task
        except asyncio.CancelledError:
            pass
    if ai_mop_worker:
        await ai_mop_worker.shutdown()
    if ai_mop_task:
        ai_mop_task.cancel()
        try:
            await ai_mop_task
        except asyncio.CancelledError:
            pass




app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        await record_error_log(
            exc=exc,
            source="api",
            status_code=exc.status_code,
            request=request,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    await record_error_log(
        exc=exc,
        source="api",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request=request,
        level="critical",
    )
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_origin_regex=r"https?://.*",
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Internal-API-Key",
        "X-Internal-Timestamp",
        "X-Internal-Signature",
        "X-Agent-API-Key",
    ],
    allow_credentials = True
)

# Security middleware
app.add_middleware(SecurityAuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSPMiddleware)


@app.middleware("http")
async def enforce_secure_transport_for_credentials(request: Request, call_next):
    sensitive_headers = {"authorization", "x-internal-api-key", "x-agent-api-key"}
    if any(header in request.headers for header in sensitive_headers):
        if not is_request_secure(request):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "HTTPS is required for credentialed requests"},
            )
    return await call_next(request)


app.include_router(users_router.router)
app.include_router(agents_router.router)
app.include_router(agents_public_router)
app.include_router(documents_router.router)
app.include_router(payments_router.router)
app.include_router(referrals_router.router)
app.include_router(admin_router.router)
app.include_router(sales_portal_router, prefix="/api/sales")
app.include_router(sales_management_router, prefix="/api/sales/management")
app.include_router(telephony_router)
app.include_router(websites_router)
app.include_router(websites_public_router, prefix="/public-website")

website_assets_path = os.getenv("WEBSITE_ASSETS_PATH", "/tmp/website_assets")
Path(website_assets_path).mkdir(parents=True, exist_ok=True)
app.mount(
    "/assets/websites",
    StaticFiles(directory=website_assets_path),
    name="website_assets",
)


if __name__ == "__main__":

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )