# 🔍 Комплексный Анализ Мультимодальности - Проблемы и Решения

**Дата:** 2026-05-15  
**Статус:** ⚠️ **ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ДЕФЕКТЫ**

---

## 📊 ИТОГОВАЯ ТАБЛИЦА ПОДДЕРЖКИ

| Функция | Telegram ✅ | WhatsApp ❌ | MAX ❌ | HTTP API ✅ |
|---------|----------|----------|-------|----------|
| **Изображения** | Работает | Не поддерживается | Не поддерживается | Работает |
| **Голосовые сообщения** | Работает | Не поддерживается | Не поддерживается | Работает |
| **runtime_context** | Передается | НЕ ПЕРЕДАЕТСЯ | НЕ ПЕРЕДАЕТСЯ | Передается |
| **Vision в LLM** | ✅ Видит фото | ❌ Фото не загружается | ❌ Не загружается | ✅ Видит фото |

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### Проблема №1: WhatsApp - Полностью отсутствует обработка медиа

**Файл:** [backend/app/channels/whatsapp_userbot_manager.py](backend/app/channels/whatsapp_userbot_manager.py)

**Строки 100-180:**

```python
def _extract_text(message: dict[str, Any]) -> str:
    msg = message.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")      # ← Только подпись!
        or (msg.get("videoMessage") or {}).get("caption")      # ← Только подпись!
        or ""
    )
    return str(text).strip()

async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    # ...
    text = _extract_text(incoming)
    if not text:                                               # ← КРИТИЧЕСКИЙ БАГ!
        return                                                 # ← Игнорирует фото без подписи
    # ...
    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        # ...
        # ← НЕ ПЕРЕДАЕТ runtime_context!
    )
```

**Проблемы:**
1. ❌ Извлекает только текстовую подпись из `imageMessage`, игнорируя само изображение
2. ❌ Если нет подписи → сообщение игнорируется (строка 147 `if not text: return`)
3. ❌ Нет загрузки медиа-данных из wa-bridge
4. ❌ `runtime_context` не передается в MessageRequest

**Последствия:**
- Фото БЕЗ подписи: полностью игнорируются
- Фото С подписью: передается только подпись, фото не видно агентом
- Голосовые сообщения: не поддерживаются вообще

---

### Проблема №2: MAX - Нет поддержки медиа

**Файл:** [backend/app/channels/max_userbot_manager.py](backend/app/channels/max_userbot_manager.py)

**Строки 228-258:**

```python
async def _handle_incoming_message(client: MaxWsClient, payload: dict[str, Any], cfg: dict[str, Any]) -> None:
    message = payload.get("message") or {}
    text = str(message.get("text") or "").strip()              # ← Только текст!
    
    if not text:
        return                                                 # ← Игнорирует любое медиа
    
    # ...
    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text,
        # ...
        # ← НЕ ПЕРЕДАЕТ runtime_context!
    )
```

**Проблемы:**
1. ❌ Поддерживает только `message.get("text")`, игнорирует медиа
2. ❌ Нет проверки на наличие `attachments`, `audio`, `images` в payload
3. ❌ `runtime_context` не передается
4. ❌ MAX WebSocket API не предоставляет медиа-данные в реальном времени

**Последствия:**
- Изображения: полностью игнорируются
- Голосовые сообщения: полностью игнорируются
- Видео: полностью игнорируются

---

### Проблема №3: runtime_context НЕ передается в WhatsApp и MAX

