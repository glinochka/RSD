# 🔧 Multimodal Processing - Implementation Details

## 1. CONFIGURATION

**File:** `backend/app/config.py`

```python
# Lines 24-40: Voice and Image Settings

# Try DeepSeek /chat/completions with OpenAI-style multimodal payloads
# (content array + image_url, including data:image/...;base64,...).
# If the gateway/model rejects vision, we fall back to a text-only mode.
DEEPSEEK_CHAT_TRY_IMAGE_MULTIMODAL: bool = True

# Speech-to-text backend: auto|faster_whisper|openai
VOICE_STT_BACKEND: Literal["auto", "faster_whisper", "openai"] = "auto"

# Faster-Whisper model (e.g., tiny|base|small|medium)
FASTER_WHISPER_MODEL: str = "base"
FASTER_WHISPER_DEVICE: Literal["auto", "cuda", "cpu"] = "auto"
FASTER_WHISPER_COMPUTE_TYPE: str = "default"

# Empty = auto-detect language; e.g. "ru" for Russian-only short voice notes.
FASTER_WHISPER_LANGUAGE: str = ""

# Size limits (bytes)
VOICE_MAX_BYTES: int = 10 * 1024 * 1024      # 10 MB
IMAGE_MAX_BYTES: int = 10 * 1024 * 1024      # 10 MB

# Transcription timeout (seconds)
VOICE_TRANSCRIPTION_TIMEOUT_SECONDS: float = 120.0
```

---

## 2. VOICE TRANSCRIPTION SERVICE

**File:** `backend/app/services/voice_transcription.py`

### Function: `is_voice_stt_configured()`
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

### Function: `transcribe_voice_bytes()`
```python
async def transcribe_voice_bytes(audio_bytes: bytes, mime_type: str) -> str:
    """
    Transcribe audio bytes to text.
    
    Args:
        audio_bytes: Audio data (WAV, OGG, MP3, M4A, etc.)
        mime_type: MIME type (e.g., "audio/ogg", "audio/mp3")
    
    Returns:
        Transcribed text, or empty string if failed
    
    Raises:
        RuntimeError: If STT not configured
        asyncio.TimeoutError: If transcription takes too long
    """
```

---

## 3. MESSAGE REQUEST STRUCTURE

**File:** `backend/app/channels/message_processor.py`

```python
@dataclass
class MessageRequest:
    """Request to process a message through template runtime."""
    
    bot_id: int                                    # Agent ID (or bot ID)
    query: str                                     # User message (text or STT result)
    user_external_id: str                          # User ID in channel
    channel: Channel                               # Channel type (telegram, whatsapp, etc)
    system_prompt: str = ""                        # Agent's system prompt
    welcome_message: str | None = None             # /start message
    process_start_with_llm: bool = False           # Process /start as normal msg
    user_display_name: str | None = None           # User's name
    telegram_peer_access_hash: int | None = None   # Telegram-specific
    skip_chat_portrait_update: bool = False        # Skip analytics
    runtime_context: dict[str, object] | None = None  # ← MULTIMODAL DATA HERE
```

### What goes in runtime_context?
```python
runtime_context = {
    "vision_image_data_url": "data:image/jpeg;base64,/9j/4AAQSkZ...",
    "vision_chat_model": "deepseek-chat",  # Optional model override
    "lead_initiated_private_dialog": False,
    "is_private_chat": True,
    # ... other context
}
```

---

## 4. TELEGRAM USERBOT - IMPLEMENTATION

**File:** `backend/app/channels/userbot_manager.py` (Lines 188-256)

### Photo Handling
```python
try:
    if event.message.photo:
        buf = BytesIO()
        await event.message.download_media(buf)
        raw = buf.getvalue()
        
        # Size validation
        if len(raw) > int(settings.IMAGE_MAX_BYTES):
            await event.respond("Изображение слишком большое. Отправьте файл поменьше.")
            return
        
        # Encode to Data URL
        mime = "image/jpeg"
        runtime_ctx["vision_image_data_url"] = (
            f"data:{mime};base64,{base64.standard_b64encode(raw).decode('ascii')}"
        )
        query = caption_or_text or "[Фото без подписи]"
```

### Voice Handling
```python
    elif getattr(event.message, "voice", None):
        buf = BytesIO()
        await event.message.download_media(buf)
        voice_bytes = buf.getvalue()
        
        # Size validation
        if len(voice_bytes) > int(settings.VOICE_MAX_BYTES):
            await event.respond("Голосовое сообщение слишком большое.")
            return
        
        if not caption_or_text:
            query = ""
```

