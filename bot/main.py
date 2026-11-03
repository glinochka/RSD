import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from fastapi.responses import JSONResponse

from core.crypto import decrypt_token
from core.middlewares import AgentContextMiddleware
from handlers.agent import agent_router
from handlers.master import master_router
from core.backendAPI import APIread
from core.config import settings
from core.telegram_webhook_secret import (
    telegram_webhook_secret,
    telegram_webhook_secret_matches,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

master_bot = None
master_dp = None
agent_dp = None

# Rate limiter: 100 requests per minute per IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Telegram may redeliver the same update_id if webhook does not ACK quickly enough.
# Voice (STT + LLM) can exceed that window → duplicate handlers → several bot replies for one ГС.
_AGENT_UPDATE_HANDLE_LOCKS: dict[tuple[int, int], asyncio.Lock] = {}
_AGENT_UPDATE_HANDLED_AT: dict[tuple[int, int], float] = {}
_AGENT_UPDATE_STATE_TTL_SEC = 600.0


def _prune_agent_update_state(now: float) -> None:
    cutoff = now - _AGENT_UPDATE_STATE_TTL_SEC
    stale = [k for k, t in _AGENT_UPDATE_HANDLED_AT.items() if t < cutoff]
    for k in stale:
        _AGENT_UPDATE_HANDLED_AT.pop(k, None)
        _AGENT_UPDATE_HANDLE_LOCKS.pop(k, None)


async def _run_agent_webhook_update_once(bot_id: int, update_id: int, coro_factory):
    """Run handler once per Telegram update_id; ignore duplicate webhook deliveries."""
    key = (int(bot_id), int(update_id))
    lock = _AGENT_UPDATE_HANDLE_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        _prune_agent_update_state(now)
        if key in _AGENT_UPDATE_HANDLED_AT:
            logger.info(
                "agent webhook: skipping duplicate update bot_id=%s update_id=%s",
                bot_id,
                update_id,
            )
            return
        await coro_factory()
        _AGENT_UPDATE_HANDLED_AT[key] = time.monotonic()


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

    webhook_url = f"{settings.BASE_URL}/webhook/master"
    master_secret = telegram_webhook_secret(
        encryption_key=settings.ENCRYPTION_KEY,
        scope="master",
    )
    master_webhook_ok = False
    for attempt in range(1, 6):
        try:
            await master_bot.set_webhook(
                url=webhook_url,
                secret_token=master_secret,
                drop_pending_updates=True,
            )
            master_webhook_ok = True
            logger.info("Master webhook secret registered")
            break
        except Exception:
            logger.error("Master webhook setup failed attempt=%s", attempt)
            await asyncio.sleep(3)
    if not master_webhook_ok:
        logger.error("Master webhook has no secret; updates will be rejected until setup succeeds")

    await _sync_agent_webhook_secrets()

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


def _webhook_authorized(request: Request, scope: str) -> bool:
    presented = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = telegram_webhook_secret(encryption_key=settings.ENCRYPTION_KEY, scope=scope)
    return telegram_webhook_secret_matches(presented, expected)


async def _sync_agent_webhook_secrets() -> None:
    """Re-register agent webhooks with the secret. Does not drop queued updates.

    The process rejects unsigned updates, so this must succeed before serving.
    Backend may still be running migrations when the bot starts.
    """
    payload = None
    for attempt in range(1, 9):
        try:
            payload = await APIread.telegramWebhookTargets()
        except Exception:
            payload = None
        if isinstance(payload, dict) and not payload.get("error_code") and isinstance(payload.get("items"), list):
            break
        logger.warning("agent webhook secret sync unavailable attempt=%s", attempt)
        payload = None
        await asyncio.sleep(min(5 * attempt, 20))
    if not isinstance(payload, dict):
        logger.error("agent webhook secret sync failed; agent bots will reject updates until the next restart")
        return
    items = payload.get("items")
    for item in items:
        if not isinstance(item, dict):
            continue
        bot_id = item.get("bot_id")
        encrypted = item.get("encrypted_token")
        if not bot_id or not encrypted:
            continue
        temp_bot = None
        try:
            token = decrypt_token(encrypted)
            secret = telegram_webhook_secret(
                encryption_key=settings.ENCRYPTION_KEY,
                scope=str(bot_id),
            )
            temp_bot = Bot(token=token)
            await temp_bot.set_webhook(
                url=f"{settings.BASE_URL}/webhook/{bot_id}",
                secret_token=secret,
                drop_pending_updates=False,
            )
        except Exception:
            logger.warning("agent webhook secret sync failed bot_id=%s", bot_id)
        finally:
            if temp_bot is not None:
                await temp_bot.session.close()


@app.post("/webhook/master")
@limiter.limit("100/minute")
async def handle_master_webhook(request: Request):
    """Handle incoming updates for master Telegram bot."""
    global master_bot, master_dp
    if not _webhook_authorized(request, "master"):
        return JSONResponse({"status": "error", "detail": "Unauthorized"}, status_code=401)
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
    if bot_id <= 0 or not _webhook_authorized(request, str(bot_id)):
        return JSONResponse({"status": "error", "detail": "Unauthorized"}, status_code=401)
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

        update_id = getattr(tg_update, "update_id", None)
        if update_id is None:
            logger.warning("agent webhook: missing update_id bot_id=%s, processing without dedup", bot_id)
            async with Bot(token=token) as bot:
                await agent_dp.feed_update(
                    bot,
                    tg_update,
                    bot_id=agent_json.get("bot_id"),
                    system_prompt=agent_json.get("system_prompt", ""),
                    welcome_message=agent_json.get("welcome_message"),
                    process_start_with_llm=bool(agent_json.get("process_start_with_llm", False)),
                )
        else:

            async def _run_feed():
                async with Bot(token=token) as bot:
                    await agent_dp.feed_update(
                        bot,
                        tg_update,
                        bot_id=agent_json.get("bot_id"),
                        system_prompt=agent_json.get("system_prompt", ""),
                        welcome_message=agent_json.get("welcome_message"),
                        process_start_with_llm=bool(agent_json.get("process_start_with_llm", False)),
                    )

            await _run_agent_webhook_update_once(bot_id, int(update_id), _run_feed)

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

