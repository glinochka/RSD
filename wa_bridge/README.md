# WhatsApp Userbot Bridge

Bridge-сервис для backend-роутов:

- `POST /auth/request_code`
- `POST /auth/verify_code`

## Назначение

Сервис закрывает flow "Простое подключение" WhatsApp userbot:

1. backend запрашивает код в bridge;
2. backend подтверждает код в bridge;
3. bridge возвращает `session_string` для сохранения канала.

## Важно

Текущая реализация использует `@whiskeysockets/baileys` и реальный WhatsApp pairing flow.
Пользователь получает `pairing_code` в интерфейсе вашего продукта и вводит его в приложении WhatsApp
(`Связанные устройства` -> `Привязать устройство`).

## ENV

- `WA_USERBOT_ENV` — `production` или `development` (по умолчанию `production`)
- `WA_USERBOT_BRIDGE_API_KEY` — API key для заголовка `X-API-Key` (в production обязателен)
- `WA_USERBOT_AUTH_TTL_SECONDS` — TTL auth-сессии, по умолчанию `600`
- `WA_USERBOT_AUTH_MAX_ATTEMPTS` — максимум попыток verify, по умолчанию `5`
- `WA_USERBOT_REQUEST_WINDOW_SECONDS` — окно rate-limit запроса кода (сек)
- `WA_USERBOT_REQUESTS_PER_PHONE_LIMIT` — лимит request_code на номер в окне
- `WA_USERBOT_VERIFY_WINDOW_SECONDS` — окно rate-limit verify (сек)
- `WA_USERBOT_VERIFY_PER_PHONE_LIMIT` — лимит verify на номер в окне
- `WA_USERBOT_SESSION_SECRET` — секрет подписи session_string (в production обязателен, >= 32 символов)
- `WA_USERBOT_DEV_EXPOSE_CODE` — показывать dev code в `hint` (`true/false`, в production должен быть `false`)
- `WA_USERBOT_DATA_DIR` — директория хранения auth state (по умолчанию `/data/wa-auth`)

## Production checklist

1. Установите длинный `WA_USERBOT_BRIDGE_API_KEY`.
2. Установите отдельный длинный `WA_USERBOT_SESSION_SECRET` (>= 32 символов).
3. Оставьте `WA_USERBOT_DEV_EXPOSE_CODE=false`.
4. Не публикуйте bridge наружу; держите его только в docker-сети (в compose порт наружу не проброшен).
5. Учтите, что WA userbot может нарушать правила платформы WhatsApp и приводить к блокировке номера.

## Local run

```bash
cd wa_bridge
npm install
export WA_USERBOT_ENV=development
export WA_USERBOT_BRIDGE_API_KEY=dev-key
export WA_USERBOT_SESSION_SECRET=dev-super-secret-should-be-long
node server.js
```

## API примеры

### Request code

```bash
curl -X POST http://localhost:8090/auth/request_code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"phone_number":"+79990001122"}'
```

Ответ вернет `pairing_code`. Пользователь должен ввести его в WhatsApp на телефоне.

### Verify code

```bash
curl -X POST http://localhost:8090/auth/verify_code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"auth_id":"wauth_...","phone_number":"+79990001122","code":"123456"}'
```

`code` должен совпадать с `pairing_code` из предыдущего шага.
Если pairing на телефоне еще не завершен — bridge вернет `409`.
