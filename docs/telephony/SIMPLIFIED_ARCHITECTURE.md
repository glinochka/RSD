# Simplified Telephony Architecture

## Overview

This document describes the simplified telephony architecture that replaces the complex streaming infrastructure with Voximplant's built-in TTS and ASR.

## Problem with Original Architecture

The original telephony system had 4 independent layers with complex interactions:

1. **Signal Plane** (telephony_bridge) - HTTP webhooks on port 8100
2. **Media Plane** (telephony_media_gateway) - WebSocket on port 8200 with:
   - PCM16 → μ-law conversion
   - Redis pub/sub for audio chunks
   - Playback pacing
   - Barge-in detection
   - VAD + streaming STT (Yandex/Deepgram)
3. **Dialog Plane** (orchestrator_worker) - Redis pub/sub with:
   - Streaming TTS via gRPC
   - Syntagma chunking
   - Complex fallback layers
4. **Control Plane** - REST API

### Issues:
- Audio from TTS didn't reach the call (no agent greeting or LLM responses)
- Too many moving parts with multiple failure points
- Complex Redis pub/sub for audio chunks
- WebSocket media streaming fragile
- Difficult to debug across 3 services

## Simplified Architecture

### New Flow

```
PSTN Call
    ↓
VoxEngine (rsd_simplified.js)
    - Uses call.say() for TTS (native Voximplant)
    - Uses call.startASR() for speech recognition (native Voximplant)
    - HTTP webhooks to backend
    ↓
Backend FastAPI (/api/internal/telephony/simplified/*)
    - Simple request/response model
    - No streaming, no WebSocket, no media gateway
    - Just returns text to speak
```

### Components

#### 1. VoxEngine Scenario (`rsd_simplified.js`)

**Features:**
- Early Media support
- DTMF handling for extension routing
- `call.say()` for TTS with configurable voice
- `call.startASR()` for speech recognition
- HTTP webhook communication to backend
- Call transfer support

**Configuration via CustomData or Secrets:**
```json
{
  "connection_id": 42,
  "webhook_base_url": "https://api.example.com",
  "webhook_secret": "...",
  "require_extension": true,
  "asr_language": "ru-RU",
  "asr_model": "general",
  "tts_voice": "Tatyana"
}
```

#### 2. Backend Webhooks (`webhooks.py`)

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/call.inbound` | POST | Incoming call, return greeting config |
| `/webhook/call.answered` | POST | Call answered, resolve agent if needed |
| `/webhook/asr.result` | POST | ASR result from Voximplant, return next action |
| `/webhook/call.hangup` | POST | Call ended, cleanup |

**Request/Response Format:**

Request from VoxEngine:
```json
{
  "call_id": "vox-call-id-123",
  "connection_id": 42,
  "caller_e164": "+79123456789",
  "event": "asr.result",
  "payload": {
    "transcript": "Привет, мне нужна помощь",
    "confidence": 0.95
  }
}
```

Response from backend:
```json
{
  "action": "say",
  "text": "Здравствуйте! Чем могу помочь?",
  "voice_id": "Tatyana"
}
```

Actions:
- `say` - Speak text using TTS
- `transfer` - Transfer to operator
- `hangup` - End call
- `enable_dtmf` - Enable DTMF input

#### 3. Simplified Orchestrator (`simplified_orchestrator.py`)

**Features:**
- In-memory call state (no audio streaming state)
- Direct LLM processing
- No Redis pub/sub for audio
- Simple action responses

### Advantages

1. **Fewer moving parts** - Only 2 components: VoxEngine + Backend
2. **No media streaming** - Uses Voximplant's native TTS/ASR
3. **Simpler debugging** - HTTP request/response is easier to trace
4. **More reliable** - Leverages Voximplant's proven TTS/ASR infrastructure
5. **Lower latency** - No audio chunking, conversion, or WebSocket overhead

### Trade-offs

1. **Less control over audio** - Can't use custom TTS engines (Yandex gRPC, ElevenLabs)
2. **Voximplant ASR only** - Can't use Deepgram or Yandex STT
3. **No barge-in during agent speech** - ASR is stopped while speaking
4. **No streaming LLM** - Must wait for complete response before speaking

### Migration Path

#### Option 1: Gradual (Recommended)

1. Deploy simplified VoxEngine scenario to a new Voximplant application
2. Route some numbers to the new application for testing
3. Compare reliability and quality
4. Migrate all traffic when confident

#### Option 2: Parallel Operation

1. Keep old system running
2. Add simplified endpoints alongside existing ones
3. Use feature flags to switch between implementations
4. Gradually increase simplified traffic

### Configuration

#### Required Environment Variables

```bash
# Backend
RSD_WEBHOOK_SECRET=your-webhook-secret

# Voximplant (Application Secrets)
RSD_CONNECTION_ID=42
RSD_WEBHOOK_BASE_URL=https://api.example.com
RSD_WEBHOOK_SECRET=your-webhook-secret
VOX_TTS_VOICE=Tatyana
VOX_ASR_LANGUAGE=ru-RU
```

#### Voximplant Application Setup

1. Create new application in Voximplant
2. Upload `rsd_simplified.js` as the scenario
3. Create routing rule with customData containing:
   - `connection_id`
   - `webhook_base_url`
   - `require_extension` (optional)
4. Assign phone numbers to the application

### Testing

#### Manual Testing

```bash
# Test inbound webhook
curl -X POST https://api.example.com/api/internal/telephony/simplified/webhook/call.inbound \
  -H "X-RSD-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-123",
    "connection_id": 42,
    "caller_e164": "+79123456789",
    "event": "call.inbound",
    "payload": {"caller_e164": "+79123456789"}
  }'

# Test ASR result
curl -X POST https://api.example.com/api/internal/telephony/simplified/webhook/asr.result \
  -H "X-RSD-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-123",
    "connection_id": 42,
    "caller_e164": "+79123456789",
    "event": "asr.result",
    "payload": {"transcript": "Привет", "confidence": 0.9}
  }'
```

### Future Enhancements

1. **Custom TTS** - Use Voximplant HTTP API for custom TTS synthesis
2. **Streaming ASR** - If Voximplant adds streaming ASR callbacks
3. **Async responses** - WebSocket or SSE for faster responses
4. **Barge-in** - Implement using Voximplant's audio level detection

## Comparison: Original vs Simplified

| Feature | Original | Simplified |
|---------|----------|------------|
| Services | 3 (bridge, gateway, orchestrator) | 2 (VoxEngine, backend) |
| TTS | Yandex gRPC streaming | Voximplant native |
| STT | Yandex/Deepgram streaming | Voximplant native |
| Media streaming | WebSocket μ-law | None |
| Redis usage | Pub/sub audio + events | Events only |
| Debug complexity | High | Low |
| Reliability | Medium | High |
| Custom TTS | Yes | Limited |
| Latency | Higher (chunks) | Lower (direct) |
