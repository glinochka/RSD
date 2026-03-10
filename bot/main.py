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



# --- ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    webhook_url = f"{settings.BASE_URL}/webhook/master"
    await master_bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print(f"✅ Вебхук установлен")

    yield # Работа приложения

    # SHUTDOWN
    print("🛑 Закрытие ресурсов...")
    await master_dp.storage.close()
    await agent_dp.storage.close()
    await master_bot.session.close()

# --- ИНИЦИАЛИЗАЦИЯ APP (с передачей lifespan) ---
app = FastAPI(lifespan=lifespan)

# --- НАСТРОЙКА AIOGRAM ---
master_bot = Bot(token=settings.MASTER_BOT_TOKEN)
master_dp = Dispatcher(storage=MemoryStorage())
master_dp.include_router(master_router)

agent_dp = Dispatcher(storage=MemoryStorage())
agent_dp.message.middleware(AgentContextMiddleware())
agent_dp.include_router(agent_router)

# --- ЭНДПОИНТЫ ---

@app.post("/webhook/master")
async def handle_master_webhook(request: Request):
    update_data = await request.json()
    tg_update = Update(**update_data)
    await master_dp.feed_update(master_bot, tg_update)
    return {"status": "ok"}

@app.post("/webhook/{bot_id}")
async def handle_agent_webhook(
    bot_id: int, 
    request: Request
):  
    
    try:
        
        agent_json = await APIread.agentBy_botID(bot_id)

        if  agent_json.get('error_code') or not agent_json['is_active']:
            return {"status": "ignored"}

        token = decrypt_token(agent_json['encrypted_token'])
        
        # Используем контекстный менеджер бота для авто-закрытия сессии
        async with Bot(token=token) as bot:
            update_data = await request.json()
            tg_update = Update(**update_data)
            await agent_dp.feed_update(bot, tg_update, agent_id=agent_json['id'])
            
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"❌ Ошибка в агенте {bot_id}: {e}")
        return {"status": "error"}