# 🔧 Быстрые Исправления - Готовый Код

## Исправление №1: WhatsApp - Добавить runtime_context

**Файл:** `backend/app/channels/whatsapp_userbot_manager.py`  
**Строки для изменения:** 130-180

### ШАГ 1: Добавить импорты в начало файла

```python
import base64
from io import BytesIO
from ..config import settings
from ..services.voice_transcription import transcribe_voice_bytes, is_voice_stt_configured
```

### ШАГ 2: Модифицировать функцию `_process_incoming()`

**НАЙТИ:**
```python
async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return

    # Reply only in direct messages, never in groups/channels/broadcast chats.
    if not _is_private_whatsapp_jid(remote_jid):
        return

    if str(incoming.get("from_me") or "").lower() == "true":
        return

    text = _extract_text(incoming)
    if not text:
        return
```

**ЗАМЕНИТЬ НА:**
```python
async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return

    # Reply only in direct messages, never in groups/channels/broadcast chats.
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
    
    # ✅ NEW: Обработка изображений (получаем подпись)
    image_data = msg.get("imageMessage") or {}
    if image_data and not text:
        # Если есть фото но нет текста, используем подпись или заглушку
        text = image_data.get("caption") or "[Фото без подписи]"
    
    # ✅ NEW: Обработка видео (получаем подпись)
    video_data = msg.get("videoMessage") or {}
    if video_data and not text:
        text = video_data.get("caption") or "[Видео без подписи]"
    
    # Если совсем нет контента, игнорировать
    if not text:
        return
```

### ШАГ 3: Добавить runtime_context в MessageRequest

**НАЙТИ:**
```python
    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
    )
```

**ЗАМЕНИТЬ НА:**
```python
    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
        runtime_context=runtime_ctx,  # ✅ ДОБАВИТЬ!
    )
```

---

## Исправление №2: MAX - Добавить runtime_context

**Файл:** `backend/app/channels/max_userbot_manager.py`  
**Строки для изменения:** 228-258

### ШАГ 1: Модифицировать функцию `_handle_incoming_message()`

**НАЙТИ:**
```python
async def _handle_incoming_message(client: MaxWsClient, payload: dict[str, Any], cfg: dict[str, Any]) -> None:
    message = payload.get("message") or {}
    sender = str(message.get("sender") or "").strip()
    chat_id = str(payload.get("chatId") or "").strip()
    if not sender or not chat_id:
        return
    chat_type = str(payload.get("chatType") or "").strip().lower()
    if chat_type and chat_type not in {"private", "direct", "dialog"}:
        return
    my_id = str((((client.me or {}).get("profile") or {}).get("contact") or {}).get("id") or "").strip()
    if my_id and sender == my_id:
        return
    status = str(message.get("status") or "").strip().upper()
    if status == "REMOVED":
        return
    text = str(message.get("text") or "").strip()
    if not text:
        return
```

**ЗАМЕНИТЬ НА:**
```python
async def _handle_incoming_message(client: MaxWsClient, payload: dict[str, Any], cfg: dict[str, Any]) -> None:
    message = payload.get("message") or {}
    sender = str(message.get("sender") or "").strip()
    chat_id = str(payload.get("chatId") or "").strip()
    if not sender or not chat_id:
        return
    chat_type = str(payload.get("chatType") or "").strip().lower()
    if chat_type and chat_type not in {"private", "direct", "dialog"}:
        return
    my_id = str((((client.me or {}).get("profile") or {}).get("contact") or {}).get("id") or "").strip()
    if my_id and sender == my_id:
        return
    status = str(message.get("status") or "").strip().upper()
    if status == "REMOVED":
        return
    
    # ✅ NEW: Инициализируем runtime_context
    runtime_ctx: dict[str, Any] = {
        "lead_initiated_private_dialog": False,
        "is_private_chat": True,
    }
    
    text = str(message.get("text") or "").strip()
    
    # ✅ NEW: Если нет текста, поддержим медиа-сообщения (если MAX API их предоставляет)
    if not text:
        # MAX WebSocket API может не предоставить медиа-данные
        # Это зависит от версии API и конфигурации
        # На данный момент MAX не полностью поддерживает медиа
        logger.debug("max_userbot: Ignoring non-text message from %s (MAX API doesn't provide media data)", sender)
        return
```

