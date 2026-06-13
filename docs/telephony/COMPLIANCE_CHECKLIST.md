# Юридический чеклист телефонии (черновик, этап 0–8)

**Не является юридической консультацией.** Перед пилотом согласовать с юристом компании и политикой обработки ПДн (152-ФЗ).

## 1. Уведомление о записи разговора

- [ ] В начале звонка проигрывается IVR-disclaimer (если `record_calls: true`).
- [ ] Текст согласован с юристом и зафиксирован в credentials / шаблоне агента.
- [ ] Владелец агента может отключить запись (`record_calls: false`) — тогда disclaimer про запись не используется (или сокращённый вариант про обработку обращения).

### Рекомендуемый текст IVR (RU, черновик)

> Здравствуйте. Ваш разговор может быть записан для контроля качества и обучения сервиса. Продолжая разговор, вы соглашаетесь на обработку персональных данных в соответствии с политикой конфиденциальности компании. Если вы не согласны — положите трубку или нажмите решётку.

Короткий вариант (если лимит по длительности IVR):

> Разговор может быть записан. Продолжая, вы соглашаетесь с политикой конфиденциальности на сайте компании.

Флаг в credentials: `disclaimer_played: true` — bridge обязан проиграть disclaimer до первой реплики агента (этап 2+).

## 2. Политика хранения записей

- [ ] Определить срок хранения записей у CPaaS и в RSD (рекомендация пилота: **90 дней**, настраиваемо).
- [ ] Описать в политике конфиденциальности клиента: кто оператор записи (Voximplant / RSD), цель, срок.
- [ ] Процедура удаления по запросу субъекта ПДн (DSAR).
- [ ] Запрет хранения записей в открытых логах и S3 без шифрования.

## 3. Согласие на обработку ПДн

- [ ] Основание обработки: согласие / исполнение договора — зафиксировать с юристом.
- [ ] Номер абонента (`caller_e164`) — ПДн: маскирование в UI (`+7900***1234`), ограничение доступа по ролям.
- [ ] Транскрипты в `agent_telephony_turns` — та же политика, что сообщения в мессенджерах.
- [ ] DPA с Voximplant (обработчик) при коммерческом запуске.

## 4. Перевод на живого оператора

- [ ] Номер `operator_transfer_e164` — согласие оператора на приём переводов.
- [ ] При transfer абонент уведомлён голосом («соединяю с оператором»).

## 5. Территория и трансграничная передача

- [ ] Данные и медиа в РФ / у провайдера с договором, допустимым для клиента.
- [ ] Если LLM/STT вне РФ — отдельное решение и уведомление в политике.
- [ ] **Деплой (этап 8):** `telephony_media_gateway`, orchestrator worker и Redis — в **одном регионе** с Voximplant edge РФ (см. [RUNBOOK.md](./RUNBOOK.md#регион-деплоя-этап-8)).

## 6. Шифрование сигнализации и медиа (SIP TLS / SRTP)

- [ ] В кабинете Voximplant / SBC включены **SIP TLS** (сигнализация) и **SRTP** (медиа RTP).
- [ ] Сертификаты TLS на SBC / trunk — от доверенного УЦ, ротация задокументирована.
- [ ] WebSocket media (`TELEPHONY_MEDIA_WS_URL`) — только **WSS** в production (TLS termination на reverse-proxy в РФ).
- [ ] Межсервисный трафик gateway ↔ orchestrator ↔ Redis — внутри VPC, без публичного Redis.
- [ ] В pentest-чеклисте зафиксирован отказ от plain RTP/SIP в prod.

| Контур | Требование prod |
|--------|-----------------|
| PSTN ↔ Voximplant | SIP TLS + SRTP |
| VoxEngine ↔ Media Gateway | WSS (μ-law frames) |
| Bridge webhook | HTTPS + HMAC |
| Internal API | HMAC + mTLS (рекомендуется) |

## 7. Retention hot/cold (этап 8)

| Данные | Hot (Redis) | Cold (Postgres) |
|--------|-------------|-----------------|
| Диалог последних N реплик | `telephony:dialog:{call_id}` TTL | `agent_telephony_turns` батч на `stt.final` |
| Промпт / session resolve | `telephony:session:*` TTL | resolve один раз на звонок |
| Метрики latency | `agent_telephony_calls.metadata_.latency_budget` | история `latency_budget_turns` (до 50) |

- [ ] Cron: `POST /api/internal/telephony/retention/purge` — `TELEPHONY_TURNS_RETENTION_DAYS` (90).
- [ ] На `session.end` / hangup — purge hot dialog keys в Redis (orchestrator).

## 8. Журнал compliance для пилота

| Пункт | Статус | Комментарий |
|-------|--------|-------------|
| IVR disclaimer | Реализовано | Bridge `call.answered` + `record_calls` / `disclaimer_played` |
| Retention 90 дней | Реализовано | `POST /api/internal/telephony/retention/purge`, `TELEPHONY_TURNS_RETENTION_DAYS` |
| Hot dialog только Redis | Реализовано | `purge_hot_dialog` на `session.end` |
| Маскирование caller в UI | Реализовано | Этап 3 |
| Latency budget / E2R p90 | Реализовано | `metadata.latency_budget`, `/metrics`, Prometheus |
| SIP TLS + SRTP | Чеклист | Настройка Voximplant/SBC — см. §6 |
| DPA Voximplant | Не начато | До коммерции |

## 9. Связь с продуктом

| Поле credentials | Назначение |
|------------------|------------|
| `record_calls` | Включить запись у CPaaS |
| `disclaimer_played` | Требовать IVR перед диалогом |
| `language` | Язык disclaimer и TTS (`ru-RU`) |