### Voice Transcription
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
    else:
        await event.respond(
            "Голосовые сообщения недоступны: не настроено распознавание речи "
            "(установите faster-whisper или задайте OPENAI_API_KEY). Напишите, пожалуйста, текстом."
        )
        return
```

---

## 5. HTTP API - INTERNAL PROCESS ENDPOINT

**File:** `backend/app/router_agents/router.py` (Lines 2950-3035)

### Schema Definition
```python
class InternalProcessMessageRequest(BaseModel):
    """Process a message with optional media (voice/image)."""
    
    bot_id: int = Field(..., gt=0)
    query: str = Field(default="", max_length=4000)
    user_external_id: str = Field(..., min_length=1, max_length=128)
    channel: str = Field(...)
    system_prompt: Optional[str] = Field(default="")
    welcome_message: Optional[str] = Field(default=None)
    process_start_with_llm: bool = Field(default=False)
    user_display_name: Optional[str] = Field(default=None, max_length=128)
    telegram_peer_access_hash: Optional[int] = Field(default=None)
    
    # MULTIMODAL FIELDS
    voice_base64: Optional[str] = Field(
        default=None,
        max_length=15_000_000,
        description="Аудио в Base64; см. VOICE_MAX_BYTES на сервере",
    )
    voice_mime_type: Optional[str] = Field(default="audio/ogg", max_length=128)
    
    image_base64: Optional[str] = Field(
        default=None,
        max_length=15_000_000,
        description="Изображение в Base64; см. IMAGE_MAX_BYTES на сервере",
    )
    image_mime_type: Optional[str] = Field(default="image/jpeg", max_length=128)
    
    @model_validator(mode="after")
    def validate_any_content(self):
        """At least one of query/voice/image must be present."""
        q = (self.query or "").strip()
        voice = (self.voice_base64 or "").strip()
        image = (self.image_base64 or "").strip()
        if not q and not voice and not image:
            raise ValueError("Укажите query, voice_base64 или image_base64.")
        return self
```

### Voice Processing
```python
# Lines 2968-2990
if payload.voice_base64:
    raw_voice = (payload.voice_base64 or "").strip()
    try:
        audio_bytes = base64.b64decode(raw_voice, validate=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid voice_base64"
        )
    
    if len(audio_bytes) > int(settings.VOICE_MAX_BYTES):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="voice payload too large"
        )
    
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
                        "(установите faster-whisper и модель, либо задайте OPENAI_API_KEY; "
                        "DeepSeek аудио не принимает). Напишите, пожалуйста, текстом."
                    ),
                    "status": RuntimeProcessingStatus.SUCCESS.value,
                },
                status_code=status.HTTP_200_OK,
            )
```

### Image Processing
```python
# Lines 3002-3011
if payload.image_base64:
    mime = ((payload.image_mime_type or "image/jpeg").strip() or "image/jpeg")
    raw_img = (payload.image_base64 or "").strip()
    
    try:
        img_bytes = base64.b64decode(raw_img, validate=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid image_base64"
        )
    
    if len(img_bytes) > int(settings.IMAGE_MAX_BYTES):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="image payload too large"
        )
    
    runtime_ctx["vision_image_data_url"] = f"data:{mime};base64,{raw_img}"
    if not query_text:
        query_text = "[Изображение без текстовой подписи]"
```

---

## 6. WHATSAPP USERBOT - CURRENT IMPLEMENTATION

**File:** `backend/app/channels/whatsapp_userbot_manager.py` (Lines 101-156)

### Text Extraction (INCOMPLETE)
```python
def _extract_text(message: dict[str, Any]) -> str:
    """Extract text from WhatsApp message."""
    msg = message.get("message") or {}
    text = (
        msg.get("conversation")                    # Plain text message
        or (msg.get("extendedTextMessage") or {}).get("text")  # Rich text
        or (msg.get("imageMessage") or {}).get("caption")      # Photo caption ⚠️
        or (msg.get("videoMessage") or {}).get("caption")      # Video caption ⚠️
        or ""
    )
    return str(text).strip()

# ❌ MISSING:
# - imageMessage.imageData  (binary image)
# - videoMessage.videoData  (binary video)
# - audioMessage            (audio message type)
# - documentMessage         (document/file)
```

### Message Processing
```python
async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return
    
    # Only process private messages, not groups
    if not _is_private_whatsapp_jid(remote_jid):
        return
    
    if str(incoming.get("from_me") or "").lower() == "true":
        return
    
    text = _extract_text(incoming)  # ← Only gets caption/text
    if not text:
        return
    
    # ❌ NO runtime_context created for media!
    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text,  # ← Lost any attachment data
        user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
        # ❌ No runtime_context parameter!
    )