### ШАГ 2: Добавить runtime_context в MessageRequest

**НАЙТИ:**
```python
    sender_profile = await asyncio.to_thread(client.get_user, sender)
    sender_name = _extract_sender_name(sender_profile)
    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text,
        user_external_id=chat_id,
        channel=Channel.MAX_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=sender_name,
    )
```

**ЗАМЕНИТЬ НА:**
```python
    sender_profile = await asyncio.to_thread(client.get_user, sender)
    sender_name = _extract_sender_name(sender_profile)
    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text,
        user_external_id=chat_id,
        channel=Channel.MAX_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=sender_name,
        runtime_context=runtime_ctx,  # ✅ ДОБАВИТЬ!
    )
```

---

## Исправление №3: Проверка инициализации runtime_ctx в других каналах

### Telegram Userbot (для проверки - уже правильно)

**Файл:** `backend/app/channels/userbot_manager.py`  
**Строки:** 186-269

Убедитесь, что у вас есть:

```python
runtime_ctx: dict[str, Any] = {
    "lead_initiated_private_dialog": template_type == "sales_manager",
    "is_private_chat": True,
}
# ... обработка медиа ...
request = MessageRequest(
    # ...
    runtime_context=runtime_ctx,  # ✅ Должно быть!
)
```

---

## 🧪 Валидационный тест

После применения исправлений, протестируйте это:

```python
# Тест 1: Проверить, что runtime_context передается
from backend.app.channels.whatsapp_userbot_manager import _process_incoming

# Симулировать входящее сообщение
incoming = {
    "remote_jid": "1234567890@s.whatsapp.net",
    "from_me": "false",
    "push_name": "Test User",
    "message": {
        "conversation": "Привет агент",
        "imageMessage": {"caption": "Описание фото"},
    }
}

cfg = {
    "bot_id": "1",
    "connection_id": "1",
    "system_prompt": "Ты полезный ассистент",
}

# Убедитесь, что runtime_context не пуст
```

---

## 📊 Результаты после исправлений

| Функция | Telegram | WhatsApp | MAX |
|---------|----------|----------|-----|
| runtime_context передается | ✅ ДА | ✅ БУДЕТ | ✅ БУДЕТ |
| Фото обрабатывается | ✅ ДА | ⚠️ Частично | ❌ НЕТ |
| Голос распознается | ✅ ДА | ❌ НЕТ | ❌ НЕТ |
| Агент видит фото | ✅ ДА | ⚠️ Если есть подпись | ❌ НЕТ |

**Примечание:** Полная поддержка медиа в WhatsApp требует расширенного API wa-bridge для загрузки медиа-файлов. Текущие исправления добавляют runtime_context, который позволит агентам видеть фото С подписью.

---

## 💡 Дополнительно: Как добавить полную загрузку медиа в WhatsApp

Это требует расширения wa-bridge API. Примерный флоу:

1. **Получить URL медиа из wa-bridge:**
   ```python
   media_key = image_data.get("media_key")
   # Запросить wa-bridge предоставить URL для загрузки
   download_response = await _bridge_post("session/download_media", {
       "connection_id": connection_id,
       "media_key": media_key,
   })
   media_url = download_response.get("url")
   ```

2. **Загрузить медиа:**
   ```python
   async with httpx.AsyncClient() as client:
       response = await client.get(media_url)
       raw_image = response.content
   ```

3. **Кодировать и добавить в runtime_context:**
   ```python
   runtime_ctx["vision_image_data_url"] = (
       f"data:image/jpeg;base64,{base64.b64encode(raw_image).decode('ascii')}"
   )
   ```

Это требует работы с wa-bridge разработчиком.
