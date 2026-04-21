# WhatsApp Userbot Bridge

Минимальный bridge-сервис для backend-роутов:

- `POST /auth/request_code`
- `POST /auth/verify_code`

## Назначение

Сервис закрывает flow "Простое подключение" WhatsApp userbot:

1. backend запрашивает код в bridge;
2. backend подтверждает код в bridge;
3. bridge возвращает `session_string` для сохранения канала.

## Важно

Текущая реализация — dev bridge (in-memory), чтобы flow работал end-to-end.
Для production замените внутреннюю логику на реальную интеграцию WA SDK.

## ENV

- `WA_USERBOT_BRIDGE_API_KEY` — API key для заголовка `X-API-Key` (опционально)
- `WA_USERBOT_AUTH_TTL_SECONDS` — TTL auth-сессии, по умолчанию `600`
- `WA_USERBOT_AUTH_MAX_ATTEMPTS` — максимум попыток verify, по умолчанию `5`
- `WA_USERBOT_SESSION_SECRET` — секрет подписи session_string
- `WA_USERBOT_DEV_EXPOSE_CODE` — показывать dev code в `hint` (`true/false`)

## Local run

```bash
cd wa_bridge
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8090
```

## API примеры

### Request code

```bash
curl -X POST http://localhost:8090/auth/request_code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"phone_number":"+79990001122"}'
```

### Verify code

```bash
curl -X POST http://localhost:8090/auth/verify_code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"auth_id":"wauth_...","phone_number":"+79990001122","code":"123456"}'
```
