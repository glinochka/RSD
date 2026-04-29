import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from core.crypto import decrypt_token
from core.middlewares import AgentContextMiddleware
from handlers.agent import agent_router
from handlers.master import master_router
from core.backendAPI import APIread
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

master_bot = None
master_dp = None
agent_dp = None

# Rate limiter: 100 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global master_bot, master_dp, agent_dp

    logger.info("🚀 LIFESPAN START")

    master_bot = Bot(token=settings.MASTER_BOT_TOKEN)
    master_dp = Dispatcher(storage=MemoryStorage())
    master_dp.include_router(master_router)

    agent_dp = Dispatcher(storage=MemoryStorage())
    agent_dp.message.middleware(AgentContextMiddleware())
    agent_dp.include_router(agent_router)

    try:
        webhook_url = f"{settings.BASE_URL}/webhook/master"
        await master_bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        logger.info(f"✅ Вебхук установлен: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Ошибка установки вебхука: {e}")

    yield

    # Shutdown
    logger.info("🛑 LIFESPAN STOP")
    if master_dp:
        await master_dp.storage.close()
    if agent_dp:
        await agent_dp.storage.close()
    if master_bot:
        await master_bot.session.close()


# FastAPI приложение с lifespan
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many requests"
))


@app.post("/webhook/master")
@limiter.limit("100/minute")
async def handle_master_webhook(request: Request):
    """Handle incoming updates for master Telegram bot."""
    global master_bot, master_dp
    if not master_dp or not master_bot:
        logger.error("Master bot not initialized")
        return {"status": "error", "detail": "Bot not initialized"}

    try:
        update_data = await request.json()
        tg_update = Update(**update_data)
        await master_dp.feed_update(master_bot, tg_update)
        return {"status": "ok"}
    except ValueError as e:
        logger.warning("Invalid webhook payload: %s", e)
        return {"status": "error", "detail": "Invalid payload"}
    except Exception as e:
        logger.exception("Error processing master webhook")
        return {"status": "error", "detail": "Internal error"}


@app.post("/webhook/{bot_id}")
@limiter.limit("100/minute")
async def handle_agent_webhook(bot_id: int, request: Request):
    """Handle incoming updates for agent Telegram bot."""
    global agent_dp
    if not agent_dp:
        logger.error("Agent dispatcher not initialized")
        return {"status": "error", "detail": "Agent dispatcher not initialized"}

    try:
        # Validate bot_id is a positive integer
        if bot_id <= 0:
            logger.warning("Invalid bot_id: %s", bot_id)
            return {"status": "error", "detail": "Invalid bot_id"}

        # Fetch agent configuration
        agent_json = await APIread.agentBy_botID(bot_id)
        if agent_json.get("error_code"):
            logger.warning("Agent fetch failed for bot_id=%s: error_code=%s", bot_id, agent_json.get("error_code"))
            return {"status": "ignored", "reason": "agent_fetch_failed"}

        if not agent_json.get("is_active"):
            logger.info("Agent not active: bot_id=%s", bot_id)
            return {"status": "ignored", "reason": "agent_not_active"}

        # Decrypt bot token
        try:
            token = decrypt_token(agent_json.get("encrypted_token"))
        except Exception as e:
            logger.error("Token decryption failed for bot_id=%s: %s", bot_id, e)
            return {"status": "error", "detail": "Token decryption failed"}

        # Parse update
        try:
            update_data = await request.json()
            tg_update = Update(**update_data)
        except ValueError as e:
            logger.warning("Invalid webhook payload for bot_id=%s: %s", bot_id, e)
            return {"status": "error", "detail": "Invalid payload"}

        # Process update
        async with Bot(token=token) as bot:
            await agent_dp.feed_update(
                bot,
                tg_update,
                bot_id=agent_json.get("bot_id"),
                system_prompt=agent_json.get("system_prompt", ""),
                welcome_message=agent_json.get("welcome_message"),
                process_start_with_llm=bool(agent_json.get("process_start_with_llm", False)),
            )

        return {"status": "ok"}

    except Exception as e:
        logger.exception("Error processing agent webhook for bot_id=%s", bot_id)
        return {"status": "error", "detail": "Internal error"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "master_bot_initialized": master_bot is not None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=False
    )