**WhatsApp** [backend/app/channels/whatsapp_userbot_manager.py](backend/app/channels/whatsapp_userbot_manager.py#L169):
```python
# ❌ НЕПРАВИЛЬНО - runtime_context отсутствует
request = MessageRequest(
    bot_id=bot_id,
    query=text,
    user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
    channel=Channel.WHATSAPP_USERBOT,
    system_prompt=cfg.get("system_prompt") or "",
    welcome_message=cfg.get("welcome_message"),
    user_display_name=str(incoming.get("push_name") or "").strip() or None,
)  # ← НЕТ runtime_context параметра!
```

**MAX** [backend/app/channels/max_userbot_manager.py](backend/app/channels/max_userbot_manager.py#L248):
```python
# ❌ НЕПРАВИЛЬНО - runtime_context отсутствует
request = MessageRequest(
    bot_id=int(cfg["bot_id"]),
    query=text,
    user_external_id=chat_id,
    channel=Channel.MAX_USERBOT,
    system_prompt=cfg.get("system_prompt") or "",
    welcome_message=cfg.get("welcome_message"),
    user_display_name=sender_name,
)  # ← НЕТ runtime_context параметра!
```

**Telegram (для сравнения)** [backend/app/channels/userbot_manager.py](backend/app/channels/userbot_manager.py#L269):
```python
# ✅ ПРАВИЛЬНО - runtime_context ПЕРЕДАЕТСЯ
request = MessageRequest(
    bot_id=bot_id,
    query=query,
    user_external_id=user_external_id,
    channel=Channel.TELEGRAM_USERBOT,
    system_prompt=system_prompt,
    welcome_message=welcome_message,
    user_display_name=user_display_name,
    telegram_peer_access_hash=peer_access_hash,
    runtime_context=runtime_ctx,  # ← ПЕРЕДАЕТСЯ!
)
```

**Последствия:**
- Даже если бы медиа обрабатывались, `vision_image_data_url` не передался бы в агента
- `runtime_context` по дизайну передает все мультимодальные данные
- Без `runtime_context` в MessageRequest → параметр всегда `None` → нет видения фото в LLM

---

## 🎯 ИСПРАВЛЕНИЯ

### Исправление №1: WhatsApp - Добавить обработку медиа

**Действие:** Модифицировать `_process_incoming()` в [backend/app/channels/whatsapp_userbot_manager.py](backend/app/channels/whatsapp_userbot_manager.py)

```python
async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return

    if not _is_private_whatsapp_jid(remote_jid):
        return

    if str(incoming.get("from_me") or "").lower() == "true":
        return

    # ✅ NEW: Инициализируем runtime_context
    runtime_ctx: dict[str, Any] = {
        "lead_initiated_private_dialog": False,
        "is_private_chat": True,
    }
    
    text = _extract_text(incoming)
    msg = incoming.get("message") or {}
    
    # ✅ NEW: Обработка изображений
    image_data = msg.get("imageMessage", {})
    if image_data:
        # Получить данные изображения из wa-bridge API
        download_url = image_data.get("download_url") or image_data.get("url")
        if download_url:
            try:
                # Загрузить изображение
                raw_image = await _bridge_download_media(download_url)
                if raw_image and len(raw_image) <= int(settings.IMAGE_MAX_BYTES):
                    mime = image_data.get("mimetype", "image/jpeg")
                    runtime_ctx["vision_image_data_url"] = (
                        f"data:{mime};base64,{base64.standard_b64encode(raw_image).decode('ascii')}"
                    )
                    # Если нет текстовой подписи, используем заглушку
                    if not text:
                        text = image_data.get("caption", "[Фото без подписи]")
            except Exception as e:
                logger.warning("Failed to download WhatsApp image: %s", e)
    
    # ✅ NEW: Обработка голосовых сообщений
    audio_data = msg.get("audioMessage", {})
    if audio_data and not text:
        download_url = audio_data.get("download_url") or audio_data.get("url")
        if download_url and is_voice_stt_configured():
            try:
                voice_bytes = await _bridge_download_media(download_url)
                if voice_bytes:
                    transcript = await transcribe_voice_bytes(voice_bytes, mime_type="audio/ogg")
                    if transcript:
                        text = f"Текст голосового сообщения: {transcript}"
            except Exception as e:
                logger.warning("Failed to transcribe WhatsApp audio: %s", e)
    
    # Если вообще нет контента, игнорировать
    if not text and "vision_image_data_url" not in runtime_ctx:
        return
    
    # ...rest of the code...
    
    # ✅ ВАЖНО: Передать runtime_context!
    request = MessageRequest(
        bot_id=bot_id,
        query=text or "[Медиа без подписи]",
        user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
        runtime_context=runtime_ctx,  # ← ДОБАВИТЬ!
    )
```

**Требуемые вспомогательные функции:**

```python
async def _bridge_download_media(url: str, timeout_s: float = 30.0) -> bytes | None:
    """Загрузить медиа из wa-bridge."""
    try:
        timeout = httpx.Timeout(timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=_bridge_headers())
            if response.is_success:
                return response.content
    except Exception as e:
        logger.warning("Failed to download media from %s: %s", url, e)
    return None
```

---

### Исправление №2: MAX - Добавить поддержку медиа (опционально)

**Проблема:** MAX WebSocket API не предоставляет медиа-данные в реальном времени. Это требует дополнительного API запроса к MAX серверам.

**Действие:** Модифицировать `_handle_incoming_message()` в [backend/app/channels/max_userbot_manager.py](backend/app/channels/max_userbot_manager.py)

```python
async def _handle_incoming_message(client: MaxWsClient, payload: dict[str, Any], cfg: dict[str, Any]) -> None:
    message = payload.get("message") or {}
    text = str(message.get("text") or "").strip()
    
    # ✅ NEW: Инициализируем runtime_context
    runtime_ctx: dict[str, Any] = {
        "lead_initiated_private_dialog": False,
        "is_private_chat": True,
    }
    
    # ✅ NEW: Обработка вложений (если MAX API их предоставляет)
    attachments = message.get("attachments", [])
    for attachment in attachments:
        attachment_type = str(attachment.get("type") or "").lower()
        
        if attachment_type == "image":
            image_url = attachment.get("url") or attachment.get("preview")
            if image_url:
                try:
                    raw_image = await _download_max_media(image_url, client)
                    if raw_image and len(raw_image) <= int(settings.IMAGE_MAX_BYTES):
                        mime = "image/jpeg"
                        runtime_ctx["vision_image_data_url"] = (
                            f"data:{mime};base64,{base64.standard_b64encode(raw_image).decode('ascii')}"
                        )
                        if not text:
                            text = "[Фото без подписи]"
                except Exception as e:
                    logger.warning("Failed to download MAX image: %s", e)
        
        elif attachment_type == "audio":
            audio_url = attachment.get("url")
            if audio_url and is_voice_stt_configured() and not text:
                try:
                    voice_bytes = await _download_max_media(audio_url, client)
                    if voice_bytes:
                        transcript = await transcribe_voice_bytes(voice_bytes, mime_type="audio/ogg")
                        if transcript:
                            text = f"Текст голосового сообщения: {transcript}"
                except Exception as e:
                    logger.warning("Failed to transcribe MAX audio: %s", e)
    
    # Если вообще нет контента, игнорировать
    if not text and "vision_image_data_url" not in runtime_ctx:
        return
    
    # ...rest of code...
    
    # ✅ ВАЖНО: Передать runtime_context!
    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text or "[Медиа без подписи]",
        user_external_id=chat_id,
        channel=Channel.MAX_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=sender_name,
        runtime_context=runtime_ctx,  # ← ДОБАВИТЬ!
    )
```

---

### Исправление №3: Все каналы - Сертификация runtime_context

**Проверка:** Убедиться, что `runtime_context` всегда передается в MessageRequest

**Чек-лист для каждого канала:**
- [ ] Telegram Userbot - ✅ Уже правильно
- [ ] WhatsApp Userbot - ❌ Исправить (см. выше)
- [ ] MAX Userbot - ❌ Исправить (см. выше)
- [ ] Telegram Bot (классический) - ⏳ Проверить и исправить если нужно
- [ ] HTTP API - ✅ Уже передает

---

## 📋 ПОЧЕМУ АГЕНТ НЕ ВИДИТ ИЗОБРАЖЕНИЯ

### Путь данных в системе

```
Пользователь отправляет фото
    ↓
[Канал: Telegram/WhatsApp/MAX]
    ↓
[Менеджер канала загружает медиа] ← ❌ WhatsApp и MAX НЕ загружают
    ↓
[Создается runtime_ctx с vision_image_data_url] ← ❌ WhatsApp и MAX НЕ создают
    ↓
[MessageRequest с runtime_context=runtime_ctx] ← ❌ WhatsApp и MAX НЕ передают
    ↓
[MessageProcessor.process(request)]
    ↓
[TemplateRuntimeService.execute(runtime_context=merged_runtime_ctx)]
    ↓
[_execute_qa_like(runtime_context=runtime_context)]
    ↓
[vision_raw = runtime_ctx.get("vision_image_data_url")] ← ✅ Здесь извлекается
    ↓
[generate_answer_with_context(vision_image_data_url=vision_url)]
    ↓
[LLM видит изображение в multimodal_user содержимом] ✅ Или НЕ видит ❌
```

### Причины проблемы

| Этап | Telegram | WhatsApp | MAX |
|------|----------|----------|-----|
| Загрузка медиа | ✅ Загружает | ❌ НЕ загружает | ❌ НЕ загружает |
| Создание runtime_ctx | ✅ Создает | ❌ НЕ создает | ❌ НЕ создает |
| Передача в MessageRequest | ✅ Передает | ❌ НЕ передает | ❌ НЕ передает |
| Передача в execute() | ✅ Передает | ❌ НЕ передает | ❌ НЕ передает |
| LLM видит фото | ✅ Видит | ❌ НЕ видит | ❌ НЕ видит |

---

## 🛠️ ПЛАН ИСПРАВЛЕНИЯ (ПРИОРИТЕТЫ)

### 🔴 Приоритет 1: КРИТИЧНО (2-3 часа)
- [ ] **WhatsApp**: добавить загрузку изображений и передачу runtime_context
- [ ] **MAX**: добавить загрузку изображений (если API это поддерживает) и передачу runtime_context

### 🟡 Приоритет 2: ВАЖНО (1-2 часа)
- [ ] Добавить логирование для отладки мультимодальности
- [ ] Тестирование на всех трёх каналах
- [ ] Обработка ошибок загрузки медиа

### 🟢 Приоритет 3: УЛУЧШЕНИЯ (1 час)
- [ ] Кэширование загруженных изображений (избежать повторной загрузки)
- [ ] Статистика по обработанным медиа
- [ ] Поддержка прогрессивной загрузки больших файлов

---

## 🧪 ТЕСТИРОВАНИЕ

После исправлений протестировать:

### Telegram Userbot
```bash
1. Отправить фото БЕЗ подписи
2. Отправить фото С подписью
3. Отправить голосовое сообщение
4. Отправить голосовое сообщение + текст
5. Убедиться, что агент видит фото и транскрибирует голос
```

### WhatsApp Userbot
```bash
1. Отправить фото БЕЗ подписи
2. Отправить фото С подписью
3. Отправить голосовое сообщение
4. Убедиться, что агент видит фото и голос
5. Проверить логи для ошибок загрузки медиа
```

### MAX Userbot
```bash
1. Отправить фото (если MAX API это поддерживает)
2. Отправить голосовое сообщение
3. Убедиться, что агент видит медиа
4. Если MAX не предоставляет медиа → документировать ограничение
```

---

## 📝 ЗАКЛЮЧЕНИЕ

**Основные выводы:**

1. ✅ **Telegram**: Мультимодальность реализована правильно - видит фото, распознает голос
2. ❌ **WhatsApp**: Критические дефекты
   - Нет загрузки медиа-данных
   - Нет передачи runtime_context
   - Фото без подписи игнорируются
3. ❌ **MAX**: Критические дефекты
   - Нет поддержки медиа вообще
   - Нет передачи runtime_context
   - Требуется проверить возможности MAX API

**Быстрое исправление:** Добавить инициализацию `runtime_ctx` и передачу в MessageRequest для WhatsApp и MAX (как в Telegram).

**Полное решение:** Добавить полную обработку медиа (загрузку, кодирование, обработку голоса) для всех каналов.
