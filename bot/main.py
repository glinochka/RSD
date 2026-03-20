import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from core.crypto import decrypt_token
from core.middlewares import AgentContextMiddleware
from handlers.agent import agent_router 
from handlers.master import master_router 
from core.backendAPI import *
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

master_bot = None
master_dp = None
agent_dp = None

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

# --- ЭНДПОИНТЫ (без изменений) ---
@app.post("/webhook/master")
async def handle_master_webhook(request: Request):
    global master_bot, master_dp
    if not master_dp or not master_bot:
        return {"status": "error", "detail": "Bot not initialized"}
    update_data = await request.json()
    tg_update = Update(**update_data)
    await master_dp.feed_update(master_bot, tg_update)
    return {"status": "ok"}

@app.post("/webhook/{bot_id}")
async def handle_agent_webhook(bot_id: int, request: Request):
    global agent_dp
    if not agent_dp:
        return {"status": "error", "detail": "Agent dispatcher not initialized"}
    try:
        agent_json = await APIread.agentBy_botID(bot_id)
        if agent_json.get('error_code') or not agent_json['is_active']:
            return {"status": "ignored"}
        
        token = decrypt_token(agent_json['encrypted_token'])
        async with Bot(token=token) as bot:
            update_data = await request.json()
            tg_update = Update(**update_data)

            await agent_dp.feed_update(
                bot, tg_update,
                bot_id = agent_json['bot_id'],
                system_prompt = agent_json['system_prompt'],
                welcome_message = agent_json['welcome_message']
            )
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"❌ Ошибка в агенте {bot_id}: {e}")
        return {"status": "error"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=False
    )
