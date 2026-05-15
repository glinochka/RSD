# 🎯 Анализ Мультимодальной Обработки в RSD Backend

**Дата анализа:** 2026-05-15  
**Версия:** 1.0  
**Автор:** Code Analysis  
**Статус:** ✅ Complete Overview

---

## 📋 Содержание
1. [Архитектура мультимодальности](#архитектура-мультимодальности)
2. [Поток данных: Изображения и Голос](#поток-данных)
3. [Каналы и их обработка](#каналы-и-их-обработка)
4. [Обработка в Message Processor](#обработка-в-message-processor)
5. [Передача в агентов (Runtime Context)](#передача-в-агентов)
6. [Проблемы и ограничения](#проблемы-и-ограничения)
7. [Рекомендации](#рекомендации)

---

## 🏗️ Архитектура мультимодальности

### Общая схема
```
Мультимедиа-сообщение
        ↓
[Канал: Telegram, WhatsApp, MAX]
        ↓
[Загрузка медиа в память]
        ↓
[Обработка: голос → текст, фото → base64]
        ↓
[MessageRequest с runtime_context]
        ↓
[MessageProcessor]
        ↓
[TemplateRuntime → LLM с vision_image_data_url]
        ↓
[Ответ агента]
```

### Ключевые компоненты
| Компонент | Назначение | Файл |
|-----------|-----------|------|
| **Каналы** | Приём сообщений | `backend/app/channels/*_manager.py` |
| **Message Processor** | Валидация и предварительная обработка | `backend/app/channels/message_processor.py` |
| **Voice Transcription** | STT (Whisper) | `backend/app/services/voice_transcription.py` |
| **Router Agents** | HTTP endpoint обработки медиа | `backend/app/router_agents/router.py` |
| **Template Runtime** | Передача в LLM (DeepSeek) | `backend/app/services/template_runtime.py` |

---

## 🔄 Поток данных

### 1. ИЗОБРАЖЕНИЯ

#### 1.1 Загрузка из канала (Telegram Userbot)
**Файл:** `backend/app/channels/userbot_manager.py` (строки 194-202)

```python
if event.message.photo:
    buf = BytesIO()
    await event.message.download_media(buf)
    raw = buf.getvalue()
    if len(raw) > int(settings.IMAGE_MAX_BYTES):  # 10MB
        await event.respond("Изображение слишком большое...")
        return
    mime = "image/jpeg"
    runtime_ctx["vision_image_data_url"] = (
        f"data:{mime};base64,{base64.standard_b64encode(raw).decode('ascii')}"
    )
    query = caption_or_text or "[Фото без подписи]"
```

**Ключевые моменты:**
- ✅ Фото загружается в `BytesIO()`
- ✅ Кодируется в Base64
- ✅ Упаковывается как Data URL: `data:image/jpeg;base64,...`
- ✅ Сохраняется в `runtime_ctx["vision_image_data_url"]`
- ✅ Лимит: 10MB (`IMAGE_MAX_BYTES`)

#### 1.2 Загрузка через HTTP API
**Файл:** `backend/app/router_agents/router.py` (строки 3002-3011)

```python
if payload.image_base64:
    mime = ((payload.image_mime_type or "image/jpeg").strip() or "image/jpeg")
    raw_img = (payload.image_base64 or "").strip()
    try:
        img_bytes = base64.b64decode(raw_img, validate=True)
    except Exception:
        raise HTTPException(..., detail="Invalid image_base64")
    if len(img_bytes) > int(settings.IMAGE_MAX_BYTES):
        raise HTTPException(..., detail="image payload too large")
    runtime_ctx["vision_image_data_url"] = f"data:{mime};base64,{raw_img}"
```

**Schema:** `InternalProcessMessageRequest`
```python
image_base64: Optional[str] = Field(
    default=None,
    max_length=15_000_000,
    description="Изображение в Base64; см. IMAGE_MAX_BYTES на сервере",
)
image_mime_type: Optional[str] = Field(default="image/jpeg", max_length=128)
```

#### 1.3 Передача в LLM (DeepSeek)
**Файл:** `backend/app/channels/message_processor.py` (строки 232-239)

```python
merged_runtime_ctx: dict[str, object] = dict(request.runtime_context or {})
# ...
if isinstance(template_config, dict):
    vm = (
        str(
            template_config.get("vision_chat_model")
            or template_config.get("generation_model")
            or "deepseek-chat",
        ).strip()
        or "deepseek-chat"
    )
    merged_runtime_ctx.setdefault("vision_chat_model", vm)

execution = await get_template_runtime().execute(
    # ...
    runtime_context=merged_runtime_ctx,  # ← Здесь передаётся vision_image_data_url
)
```

**Конфигурация DeepSeek для мультимодальности:**
**Файл:** `backend/app/config.py` (строки 24-27)

```python
# Try DeepSeek /chat/completions with OpenAI-style multimodal payloads
# including data:image/...;base64,...
DEEPSEEK_CHAT_TRY_IMAGE_MULTIMODAL: bool = True
```

---

### 2. ГОЛОСОВЫЕ СООБЩЕНИЯ

#### 2.1 Загрузка из канала (Telegram Userbot)
**Файл:** `backend/app/channels/userbot_manager.py` (строки 206-210)

```python
elif getattr(event.message, "voice", None):
    buf = BytesIO()
    await event.message.download_media(buf)
    voice_bytes = buf.getvalue()
    if len(voice_bytes) > int(settings.VOICE_MAX_BYTES):  # 10MB
        await event.respond("Голосовое сообщение слишком большое...")
        return
    if not caption_or_text:
        query = ""
```

#### 2.2 Транскрипция голоса в текст
**Файл:** `backend/app/channels/userbot_manager.py` (строки 231-240)

```python
if voice_bytes is not None:
    if is_voice_stt_configured():
        transcript = await transcribe_voice_bytes(voice_bytes, mime_type="audio/ogg")
        if transcript:
            query = (
                f"{caption_or_text}\n\nТекст голосового сообщения: {transcript}".strip()
                if caption_or_text
                else f"Текст голосового сообщения: {transcript}"
            )
        else:
            query = caption_or_text or (
                "Пользователь прислал голосовое сообщение, но текст распознать не удалось."
            )
```

#### 2.3 STT-обработка (Faster Whisper или OpenAI)
**Файл:** `backend/app/services/voice_transcription.py`

```python
def is_voice_stt_configured() -> bool:
    """Whether we will attempt to transcribe voice (any backend)."""
    backend = (settings.VOICE_STT_BACKEND or "auto").strip().lower()
    openai_ok = bool((settings.OPENAI_API_KEY or "").strip())
    if backend == "openai":
        return openai_ok
    if backend == "faster_whisper":
        return faster_whisper_runtime_available()
    # auto
    return faster_whisper_runtime_available() or openai_ok
```

**Параметры STT:**
- `VOICE_STT_BACKEND`: `"auto" | "faster_whisper" | "openai"` 
- `FASTER_WHISPER_MODEL`: модель для local STT
- `FASTER_WHISPER_DEVICE`: `"auto" | "cuda" | "cpu"`
- `FASTER_WHISPER_LANGUAGE`: язык (пусто = auto-detect)
- `VOICE_MAX_BYTES`: 10MB
- `VOICE_TRANSCRIPTION_TIMEOUT_SECONDS`: 120 сек

#### 2.4 Загрузка голоса через HTTP API
**Файл:** `backend/app/router_agents/router.py` (строки 2968-2990)

```python
if payload.voice_base64:
    raw_voice = (payload.voice_base64 or "").strip()
    try:
        audio_bytes = base64.b64decode(raw_voice, validate=True)
    except Exception:
        raise HTTPException(..., detail="Invalid voice_base64")
    if len(audio_bytes) > int(settings.VOICE_MAX_BYTES):
        raise HTTPException(..., detail="voice payload too large")
    if is_voice_stt_configured():
        transcript = await transcribe_voice_bytes(
            audio_bytes,
            mime_type=(payload.voice_mime_type or "audio/ogg"),
        )
        if transcript:
            query_text = (
                f"{query_text}\n\nТекст голосового сообщения: {transcript}".strip()
                if query_text
                else f"Текст голосового сообщения: {transcript}"
            )
        elif not query_text:
            return JSONResponse(
                content={
                    "text": (
                        "Голосовые сообщения недоступны: не настроено распознавание речи "
                        "(установите faster-whisper и модель, либо задайте OPENAI_API_KEY)..."
                    ),
                    "status": RuntimeProcessingStatus.SUCCESS.value,
                },
                status_code=status.HTTP_200_OK,
            )
```

---

## 🔌 Каналы и их обработка

### Telegram Userbot
**Файл:** `backend/app/channels/userbot_manager.py`

| Мультимедиа | Поддержка | Реализация |
|-------------|----------|-----------|
| 📷 Фото | ✅ Да | `event.message.photo` → Base64 Data URL |
| 🎙️ Голос | ✅ Да | `event.message.voice` → Whisper STT |
| 📹 Видео | ❌ Нет | Явно не обрабатывается |
| 📄 Документы | ❌ Нет | Явно не обрабатывается |

### WhatsApp Userbot (через wa_bridge)
**Файл:** `backend/app/channels/whatsapp_userbot_manager.py`

**Обработка медиа:**
```python
def _extract_text(message: dict[str, Any]) -> str:
    msg = message.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or (msg.get("videoMessage") or {}).get("caption")
        or ""
    )
    return str(text).strip()
```

| Мультимедиа | Поддержка | Замечание |
|-------------|----------|----------|
| 📷 Фото | ⚠️ Только текст | Берётся только caption |
| 🎙️ Голос | ❌ Нет | Не обрабатывается |
| 📹 Видео | ⚠️ Только текст | Берётся только caption |

**Проблема:** WhatsApp userbot не скачивает медиа-файлы, только текстовую часть. Необходимо расширить wa_bridge для загрузки медиа.

### MAX Userbot
**Файл:** `backend/app/channels/max_userbot_manager.py`

```python
def _extract_sender_name(user_payload: dict[str, Any]) -> str | None:
    # ...
    text = str(message.get("text") or "").strip()
    if not text:
        return
```

| Мультимедиа | Поддержка | Замечание |
|-------------|----------|----------|
| 📷 Фото | ❌ Нет | Не обрабатывается |
| 🎙️ Голос | ❌ Нет | Не обрабатывается |
| 📹 Видео | ❌ Нет | Не обрабатывается |

---

## 📤 Обработка в Message Processor

**Файл:** `backend/app/channels/message_processor.py`

### MessageRequest dataclass
```python
@dataclass
class MessageRequest:
    bot_id: int
    query: str  # ← Основной текст (может содержать результат STT)
    user_external_id: str
    channel: Channel
    system_prompt: str = ""
    welcome_message: str | None = None
    process_start_with_llm: bool = False
    user_display_name: str | None = None
    telegram_peer_access_hash: int | None = None
    skip_chat_portrait_update: bool = False
    runtime_context: dict[str, object] | None = None  # ← Сюда кладётся vision_image_data_url
```

### Обработка в process()
```python
async def process(self, request: MessageRequest) -> MessageResponse:
    # 1. Валидация подписки, заморозка пользователя
    # 2. Парсинг конфигурации шаблона
    # 3. Проверка времени работы
    
    # 4. Обновление чат-портрета (если включено)
    chat_portrait = await get_template_runtime().update_chat_portrait(...)
    
    # 5. Объединение runtime_context
    merged_runtime_ctx = dict(request.runtime_context or {})
    if request.telegram_peer_access_hash:
        merged_runtime_ctx["telegram_peer_access_hash"] = ...
    if isinstance(template_config, dict):
        vm = str(template_config.get("vision_chat_model") or "deepseek-chat")
        merged_runtime_ctx.setdefault("vision_chat_model", vm)
    
    # 6. Выполнение шаблона
    execution = await get_template_runtime().execute(
        template_type=resolved_agent.template_type,
        prompt=request.system_prompt or resolved_agent.system_prompt,
        user_message=request.query,
        knowledge_scope_id=resolved_agent.bot_id or resolved_agent.id,
        agent_id=resolved_agent.id,
        user_external_id=normalized_user_external_id,
        template_config=template_config,
        source_channel=request.channel.value,
        chat_portrait=chat_portrait,
        runtime_context=merged_runtime_ctx,  # ← vision_image_data_url
    )
```

---

## 🧠 Передача в агентов

### Где используется runtime_context

**Файл:** `backend/app/services/template_runtime.py`

#### QA-подобные шаблоны (qa, lead_generation, content_factory)
```python
async def _execute_qa_like(
    self,
    *,
    prompt: str,
    user_message: str,  # ← Содержит текст или "[Фото без подписи]"
    knowledge_scope_id: int,
) -> TemplateExecutionResult:
    context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
    # 🔴 ПРОБЛЕМА: vision_image_data_url теряется для QA шаблонов!
    answer = await generate_answer_with_context(user_message, context_list, prompt)
    # LLM не получает изображение
```

#### CRM Admin шаблон
```python
async def _execute_crm_admin(
    self,
    *,
    prompt: str,
    user_message: str,
    template_config: dict[str, Any],
    runtime_context: dict[str, object] | None = None,  # ← Получает runtime_context
    # ...
) -> TemplateExecutionResult | None:
    # Подготовка системного промпта
    system_prompt = (
        f"{prompt}\n\n"
        "Ты CRM-администратор. Если нужно действие в CRM — используй function tools..."
    )
    
    # Подготовка сообщений для LLM
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message})
    
    # Отправка в DeepSeek
    completion = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=llm_tools,
        tool_choice="auto",
        temperature=0.2,
    )
```

**Ключевой вопрос:** Где используется `vision_image_data_url` из `runtime_context`?

❌ **Ответ:** Нигде явно не используется!

### Как должна работать Vision (OpenAI-стиль)

```python
# Правильный формат для DeepSeek/OpenAI:
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": user_message},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZ..."
                }
            }
        ]
    }
]

completion = await ai_client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    # ...
)
```

**Текущее состояние:** 
- ✅ `vision_image_data_url` кладётся в `runtime_context`
- ❌ `vision_image_data_url` никогда не используется в `generate_answer_with_context()`
- ❌ `generate_answer_with_context()` отправляет только текст
- ❌ LLM никогда не видит изображение

---

## ⚠️ Проблемы и ограничения

### Критические проблемы

#### 1. **Vision не работает для QA шаблонов** 🔴
- **Файл:** `backend/app/services/ai_authoring.py` / `template_runtime.py`
- **Проблема:** `runtime_context` с `vision_image_data_url` не передаётся в `generate_answer_with_context()`
- **Следствие:** Агент никогда не видит изображения
- **Влияние:** Все QA, lead_generation, content_factory агенты не могут анализировать картинки
- **Решение:** Переделать `generate_answer_with_context()` для приёма `runtime_context`

#### 2. **WhatsApp не загружает медиа** 🔴
- **Файл:** `backend/app/channels/whatsapp_userbot_manager.py`
- **Проблема:** `_extract_text()` берёт только текстовую часть сообщения
- **Текущее:** `imageMessage.caption`, `videoMessage.caption`
- **Отсутствует:** Загрузка `imageMessage.imageData`, `audioMessage.audioData`
- **Следствие:** WhatsApp юзербот теряет все изображения и аудио
- **Решение:** Расширить обработку для скачивания и кодирования медиа

#### 3. **MAX не поддерживает медиа вообще** 🔴
- **Файл:** `backend/app/channels/max_userbot_manager.py`
- **Проблема:** В `_process_event()` ищется только `message.text`
- **Отсутствует:** Обработка вложений/медиа в MAX API
- **Следствие:** Все графики, фото, голос игнорируются
- **Решение:** Добавить парсинг структуры медиа-сообщений MAX

#### 4. **vision_chat_model не обрабатывается** 🟡
- **Файл:** `backend/app/services/ai_authoring.py`
- **Проблема:** `template_config.vision_chat_model` устанавливается, но не используется
- **Текущее:** `ai_client.chat.completions.create(model="deepseek-chat")`
- **Следствие:** Для vision всегда используется `deepseek-chat`
- **Решение:** Передавать `vision_chat_model` из `runtime_context` в `generate_answer_with_context()`

### Архитектурные проблемы

#### 5. **Нет версионирования для медиа-формата** 🟡
- Если захотим менять формат передачи изображений (например, с data URL на URL), 
  нужна миграция по всему коду
- Рекомендация: Создать `MediaPayload` dataclass

#### 6. **STT ошибки пересасываются в пользовательское сообщение** 🟡
- Файл: `backend/app/channels/userbot_manager.py:233-240`
- Если Whisper упал: `"Пользователь прислал голосовое сообщение, но текст распознать не удалось"`
- Это может быть очень неудобно для пользователя
- Рекомендация: Отправлять ошибку отдельным сообщением

#### 7. **Нет кэширования медиа** 🟡
- Большие файлы каждый раз кодируются/декодируются
- Нет дедупликации одинаковых фото
- Рекомендация: Redis кэш для `(file_hash, channel) → base64_url`

### Лимиты и ограничения

| Параметр | Значение | Источник |
|----------|---------|---------|
| IMAGE_MAX_BYTES | 10 MB | `config.py:39` |
| VOICE_MAX_BYTES | 10 MB | `config.py:38` |
| VOICE_TRANSCRIPTION_TIMEOUT | 120 сек | `config.py:40` |
| Поддерживаемые форматы фото | JPEG | Hardcoded |
| Поддерживаемые форматы голоса | OGG, WAV, MP3, M4A | Whisper |

---

## 🔍 Детальный анализ по каналам

### TELEGRAM USERBOT
```
Входящее → Telethon → Photo/Voice/Text
           ↓
           if photo:
             - download_media(BytesIO)
             - Base64 encode
             - runtime_ctx["vision_image_data_url"] = data URL
             - query = caption or "[Фото без подписи]"
           
           if voice:
             - download_media(BytesIO)
             - transcribe_voice_bytes()
             - query = "Текст голосового сообщения: {transcript}"
           
           MessageRequest(query, runtime_ctx)
           ↓
           MessageProcessor.process()
           ↓
           TemplateRuntime.execute(runtime_context)
           ↓
           generate_answer_with_context(user_message)  ← vision_context теряется!
```

### WHATSAPP USERBOT (через wa_bridge)
```
Входящее → wa_bridge (Node.js) → JSON message
           ↓
           _extract_text():
             ✓ conversation
             ✓ extendedTextMessage.text
             ✓ imageMessage.caption    ← только текст!
             ✓ videoMessage.caption    ← только текст!
             ✗ audioMessage           ← вообще не обрабатывается!
           
           MessageRequest(query="только текст", runtime_ctx={})
           ↓
           MessageProcessor.process()
           ↓
           TemplateRuntime.execute()
```

### MAX USERBOT
```
Входящее → MAX WebSocket → JSON event
           ↓
           _process_event():
             ✓ message.text
             ✗ attachments     ← вообще не обрабатывается!
           
           MessageRequest(query="только текст")
```

---

## 📁 Структура кода мультимодальности

```
backend/app/
├── channels/
│   ├── userbot_manager.py           ← Telegram photo + voice ✅
│   ├── whatsapp_userbot_manager.py  ← WhatsApp text only ❌
│   ├── max_userbot_manager.py       ← MAX text only ❌
│   ├── message_processor.py         ← MessageRequest dataclass
│   └── base.py
├── router_agents/
│   ├── router.py                    ← HTTP `/internal/process` endpoint
│   │                                   (обработка voice_base64, image_base64)
│   └── schemas.py                   ← InternalProcessMessageRequest schema
├── services/
│   ├── voice_transcription.py       ← Whisper STT logic
│   ├── ai_authoring.py              ← generate_answer_with_context() ← PROBLEM
│   └── template_runtime.py          ← TemplateRuntime.execute()
├── config.py                         ← VOICE_STT_BACKEND, IMAGE_MAX_BYTES, etc.
└── alembic/models.py                ← База данных
```

---

## 🎯 Рекомендации

### 1. Срочные исправления (Критично)

#### 1.1 Исправить Vision для QA шаблонов
```python
# backend/app/services/ai_authoring.py

async def generate_answer_with_context(
    question: str, 
    context_list: list, 
    system_prompt: str,
    runtime_context: dict | None = None  # ← Добавить
) -> str:
    """Generate answer with optional vision support."""
    
    runtime_context = runtime_context or {}
    vision_image_url = runtime_context.get("vision_image_data_url")
    
    # Построить content array для OpenAI-style API
    user_content = [{"type": "text", "text": user_prompt}]
    if vision_image_url:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": vision_image_url}
        })
    
    messages = [
        {"role": "system", "content": full_system_prompt},
        {"role": "user", "content": user_content},  # ← Array вместо string!
    ]
    
    response = await ai_client.chat.completions.create(
        model=runtime_context.get("vision_chat_model", "deepseek-chat"),
        messages=messages,
        temperature=0.3,
    )
```

#### 1.2 Переделать TemplateRuntime для передачи runtime_context
```python
# backend/app/services/template_runtime.py

async def _execute_qa_like(
    self,
    *,
    prompt: str,
    user_message: str,
    knowledge_scope_id: int,
    runtime_context: dict | None = None,  # ← Добавить
) -> TemplateExecutionResult:
    context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
    context_list = context if isinstance(context, list) else []
    
    answer = await generate_answer_with_context(
        user_message, 
        context_list, 
        prompt,
        runtime_context=runtime_context  # ← Передать!
    )
```

#### 1.3 Добавить медиа-обработку для WhatsApp
```python
# backend/app/channels/whatsapp_userbot_manager.py

async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    text = _extract_text(incoming)
    runtime_ctx = {}
    
    # Проверить наличие изображения
    img_msg = (incoming.get("message") or {}).get("imageMessage") or {}
    if img_msg:
        try:
            # Скачать изображение из wa_bridge
            image_data = await _bridge_post(
                "media/download",
                {
                    "connection_id": cfg["connection_id"],
                    "message_id": incoming.get("id"),
                    "media_type": "image"
                }
            )
            if image_data:
                base64_img = image_data.get("base64")
                runtime_ctx["vision_image_data_url"] = (
                    f"data:image/jpeg;base64,{base64_img}"
                )
                text = text or "[Фото без подписи]"
        except Exception:
            logger.exception("Failed to download WhatsApp image")
    
    request = MessageRequest(
        # ... existing fields ...
        runtime_context=runtime_ctx if runtime_ctx else None
    )
```

### 2. Среднесрочные улучшения (Важно)

#### 2.1 Добавить поддержку медиа в MAX
- Изучить MAX API для определения типов медиа-сообщений
- Реализовать загрузку вложений
- Протестировать с реальными сообщениями

#### 2.2 Создать MediaContext dataclass
```python
# backend/app/models/media.py

@dataclass
class MediaContext:
    image_data_url: str | None = None
    audio_transcript: str | None = None
    vision_model: str = "deepseek-chat"
    
    def to_runtime_context(self) -> dict:
        ctx = {}
        if self.image_data_url:
            ctx["vision_image_data_url"] = self.image_data_url
        if self.vision_model != "deepseek-chat":
            ctx["vision_chat_model"] = self.vision_model
        return ctx
```

#### 2.3 Добавить метрики для медиа
```python
# AgentAnalyticsMessage расширить:
- has_image: bool
- has_audio: bool
- image_size: int | None
- audio_duration_seconds: float | None
- transcription_latency_ms: int | None
```

### 3. Долгосрочная архитектура (Рекомендация)

#### 3.1 MediaPipeline абстракция
```python
class MediaProcessor(ABC):
    @abstractmethod
    async def process_image(self, data: bytes, mime: str) -> str:
        """Return data URL"""
        pass
    
    @abstractmethod
    async def process_audio(self, data: bytes, mime: str) -> str:
        """Return transcript"""
        pass

class TelegramMediaProcessor(MediaProcessor):
    # Telethon-specific implementation

class WhatsAppMediaProcessor(MediaProcessor):
    # wa_bridge-specific implementation
```

#### 3.2 MediaCache с Redis
```python
async def get_media_cache_key(file_hash: str, channel: str) -> str:
    """Get cached vision_image_data_url"""
    key = f"media:{channel}:{file_hash}"
    return redis.get(key)
```

---

## 📊 Таблица совместимости

| Функция | Telegram Userbot | WhatsApp Userbot | MAX Userbot | HTTP API |
|---------|-----------------|-----------------|------------|----------|
| 📷 Фото | ✅ Полная | ❌ Только caption | ❌ Нет | ✅ Base64 |
| 🎙️ Голос | ✅ Whisper STT | ❌ Нет | ❌ Нет | ✅ Base64 |
| 📹 Видео | ❌ Нет | ❌ Только caption | ❌ Нет | ❌ Нет |
| 📄 Документы | ❌ Нет | ❌ Нет | ❌ Нет | ❌ Нет |
| Vision в LLM | ❌ Не работает | ❌ Нет | ❌ Нет | ✅ Готово |

---

## 🔧 Тестирование

### Что протестировать
1. Telegram: отправить фото с caption и без
2. Telegram: отправить голос с текстом и без
3. WhatsApp: отправить фото (проверить, что caption берётся)
4. MAX: отправить текстовое сообщение (base case)
5. HTTP API: POST `/internal/process` с `image_base64` + `voice_base64`
6. Проверить, что LLM видит изображение (добавить debug logging)

---

## 📝 Выводы

### Текущее состояние
- ✅ Каналы корректно загружают медиа в память
- ✅ Голос транскрибируется в текст
- ✅ Изображения кодируются в base64
- ❌ **Изображения не передаются в LLM для QA шаблонов**
- ❌ **WhatsApp и MAX имеют серьёзные ограничения**

### Главная проблема
**`runtime_context["vision_image_data_url"]` создаётся, но никогда не используется.**

Это происходит, потому что:
1. `template_runtime.execute()` получает `runtime_context`
2. Но он не передаётся в `_execute_qa_like()`
3. `generate_answer_with_context()` не знает про `vision_image_data_url`
4. LLM получает только текст, не видя картинку

### Приоритет исправлений
1. 🔴 **КРИТИЧНО:** Исправить Vision для QA шаблонов (2-3 часа)
2. 🔴 **КРИТИЧНО:** Добавить медиа в WhatsApp (4-6 часов)
3. 🟡 **ВАЖНО:** Добавить медиа в MAX (4-6 часов)
4. 🟡 **ВАЖНО:** Добавить error handling для STT failures (1-2 часа)
5. 🟢 **РЕКОМЕНДАЦИЯ:** Архитектурные улучшения (8-12 часов)

---

**Дата обновления:** 2026-05-15  
**Версия документа:** 1.0
