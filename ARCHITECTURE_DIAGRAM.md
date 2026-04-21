# 🏗️ Архитектура подключения каналов (после рефакторинга)

## Общая схема обработки сообщений

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                         INCOMING MESSAGE SOURCES                          ║
╠════════════════╦═════════════════════╦═══════════════╦═══════════════════╣
║  Telegram      ║  Telegram Userbot   ║  WhatsApp     ║ WhatsApp Userbot  ║
║  Master Bot    ║  (Telethon-based)   ║  Business     ║ (wa_bridge-based) ║
║                ║                     ║  API          ║                   ║
║ Webhook:       ║ Event-based:        ║ (FUTURE)      ║ Polling:          ║
║ POST /webhook  ║ NewMessage event    ║               ║ /session/pull     ║
║ /master        ║                     ║               ║ every 5 seconds   ║
╚════════════════╩═════════════════════╩═══════════════╩═══════════════════╝
       │                   │                              │
       │                   │                              │
       ├───────────────────┴──────────────────────────────┤
       │                                                  │
       v                                                  v
┌──────────────────────────────┐           ┌──────────────────────────────┐
│ REQUEST ADAPTER              │           │ wa_bridge REQUEST ADAPTER    │
│ (bot/handlers/agent.py)      │           │ (whatsapp_userbot_manager)   │
│                              │           │                              │
│ Extract from aiogram:        │           │ Extract from wa_bridge API:  │
│ • message.text               │           │ • incoming["message"]["..."] │
│ • message.from_user.id       │           │ • incoming["remote_jid"]     │
│ • message.from_user.full_name│           │ • incoming["push_name"]      │
└──────────────┬───────────────┘           └──────────────┬───────────────┘
               │                                          │
               │                 ┌────────────────────────┘
               │                 │
               v                 v
        ┌──────────────────────────────────┐
        │  Create MessageRequest object    │
        │                                  │
        │  {                               │
        │    bot_id: int,                  │
        │    query: str,                   │
        │    user_external_id: str,        │
        │    channel: Channel,  ← NEW      │
        │    system_prompt: str,           │
        │    welcome_message: str,         │
        │    user_display_name: str,       │
        │    telegram_peer_access_hash: int│
        │  }                               │
        └──────────────┬───────────────────┘
                       │
                       v
        ┌──────────────────────────────────────────────────────────┐
        │    UNIFIED MESSAGE PROCESSOR                             │
        │    (bot/core/message_processor.py) ✨ NEW                │
        │                                                          │
        │  async def process(request) → MessageResponse           │
        │  ─────────────────────────────────────────────────      │
        │                                                          │
        │  1️⃣  _check_subscription()                             │
        │      └─ Fetch owner subscription from backend API       │
        │         └─ Compare subscription_end_date with now()     │
        │            └─ Return: valid=True/False                  │
        │                                                          │
        │  2️⃣  _check_user_frozen()                              │
        │      └─ Call APIread.agentFrozenCheck(bot_id, user_id)  │
        │         └─ Return: frozen=True/False                    │
        │                                                          │
        │  3️⃣  Handle /start command                             │
        │      └─ If query == "/start":                           │
        │         └─ Return MessageResponse(welcome_message)      │
        │            └─ Status: WELCOME                           │
        │                                                          │
        │  4️⃣  Log incoming user message                         │
        │      └─ APIcreate.logAgentAnalyticsMessage(role="user") │
        │         └─ With graceful exception handling             │
        │                                                          │
        │  5️⃣  Retrieve context from knowledge base              │
        │      └─ APIread.contextBy_botID(bot_id, query)          │
        │         └─ Query Qdrant vectors                         │
        │            └─ Return: list[str] (context chunks)        │
        │                                                          │
        │  6️⃣  Generate LLM response                             │
        │      └─ ai_service.get_answer(query, context, prompt)   │
        │         └─ Call DeepSeek API                            │
        │            └─ Return: str (generated answer)            │
        │                                                          │
        │  7️⃣  Log outgoing agent response                       │
        │      └─ APIcreate.logAgentAnalyticsMessage(role="agent")│
        │         └─ With graceful exception handling             │
        │                                                          │
        │  RETURN: MessageResponse                                │
        │  {                                                       │
        │    text: str,                                            │
        │    status: ProcessingStatus                              │
        │      ├─ SUCCESS              (все ОК)                   │
        │      ├─ BLOCKED_USER         (пользователь заблокирован)│
        │      ├─ EXPIRED_SUBSCRIPTION (подписка истекла)         │
        │      ├─ WELCOME              (/start команда)           │
        │      └─ ERROR                (ошибка обработки)         │
        │  }                                                       │
        └──────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┴────────────────────┐
        │                                   │
        v                                   v
    ┌─────────────────┐           ┌──────────────────────┐
    │ SEND RESPONSE   │           │ BACKEND API CALLS    │
    │ via CHANNEL     │           │ (with caching TODO)  │
    │                 │           │                      │
    │ Telegram Bot:   │           │ • agentBy_botID()    │
    │ message.answer()│           │ • userBy_agentID()   │
    │                 │           │ • agentFrozenCheck() │
    │ Telegram        │           │ • contextBy_botID()  │
    │ Userbot:        │           │ • logAnalyticsMsg()  │
    │ event.respond() │           │                      │
    │                 │           │ Qdrant Search:       │
    │ WhatsApp        │           │ • Vector query       │
    │ Userbot:        │           │ • Return chunks      │
    │ bridge_post()   │           │                      │
    │ session/send    │           │ LLM Service:         │
    │                 │           │ • DeepSeek API       │
    │                 │           │ • Temperature, etc   │
    └─────────────────┘           └──────────────────────┘