```

---

## 7. TEMPLATE RUNTIME - WHERE VISION IS LOST

**File:** `backend/app/services/template_runtime.py`

### Execute Method (Lines 79-103)
```python
async def execute(
    self,
    *,
    template_type: str | None,
    prompt: str,
    user_message: str,
    knowledge_scope_id: int,
    agent_id: int | None = None,
    user_external_id: str | None = None,
    template_config: dict[str, Any] | None = None,
    source_channel: str | None = None,
    chat_portrait: str | None = None,
    runtime_context: dict[str, object] | None = None,  # ← RECEIVES HERE
) -> TemplateExecutionResult:
    """Execute agent template with optional vision support."""
    
    normalized = (template_type or "qa").strip().lower()
    if normalized == "function_calling":
        normalized = "crm_admin"
    
    if normalized == "crm_admin":
        crm_result = await self._execute_crm_admin(...)
        if crm_result is not None:
            return crm_result
    
    # ❌ PROBLEM: runtime_context NOT passed to _execute_qa_like!
    if normalized in {"qa", "lead_generation", "content_factory"}:
        return await self._execute_qa_like(
            prompt=prompt,
            user_message=user_message,
            knowledge_scope_id=knowledge_scope_id,
            # ❌ Missing: runtime_context=runtime_context
        )
```

### Current _execute_qa_like (BROKEN)
```python
# Lines 308-329
async def _execute_qa_like(
    self,
    *,
    prompt: str,
    user_message: str,
    knowledge_scope_id: int,
    # ❌ NO runtime_context parameter!
) -> TemplateExecutionResult:
    """Execute QA template (search + generate)."""
    
    context = await search_knowledge_base(user_message, agent_id=knowledge_scope_id)
    context_list = context if isinstance(context, list) else []
    
    answer = await generate_answer_with_context(
        user_message,
        context_list,
        prompt,
        # ❌ NOT passing runtime_context!
    )
```

### Current generate_answer_with_context (BROKEN)
```python
# backend/app/services/ai_authoring.py, Lines 79-98
async def generate_answer_with_context(
    question: str,
    context_list: list,
    system_prompt: str,
    # ❌ NO runtime_context parameter!
) -> str:
    """Generate answer based on context and question."""
    
    # Build messages
    full_system_prompt = _build_system_prompt(system_prompt, context_list)
    user_prompt = _build_user_prompt(context_list, question)
    
    messages = [
        {"role": "system", "content": full_system_prompt},
        {"role": "user", "content": user_prompt},  # ← STRING ONLY, NO VISION!
    ]
    
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.3,
        # ❌ No image_url support!
    )
```

---

## 8. MESSAGE PROCESSOR - CORRECT HANDLING

**File:** `backend/app/channels/message_processor.py` (Lines 200-245)

```python
async def process(self, request: MessageRequest) -> MessageResponse:
    """Process message through template runtime."""
    
    # ... validation ...
    
    # Parse template config
    template_config = self._parse_template_config(resolved_agent.template_config)
    
    # ... availability checks ...
    
    # Build runtime context
    merged_runtime_ctx: dict[str, object] = dict(request.runtime_context or {})
    
    # Add Telegram peer info if available
    if request.telegram_peer_access_hash is not None and int(request.telegram_peer_access_hash) != 0:
        merged_runtime_ctx["telegram_peer_access_hash"] = int(request.telegram_peer_access_hash)
    
    # Add vision model config
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
    
    # Execute with runtime context
    execution = await get_template_runtime().execute(
        template_type=resolved_agent.template_type,
        prompt=request.system_prompt or (resolved_agent.system_prompt or ""),
        user_message=request.query,
        knowledge_scope_id=resolved_agent.bot_id or resolved_agent.id,
        agent_id=resolved_agent.id,
        user_external_id=normalized_user_external_id,
        template_config=template_config,
        source_channel=request.channel.value,
        chat_portrait=chat_portrait,
        runtime_context=merged_runtime_ctx,  # ← Passed here, but lost later!
    )
```

---

## Summary

| Component | Status | Issue |
|-----------|--------|-------|
| Photo upload (Telegram) | ✅ Works | - |
| Photo → Base64 | ✅ Works | - |
| Voice → Whisper | ✅ Works | - |
| MessageRequest.runtime_context | ✅ Works | - |
| MessageProcessor.process() | ✅ Works | - |
| TemplateRuntime.execute() receives context | ✅ Works | - |
| _execute_qa_like() receives context | ❌ BROKEN | Not passed |
| generate_answer_with_context() uses vision | ❌ BROKEN | Not passed |
| LLM sees image for QA | ❌ BROKEN | Data lost |
| **Overall Vision Support** | ❌ **BROKEN** | **Complete chain failure** |
