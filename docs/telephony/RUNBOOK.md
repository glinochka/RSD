# Runbook: телефония (этап 8 — control plane)

## Сервисы

| Сервис | Порт | Health |
|--------|------|--------|
| `telephony_bridge` | 8100 | `GET /health` |
| `telephony_media_gateway` | 8200 | `GET /health` |
| backend | 8000 | `GET /health` (если есть) |
| orchestrator worker | — | лог `subscribed to Redis events` |

## Регион деплоя (этап 8)

**Prod PSTN:** разместить в **одном регионе РФ** (или одной VPC):

- Voximplant edge / сценарий `voxengine/rsd_inbound.js`
- `telephony_media_gateway` (WSS)
- `python -m app.telephony.orchestrator_main`
- Redis (`REDIS_URL`)

Backend FastAPI и Postgres могут быть в том же регионе или с RTT &lt; 5 ms к Redis. Не разносить media gateway и Redis между AZ без замера E2R.

```bash
# Минимальный prod-стек (после миграций БД)
docker compose up -d redis telephony_media_gateway telephony_bridge backend
python -m app.telephony.orchestrator_main   # отдельный процесс / unit
```

`TELEPHONY_BRIDGE_CONTROL_ONLY=true` — bridge только сигнальные webhook; media только через gateway.

## Деплой

1. Установить в `.env`: `TELEPHONY_ENABLED=true`, `TELEPHONY_INTERNAL_API_KEY`, `TELEPHONY_BRIDGE_API_KEY`, `TELEPHONY_WEBHOOK_BASE_URL` (HTTPS), `REDIS_URL`, `TELEPHONY_BRIDGE_CONTROL_ONLY=true`.
2. `docker compose up -d telephony_bridge telephony_media_gateway backend redis`
3. Запустить orchestrator worker.
4. Проверить: `curl -s http://127.0.0.1:8100/health` и `curl -s http://127.0.0.1:8200/health`
5. Метрики JSON: internal `GET /api/internal/telephony/metrics`
6. Метрики Prometheus: `GET /api/internal/telephony/metrics/prometheus`
7. Bridge metrics: `curl -s -H "X-API-Key: $TELEPHONY_BRIDGE_API_KEY" http://127.0.0.1:8100/metrics`

### Latency dashboard (p90 E2R)

Поля `latency_budget_p90.e2r_p90_ms` и таблица `latency_budget_table` в `/metrics`. Цель: **600–850 ms** на 50 фраз (см. [KPI_LATENCY.md](./KPI_LATENCY.md)).

Алерт: `TELEPHONY_E2R_ALERT_P90_MS` (default 850).

## Типовые сбои

| Симптом | Действие |
|---------|----------|
| `401 Invalid signature` | Сверить `webhook_secret` в credentials и Voximplant callback |
| `429 Rate limit` | Проверить flood/replay; увеличить лимиты только временно |
| `502 Backend call-event failed` | Логи backend; БД; `TELEPHONY_ENABLED` |
| `410` на `/internal/telephony/turn` | Ожидаемо для PSTN — используйте gateway + orchestrator |
| `e2r_p90_high` alert | STT/VAD/LLM/TTS; см. `metadata.latency_budget` последних звонков |
| Абонент слышит «Сервис временно недоступен» | Backend недоступен из bridge-сети; проверить `TELEPHONY_BACKEND_URL` |

## Retention (cron)

Раз в сутки:

```bash
curl -X POST "$BACKEND_URL/api/internal/telephony/retention/purge" \
  -H "X-Internal-API-Key: $TELEPHONY_INTERNAL_API_KEY" \
  -H "X-Internal-Timestamp: ..." \
  -H "X-Internal-Signature: ..."
```

- **Postgres:** turns старше `TELEPHONY_TURNS_RETENTION_DAYS` (90).
- **Redis:** hot dialog удаляется orchestrator на `session.end` (`purge_hot_dialog`).

## Тесты без PSTN (этап 9)

```bash
# Backend unit/integration (CI)
cd backend/app && pytest tests/test_telephony_latency_budget.py tests/test_telephony_orchestrator_integration.py -q

# Gateway VAD unit
cd telephony_media_gateway && npm run test:vad

# Gateway pipeline + mock STT
STT_PROVIDER=mock TELEPHONY_MEDIA_PIPELINE_ENABLED=true npm run test:pipeline

# Load: parallel WS sessions (не webhook turn)
TELEPHONY_MEDIA_WS_URL=ws://127.0.0.1:8200/ws node telephony_bridge/scripts/load_parallel_calls.mjs

# Optional: replay WS trace
node telephony_media_gateway/scripts/replay_ws_trace.mjs telephony_media_gateway/traces/sample_pipeline.jsonl
```

## Compliance

- IVR disclaimer при `record_calls=true` и `disclaimer_played=true` — на `call.answered`.
- SIP TLS + SRTP: [COMPLIANCE_CHECKLIST.md](./COMPLIANCE_CHECKLIST.md) §6
- Pentest webhook: [WEBHOOK_PENTEST_CHECKLIST.md](./WEBHOOK_PENTEST_CHECKLIST.md)