```

---

## Обработка ошибок и граничные случаи

```
┌───────────────────────────────────────────────────────────────┐
│          MESSAGE PROCESSING - ERROR HANDLING FLOW             │
└───────────────────────────────────────────────────────────────┘

MessageRequest
    │
    ├─ Validate input
    │  └─ If invalid (empty query, no user_id)
    │     └─ Return ERROR (status 400)
    │
    ├─ Check subscription
    │  ├─ API error
    │  │  └─ FAIL OPEN (assume valid) ✓ Safe default
    │  │
    │  └─ Subscription expired
    │     └─ Return EXPIRED_SUBSCRIPTION with message
    │        └─ Stop processing (don't call LLM)
    │
    ├─ Check if user frozen
    │  ├─ API error
    │  │  └─ FAIL OPEN (assume not frozen) ✓ Safe default
    │  │
    │  └─ User is frozen
    │     └─ Return BLOCKED_USER with message
    │        └─ Stop processing
    │
    ├─ Handle /start command
    │  └─ Return WELCOME message
    │     └─ Stop processing (don't call LLM)
    │
    ├─ Log user message
    │  └─ If analytics fails
    │     └─ WARNING log (don't stop processing)
    │
    ├─ Retrieve context
    │  └─ If retrieval fails
    │     └─ Use empty context (don't stop processing)
    │
    ├─ Generate LLM response
    │  └─ If LLM fails
    │     └─ Return ERROR message
    │        └─ Still log failed attempt
    │
    ├─ Log agent response
    │  └─ If logging fails
    │     └─ WARNING log (don't stop processing)
    │
    └─ Return MessageResponse with text & status
```

---

## Rate Limiting на Webhooks

```
REQUEST: POST /webhook/{bot_id}
    │
    ├─ Check rate limiter (slowapi)
    │  ├─ Limit: 100 requests per minute per IP
    │  │
    │  ├─ If EXCEEDED
    │  │  └─ Return 429 Too Many Requests
    │  │     └─ Response: {"detail": "rate limit exceeded"}
    │  │
    │  └─ If OK
    │     └─ Continue processing
    │
    ├─ Parse & validate request
    │  ├─ If JSON invalid
    │  │  └─ Return 422 Unprocessable Entity
    │  │     └─ Log: WARNING "Invalid webhook payload"
    │  │
    │  └─ If valid
    │     └─ Continue
    │
    ├─ Process via handler
    │  ├─ Success
    │  │  └─ Return 200 {"status": "ok"}
    │  │
    │  └─ Error
    │     └─ Return 500 {"status": "error", "detail": "..."}
    │        └─ Log: ERROR with exception details
```

---

## Subscription Check Flow (Детально)

```
_check_subscription(bot_id: int) → dict[str, bool]
    │
    ├─ Fetch owner data
    │  │ APIread.userBy_agentID(bot_id)
    │  │
    │  ├─ ERROR (API down, 404, etc)
    │  │  └─ FAIL OPEN: return {"valid": True}
    │  │     └─ Rationale: Don't block users if API fails
    │  │
    │  └─ SUCCESS: get owner_json
    │
    ├─ Get subscription_end_date
    │  │
    │  ├─ None (Free tier, no expiry)
    │  │  └─ return {"valid": True}
    │  │
    │  ├─ Value (date string in ISO format)
    │  │  │
    │  │  ├─ Parse: datetime.fromisoformat()
    │  │  │  ├─ PARSE ERROR
    │  │  │  │  └─ FAIL OPEN: return {"valid": True}
    │  │  │  │
    │  │  │  └─ PARSE SUCCESS: subscription_end datetime
    │  │  │
    │  │  └─ Compare: subscription_end >= now()
    │  │     │
    │  │     ├─ YES (Not expired)
    │  │     │  └─ return {"valid": True}
    │  │     │
    │  │     └─ NO (Expired)
    │  │        └─ return {"valid": False}
    │
    └─ User checks during message processing:
       │
       ├─ Process.process() checks result
       │  │
       │  └─ if not subscription_check["valid"]:
       │     │
       │     └─ return MessageResponse(
       │          text="⚠️ Подписка истекла",
       │          status=EXPIRED_SUBSCRIPTION
       │        )
```

---

## Возможные расширения

### Future Architecture: Message Bus

```
Channel Events → Message Bus → Processors → Post-processors

┌─────────────┐
│   Channel   │
│ (Telegram,  │──────┐
│ WhatsApp)   │      │
└─────────────┘      │
                     │ Publish(UserMessageReceived)
                     │
                     v
            ┌────────────────────┐
            │   MESSAGE BUS      │
            │  (Redis/RabbitMQ)  │
            └────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         v           v           v
    ┌─────────┐ ┌────────┐ ┌──────────┐
    │Processor│ │Analytics│ │Features  │
    │         │ │Logging  │ │Tracking  │
    └─────────┘ └────────┘ └──────────┘
         │           │           │
         └───────────┼───────────┘
                     │ Publish(ProcessingComplete)
                     │
                     v
            ┌────────────────────┐
            │  POST-PROCESSORS   │
            │  (Stats, Cache, etc)
            └────────────────────┘
```

---

## Monitoring & Observability Points

```
┌──────────────────────────────────────────────────────────────┐
│  METRICS & MONITORING HOOKS                                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Webhook Metrics                                           │
│     └─ Rate limiting hits: /webhook hit limit                │
│        Latency: message received → response sent             │
│        Error rate: % of 5xx responses                        │
│                                                               │
│  2. Subscription Check Metrics                               │
│     └─ Check latency: API call duration                      │
│        Failure rate: % of API errors                         │
│        Expired users: how many rejected due to expiry        │
│                                                               │
│  3. Message Processing Metrics                               │
│     └─ Processing latency: total time per message            │
│        Status breakdown: % SUCCESS/BLOCKED/ERROR             │
│        Channel distribution: % per channel                   │
│                                                               │
│  4. Analytics Logging Metrics                                │
│     └─ Log success rate: % successful analytics logs         │
│        Log latency: time to log analytics                    │
│                                                               │
│  5. Context Retrieval Metrics                                │
│     └─ Retrieval latency: Qdrant query time                  │
│        Error rate: % context retrieval failures              │
│        Cache hit rate: % of cached contexts (future)         │
│                                                               │
│  6. LLM Generation Metrics                                   │
│     └─ Generation latency: DeepSeek API time                 │
│        Error rate: % LLM failures                            │
│        Token usage: tokens per message                       │
│        Cost: USD per message                                 │
│                                                               │
│  7. Channel Health Metrics                                   │
│     └─ Telegram Bot: webhook uptime                          │
│        Telegram Userbot: active connections                  │
│        WhatsApp Userbot: active connections, poll latency    │
│                                                               │
│  8. System Metrics                                           │
│     └─ Memory usage: MB per processor                        │
│        CPU usage: % utilization                              │
│        Error logs: ERROR level occurrences                   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT SETUP                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Production Bot Service                                      │
│  ├─ bot/main.py (FastAPI + Lifespan)                        │
│  │  ├─ Initialize Bot instances                             │
│  │  ├─ Setup Dispatchers                                    │
│  │  ├─ Setup Middleware (subscription check)               │
│  │  └─ Setup Rate Limiter (slowapi)                        │
│  │                                                           │
│  ├─ Async Managers (started in lifespan)                    │
│  │  ├─ UserbotManager (Telegram userbot polling)            │
│  │  └─ WhatsAppUserbotManager (WhatsApp polling)            │
│  │                                                           │
│  ├─ Shared Services                                          │
│  │  ├─ MessageProcessor (core logic)                        │
│  │  ├─ Backend API (HTTP client)                            │
│  │  ├─ LLM Service (DeepSeek wrapper)                       │
│  │  └─ Crypto utils (token decryption)                      │
│  │                                                           │
│  └─ Health Check Endpoint                                   │
│     └─ GET /health (readiness probe)                        │
│                                                               │
│  Dependencies                                                │
│  ├─ aiogram (Telegram bot framework)                        │
│  ├─ telethon (Telegram userbot library)                     │
│  ├─ fastapi (Web framework)                                 │
│  ├─ uvicorn (ASGI server)                                   │
│  ├─ httpx (HTTP client)                                     │
│  ├─ pydantic (Validation)                                   │
│  ├─ slowapi (Rate limiting) ← NEW                           │
│  ├─ cryptography (Token encryption)                         │
│  ├─ openai (LLM API client)                                 │
│  └─ qdrant-client (Vector DB)                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

**Версия**: 1.0  
**Дата**: 21 апреля 2026  
**Статус**: ✅ Реализовано
