# Настройка внешних сервисов (телефония)

Модель: **один входящий номер** на платформе (Voximplant) + **4-значный добавочный** на каждого агента. Секреты Voximplant и DID задаются только в `.env` сервера, не в UI.

## 1. Voximplant

### Регистрация и номер

1. [manage.voximplant.com](https://manage.voximplant.com) — создайте аккаунт.
2. **Phone numbers** → купите/подключите один входящий номер (DID) — это `TELEPHONY_SHARED_POOL_E164` (формат E.164, например `+74951234567`).
3. Привяжите номер к **Application** (приложению VoxEngine).

### Application и сценарий

1. **Applications** → создайте приложение → запомните **Application ID** → `TELEPHONY_VOXIMPLANT_APPLICATION_ID`.
2. Загрузите сценарий из репозитория: `voxengine/rsd_inbound.js` и `voxengine/lib/*` (см. [voxengine/README.md](../../voxengine/README.md)).
3. **Routing rules** → правило на купленный номер, сценарий `rsd_inbound`.
4. **Rule ID** из кабинета → `TELEPHONY_VOXIMPLANT_RULE_ID`.
5. В **script_custom_data** правила укажите (пример):

```json
{
  "connection_id": 42,
  "webhook_base_url": "https://rsd-ai.ru",
  "media_ws_url": "wss://rsd-ai.ru/ws",
  "require_extension": true,
  "greeting_text": "Введите четыре цифры добавочного номера"
}
```

`require_extension: true` обязателен для общего номера с DTMF-маршрутизацией.

### API Key и Account ID

| Переменная | Где взять |
|------------|-----------|
| `TELEPHONY_VOXIMPLANT_ACCOUNT_ID` | **Settings** → **API** → Account ID (числовой) |
| `TELEPHONY_VOXIMPLANT_API_KEY` | **Settings** → **API** → создайте **API Key** (не пароль от кабинета) |

Проверка с сервера: при подключении канала агента backend вызывает `GetAccountInfo`, `GetPhoneNumbers`, `GetRules` ([voximplant_client.py](../../backend/app/services/voximplant_client.py)).

### Secrets приложения (не .env backend)

В кабинете приложения: **Manage** → **Secrets**:

| Secret | Значение |
|--------|----------|
| `RSD_WEBHOOK_SECRET` | `webhook_secret` из credentials канала (показывается после подключения агента; HMAC webhook) |
| `RSD_WEBHOOK_BASE_URL` | = `TELEPHONY_WEBHOOK_BASE_URL` (HTTPS без path) |
| `TELEPHONY_MEDIA_WS_URL` | = `TELEPHONY_MEDIA_WS_URL` (публичный `wss://…/ws`) |

### Перевод на оператора

`TELEPHONY_OPERATOR_TRANSFER_E164` — E.164 номера живого оператора (перевод из сценария). Один на всю платформу.

### Как звонят клиенты

- Позвонить на общий номер → после приветствия ввести **4 цифры** добавочного агента.
- Или с телефона с поддержкой DTMF в номере: `+74951234567,1234` (отображается в UI как **dial_hint**).

---

## 2. Yandex SpeechKit (STT + TTS)

1. [console.cloud.yandex.ru](https://console.cloud.yandex.ru) → каталог → **сервисный аккаунт** с ролями `ai.speechkit-stt.user`, `ai.speechkit-tts.user` (или аналог для API-ключа).
2. **API-ключ** → `YANDEX_SPEECHKIT_API_KEY`.
3. **Folder ID** каталога → `YANDEX_SPEECHKIT_FOLDER_ID` (рекомендуется для учёта).

Используется: `telephony_media_gateway` (streaming STT), orchestrator (stream TTS), preview в браузере.

---

## 3. LLM

| Режим | Переменные |
|-------|------------|
| DeepSeek (по умолчанию) | `TELEPHONY_LLM_MODE=chat`, `DEEPSEEK_API_KEY` — [platform.deepseek.com](https://platform.deepseek.com) API keys |
| Groq | `TELEPHONY_LLM_MODE=groq`, `GROQ_API_KEY` — [console.groq.com](https://console.groq.com) |

---

## 4. Опционально: ElevenLabs / Deepgram / OpenAI

- **ElevenLabs** (stream TTS): `TELEPHONY_STREAM_TTS_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY` — [elevenlabs.io](https://elevenlabs.io) → Profile → API Key.
- **Deepgram** (STT в gateway): `STT_PROVIDER=deepgram`, `DEEPGRAM_API_KEY` — [console.deepgram.com](https://console.deepgram.com).
- **OpenAI** (preview TTS): `TELEPHONY_TTS_PROVIDER=openai`, `OPENAI_API_KEY` — [platform.openai.com](https://platform.openai.com/api-keys).

---

## 5. Внутренние секреты RSD

```bash
openssl rand -hex 32
```

| Переменная | Назначение |
|------------|------------|
| `INTERNAL_API_KEY` | Internal API fallback |
| `INTERNAL_REQUEST_SIGNING_SECRET` | HMAC worker/bridge → backend |
| `TELEPHONY_BRIDGE_API_KEY` | Авторизация HTTP `telephony_bridge` |
| `TELEPHONY_INTERNAL_API_KEY` | Bridge → backend (пусто = `INTERNAL_API_KEY`) |
| `ENCRYPTION_KEY` | Шифрование credentials каналов |

---

## 6. Публичные URL

| Переменная | Пример |
|------------|--------|
| `TELEPHONY_WEBHOOK_BASE_URL` | `https://rsd-ai.ru` (nginx → `telephony_bridge:8100`) |
| `TELEPHONY_MEDIA_WS_URL` | `wss://rsd-ai.ru/ws` (nginx → `telephony_media_gateway:8200`) |

В prod **нельзя** `localhost` в `TELEPHONY_MEDIA_WS_URL` — Voximplant cloud не достучится.

---

## 7. Чеклист после деплоя

1. `.env`: блок **Platform pool** + `TELEPHONY_ENABLED=true` + Redis + Yandex + LLM.
2. `docker compose up` сервисы телефонии (см. [ENV_VARIABLES.md](./ENV_VARIABLES.md)).
3. Voximplant: сценарий, rule, secrets, `require_extension: true`.
4. В UI агента: подключить канал «Телефония», указать **добавочный 4 цифры**.
5. Скопировать **Webhook URL** канала в Voximplant (если используется per-connection secret) или общий bridge URL по документации RFC-001.
6. Тестовый звонок на общий номер → ввод добавочного → диалог с агентом.

Подробнее маршрутизация: [ROUTING.md](./ROUTING.md).
