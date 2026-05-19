# Решение по CPaaS (этап 0)

**Статус:** утверждено для MVP  
**Дата:** 2026-05-18  
**Выбранный провайдер:** [Voximplant](https://voximplant.com/)

## Сравнение (кратко)

| Критерий | Voximplant | Mango Office | Twilio |
|----------|------------|--------------|--------|
| РФ, номера | Да | Да | Ограниченно |
| Webhook + сценарии | Да | Да | Да |
| Встроенные ASR/TTS | Да | Частично / партнёры | Да (Media Streams) |
| Документация для voice-бота | Хорошая | Средняя | Отличная |

**Обоснование:** для MVP нужен один провайдер с webhook, сценариями VoxEngine, встроенным TTS/ASR и номерами в РФ. Voximplant закрывает все пункты без отдельного SIP. В коде далее — абстракция `TelephonyProvider`; смена CPaaS не должна менять контракт `MessageProcessor` / `template_runtime`.

## Маппинг в RSD

| Сущность RSD | Значение |
|--------------|----------|
| `agent_channel_connections.provider` | `telephony_voximplant` |
| `encrypted_credentials` (JSON, до шифрования) | см. [credentials.v1.schema.json](../../schemas/telephony/credentials.v1.schema.json) |
| Публичный webhook | `/webhook/voximplant/{connection_id}` |

## Чеклист: тестовый аккаунт и номер

Выполнить в [кабинете Voximplant](https://manage.voximplant.com/). Секреты хранить только в `.env` / `encrypted_credentials`, не в git.

### 1. Аккаунт

- [ ] Зарегистрировать аккаунт (или использовать корпоративный).
- [ ] Скопировать **Account ID** и **API Key** (раздел API).
- [ ] Включить биллинг / тестовый баланс для исходящих вызовов и TTS (по тарифу).

### 2. Application и сценарий

- [ ] Создать **Application** (например `rsd-telephony-dev`).
- [ ] Записать **Application ID**.
- [ ] Создать **Rule** для входящих на тестовый номер (routing → HTTP callback на bridge).
- [ ] Записать **Rule ID**.
- [ ] Подготовить минимальный VoxEngine-сценарий (этап 2): answer → HTTP POST на bridge → play/record по ответу bridge.

### 3. Номер

- [ ] Арендовать или привязать тестовый номер в формате **E.164** (например `+79XXXXXXXXX`).
- [ ] Привязать номер к Application / Rule.
- [ ] Зафиксировать номер в `phone_number_e164` в credentials.

### 4. Webhook на bridge (после деплоя этапа 1)

- [ ] Указать URL: `https://<TELEPHONY_WEBHOOK_BASE_URL>/webhook/voximplant/<connection_id>`.
- [ ] Сгенерировать `webhook_secret` (мин. 32 символа, `openssl rand -hex 32`).
- [ ] Проверить TLS и доступность с интернета (curl / тестовый звонок).

### 5. Оператор для transfer (MVP)

- [ ] Указать `operator_transfer_e164` — мобильный тестового оператора для эскалации.

### 6. Локальная разработка

- [ ] Скопировать [.env.telephony.example](../../.env.telephony.example) → дополнить корневой `.env`.
- [ ] Для локального webhook: ngrok / Cloudflare Tunnel на порт `telephony_bridge` (планируется `8100`).

## Журнал тестового окружения (заполнить командой)

| Поле | Значение |
|------|----------|
| Account ID | _заполнить_ |
| Application ID | _заполнить_ |
| Rule ID | _заполнить_ |
| Тестовый номер E.164 | _заполнить_ |
| Webhook URL (staging) | _заполнить_ |
| Ответственный | _заполнить_ |

> После заполнения таблицы не коммитить реальные ключи — только ссылку на vault / password manager.
