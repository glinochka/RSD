# Runbook: телефония (этап 4)

## Сервисы

| Сервис | Порт | Health |
|--------|------|--------|
| `telephony_bridge` | 8100 | `GET /health` |
| backend | 8000 | `GET /health` (если есть) |

## Деплой

1. Установить в `.env`: `TELEPHONY_ENABLED=true`, `TELEPHONY_INTERNAL_API_KEY`, `TELEPHONY_BRIDGE_API_KEY`, `TELEPHONY_WEBHOOK_BASE_URL` (HTTPS).
2. `docker compose up -d telephony_bridge backend`
3. Проверить: `curl -s http://127.0.0.1:8100/health`
4. Метрики bridge: `curl -s -H "X-API-Key: $TELEPHONY_BRIDGE_API_KEY" http://127.0.0.1:8100/metrics`
5. Метрики backend: internal `GET /api/internal/telephony/metrics` (ключ + HMAC)

## Типовые сбои

| Симптом | Действие |
|---------|----------|
| `401 Invalid signature` | Сверить `webhook_secret` в credentials и Voximplant callback |
| `429 Rate limit` | Проверить flood/replay; увеличить лимиты только временно |
| `502 Backend call-event failed` | Логи backend; БД; `TELEPHONY_ENABLED` |
| Абонент слышит «Сервис временно недоступен» | Backend недоступен из bridge-сети; проверить `TELEPHONY_BACKEND_URL` |
| `turn_latency_p95_high` alert | LLM/STT медленные; см. KPI_LATENCY.md |

## Retention (cron)

Раз в сутки (пример):

```bash
curl -X POST "$BACKEND_URL/api/internal/telephony/retention/purge" \
  -H "X-Internal-API-Key: $TELEPHONY_INTERNAL_API_KEY" \
  -H "X-Internal-Timestamp: ..." \
  -H "X-Internal-Signature: ..."
```

Срок: `TELEPHONY_TURNS_RETENTION_DAYS` (по умолчанию 90).

## Compliance

- IVR disclaimer при `record_calls=true` и `disclaimer_played=true` — автоматически на `call.answered`.
- Чеклист: [COMPLIANCE_CHECKLIST.md](./COMPLIANCE_CHECKLIST.md)
- Pentest webhook: [WEBHOOK_PENTEST_CHECKLIST.md](./WEBHOOK_PENTEST_CHECKLIST.md)
