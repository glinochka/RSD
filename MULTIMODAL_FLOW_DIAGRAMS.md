# 🎯 Multimodal Data Flow - Visual Diagrams

## 1. TELEGRAM USERBOT - FULL FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ User sends Photo + Caption in Telegram                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Telethon event.message.photo detected                           │
│ ✅ event.message.photo = True                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend: userbot_manager.py:194-202                             │
│                                                                 │
│  buf = BytesIO()                                                │
│  await event.message.download_media(buf)                        │
│  raw = buf.getvalue()  # Photo bytes                            │
│  mime = "image/jpeg"                                            │
│  base64_encoded = base64.standard_b64encode(raw)                │
│  runtime_ctx["vision_image_data_url"] =                         │
│    f"data:image/jpeg;base64,{base64_encoded}"                   │
│  query = caption_or_text or "[Фото без подписи]"               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ MessageRequest created with:                                    │
│  - query: "Caption text" or "[Фото без подписи]"               │
│  - runtime_context: {                                           │
│      "vision_image_data_url":                                   │
│        "data:image/jpeg;base64,/9j/4AAQSkZ..."                  │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ MessageProcessor.process()                                      │
│ - Validates subscription                                        │
│ - Checks frozen user                                            │
│ - Merges runtime_ctx                                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ TemplateRuntime.execute(                                        │
│   template_type="qa",                                           │
│   user_message="Caption text",                                  │
│   runtime_context={                                             │
│     "vision_image_data_url": "data:image/jpeg;base64,..."      │
│   }                                                              │
│ )                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
                    ⚠️ PROBLEM HERE ⚠️
┌─────────────────────────────────────────────────────────────────┐
│ _execute_qa_like() called WITHOUT runtime_context               │
│                                                                 │
│ async def _execute_qa_like(                                     │
│     prompt: str,                                                │
│     user_message: str,                                          │
│     knowledge_scope_id: int,                                    │
│     # ❌ NO runtime_context parameter!                          │
│ ):                                                              │
│     context = search_knowledge_base(user_message)               │
│     answer = generate_answer_with_context(                      │
│         user_message,                                           │
│         context_list,                                           │
│         prompt                                                  │
│         # ❌ NO vision_image_data_url passed                    │
│     )                                                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ generate_answer_with_context()                                  │
│                                                                 │
│ messages = [                                                    │
│     {"role": "system", "content": system_prompt},               │
│     {"role": "user", "content": user_prompt}  # ← STRING ONLY   │
│ ]                                                               │
│                                                                 │
│ ❌ LLM receives ONLY TEXT, image is LOST!                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ DeepSeek API Response                                           │
│ Model never sees the image, can only answer based on caption    │
└─────────────────────────────────────────────────────────────────┘
```

## 2. TELEGRAM USERBOT - VOICE FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ User sends Voice Message with optional Caption                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Telethon: getattr(event.message, "voice", None) = True          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Backend: userbot_manager.py:206-210                             │
│                                                                 │
│  buf = BytesIO()                                                │
│  await event.message.download_media(buf)                        │
│  voice_bytes = buf.getvalue()  # OGG audio                      │
│  if len(voice_bytes) > 10MB: reject                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Check: is_voice_stt_configured()                                │
│                                                                 │
│ if VOICE_STT_BACKEND == "faster_whisper":                       │
│   ✅ Use local Whisper model                                    │
│ elif OPENAI_API_KEY set:                                        │
│   ✅ Use OpenAI Whisper API                                     │
│ else:                                                            │
│   ❌ Tell user to enable STT                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ transcribe_voice_bytes(voice_bytes, mime="audio/ogg")           │
│                                                                 │
│ if FASTER_WHISPER:                                              │
│   - Load model from FASTER_WHISPER_MODEL config                 │
│   - Run on FASTER_WHISPER_DEVICE (cuda/cpu)                     │
│   - Timeout: VOICE_TRANSCRIPTION_TIMEOUT_SECONDS (120s)         │
│   - Result: "Текст, что пользователь сказал"                    │
│                                                                 │
│ elif OPENAI:                                                    │
│   - Call OpenAI Whisper API                                     │
│   - Result: transcript                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ userbot_manager.py:231-240                                      │
│                                                                 │
│ if transcript:                                                  │
│   query = f"{caption_or_text}\n\nТекст голосового сообщения:    │
│     {transcript}".strip()                                       │
│ else:                                                            │
│   query = "Пользователь прислал голосовое сообщение,            │
│     но текст распознать не удалось."                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ MessageRequest created with:                                    │
│  - query: Contains transcript text (NO AUDIO BYTES)             │
│  - runtime_context: {} (empty for voice)                        │
│                                                                 │
│ ✅ Voice becomes TEXT, LLM processes successfully               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ TemplateRuntime.execute()                                       │
│ → LLM gets transcript text                                      │
│ → No special handling needed                                    │
│ → Works for all template types ✅                               │
└─────────────────────────────────────────────────────────────────┘
```

## 3. WHATSAPP USERBOT - LIMITED FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ wa_bridge receives WhatsApp message JSON                         │
│ (Message comes from Baileys/WhatsApp)                           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ whatsapp_userbot_manager.py:101-110                             │
│ _extract_text(message):                                         │
│                                                                 │
│  msg = message.get("message") or {}                             │
│  text = (                                                       │
│    msg.get("conversation")                   # Plain text ✅    │
│    or msg.get("extendedTextMessage")?.text   # Text message ✅  │
│    or msg.get("imageMessage")?.caption       # ⚠️ Caption only   │
│    or msg.get("videoMessage")?.caption       # ⚠️ Caption only   │
│    or ""                                                        │
│  )                                                              │
│  return text                                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ⚠️ IMAGE/VIDEO DATA IS IGNORED ⚠️
┌─────────────────────────────────────────────────────────────────┐
│ What's MISSING:                                                 │
│  - imageMessage.imageData (binary)            ❌ NOT extracted  │
│  - imageMessage.mediaKey (for decryption)     ❌ NOT extracted  │
│  - videoMessage.videoData (binary)            ❌ NOT extracted  │
│  - audioMessage (exists in WhatsApp)          ❌ NOT extracted  │
│                                                                 │
│ What's used:                                                    │
│  - Only text captions                         ⚠️ Partial        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ _process_incoming():                                            │
│                                                                 │
│ request = MessageRequest(                                       │
│   query=text,                    # Only caption "Фото продукта" │
│   # ❌ runtime_context not created for media!                   │
│   # ❌ Image binary data never downloaded                       │
│ )                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ MessageProcessor + TemplateRuntime                              │
│ LLM sees only: "Фото продукта" (photo caption)                 │
│ LLM CANNOT see: actual photo ❌                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 4. MAX USERBOT - TEXT ONLY

```
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket message from MAX                                      │
│ {                                                               │
│   "opcode": 128,                                                │
│   "payload": {                                                  │
│     "chatId": "...",                                            │
│     "message": {                                                │
│       "text": "Hello",                                          │
│       "status": "DELIVERED"                                     │
│     }                                                           │
│   }                                                             │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ max_userbot_manager.py:_process_event()                         │
│                                                                 │
│ text = str(message.get("text") or "").strip()                   │
│ if not text: return  # ❌ No attachments check                   │
│                                                                 │
│ MessageRequest(                                                 │
│   query=text,                                                   │
│   # ❌ No runtime_context for attachments                       │
│ )                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ LLM sees only text ✅ (if present)                              │
│ LLM CANNOT see: images, files, etc. ❌                          │
└─────────────────────────────────────────────────────────────────┘
```

## 5. HTTP API - FULL SUPPORT

```
┌─────────────────────────────────────────────────────────────────┐
│ External API Client                                             │
│ POST /api/agents/internal/process                               │
│ {                                                               │
│   "bot_id": 123,                                                │
│   "query": "What about this?",                                  │
│   "user_external_id": "user_456",                               │
│   "channel": "telegram_userbot",                                │
│   "image_base64": "/9j/4AAQSkZJRgABA...",  ← Image in Base64   │
│   "image_mime_type": "image/jpeg",                              │
│   "voice_base64": "ID3v23000..."          ← Audio in Base64     │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ router.py:2968-3011 - Process voice                             │
│                                                                 │
│ if payload.voice_base64:                                        │
│   audio_bytes = base64.b64decode(payload.voice_base64)          │
│   if len(audio_bytes) > 10MB: reject                            │
│   transcript = transcribe_voice_bytes(                          │
│     audio_bytes,                                                │
│     mime="audio/ogg"                                            │
│   )                                                             │
│   query_text = f"{query_text}\\n\\nТекст голосового сообщения:    │
│     {transcript}"                                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ router.py:3002-3011 - Process image                             │
│                                                                 │
│ if payload.image_base64:                                        │
│   mime = payload.image_mime_type or "image/jpeg"                │
│   img_bytes = base64.b64decode(payload.image_base64)            │
│   if len(img_bytes) > 10MB: reject                              │
│   runtime_ctx["vision_image_data_url"] =                        │
│     f"data:{mime};base64,{payload.image_base64}"                │
│   if not query_text:                                            │
│     query_text = "[Изображение без текстовой подписи]"          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ RuntimeMessageRequest with BOTH:                                │
│  - query_text: Contains voice transcript                        │
│  - runtime_context: {                                           │
│      "vision_image_data_url": "data:image/jpeg;base64,..."      │
│    }                                                            │
│                                                                 │
│ ✅ Can be used for all template types                           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ BUT: Same problem as Telegram!                                  │
│                                                                 │
│ _execute_qa_like() does NOT receive runtime_context ❌           │
│ generate_answer_with_context() does NOT use vision_image_url ❌ │
│                                                                 │
│ ✅ HTTP API prepares data correctly                             │
│ ❌ Template runtime doesn't use it                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Issues Summary

### ❌ Vision Images NOT Transmitted to LLM

**Problem Flow:**
```
Telegram:  Photo → download → Base64 → vision_image_data_url ✅
             ↓
        MessageProcessor.process()  ✅
             ↓
        runtime_context passed ✅
             ↓
        _execute_qa_like() called WITHOUT runtime_context ❌
             ↓
        LLM receives ONLY text ❌
```

### ⚠️ WhatsApp Limited Support

```
WhatsApp Message:
  - Plain text     ✅ Works
  - Text caption   ✅ Works (extracted)
  - Photo binary   ❌ NOT downloaded
  - Audio binary   ❌ NOT extracted
  - Voice caption  ❌ Cannot get (no audio extraction)
```

### ❌ MAX No Media Support

```
MAX Message:
  - Text only      ✅ Works
  - Attachments    ❌ NOT checked
  - Media          ❌ NOT parsed
```

---

## The Fix Needed

```
BEFORE (Broken):
┌──────────────────┐
│ _execute_qa_like │
│                  │
│ async def(       │
│   prompt,        │
│   user_message,  │
│   scope_id       ← ❌ NO runtime_context
│ )                │
└──────────────────┘

AFTER (Fixed):
┌──────────────────┐
│ _execute_qa_like │
│                  │
│ async def(       │
│   prompt,        │
│   user_message,  │
│   scope_id,      │
│   runtime_ctx ← ✅ YES!
│ )                │
│   # Pass to      │
│   # generate_ans │
│   # with_context │
└──────────────────┘
        ↓
┌──────────────────────────┐
│generate_answer_with_ctx  │
│                          │
│ messages = [{            │
│   "role": "user",        │
│   "content": [           │
│     {"type": "text",     │
│      "text": msg},       │
│     {"type": "image_url",│
│      "image_url": {      │
│        "url": vision_url │
│      }}                  │
│   ]                      │
│ }]                       │
│                          │
│ ✅ LLM sees BOTH text    │
│    and image!            │
└──────────────────────────┘
```
