# KPI задержки телефонии (этап 8 — streaming)

Метрики для приёмки prod PSTN (`telephony_media_gateway` + orchestrator). Preview (`channel=browser_preview`) в бюджет **не входит**.

## Latency budget (целевой p90)

| Поле | Определение | Target p90 (ms) |
|------|-------------|-----------------|
| `sip_ms` | Inbound → первый ответ сигнализации (183/answer) | 1200 |
| `vad_ms` | Оценка тишины до endpoint (из `vad_speech_ratio` × `stt_final_ms`) | 450 |
| `stt_final_ms` | Конец реплики абонента → финальный transcript | 400 |
| `llm_ttft_ms` | `stt.final` → первый токен LLM | 300 |
| `tts_ttfa_ms` | первый токен → первый байт TTS | 150 |
| `e2r_ms` | end-of-speech → первый байт ответа агента (wall или сумма) | **600–850** |

Значения пишутся в `agent_telephony_calls.metadata_.latency_budget` и агрегируются в `GET /api/internal/telephony/metrics` (`latency_budget_p90`, `latency_budget_table`).

Prometheus (тот же процесс backend):

```bash
curl -s -H "X-Internal-..." "$BACKEND/api/internal/telephony/metrics/prometheus"
```

## Как измерять

### E2R (production)

```
E2R_ms ≈ stt_final_ms + llm_ttft_ms + tts_ttfa_ms
```

или wall-clock orchestrator от `stt.final` до первого `agent.audio.chunk` (`e2r_ms` в metadata).

### Регрессия

- Набор из **50** коротких фраз (RU), замер p90 `e2r_ms` на стенде в регионе РФ.
- Критерий этапа 8: **p90 E2R 600–850 ms** при mock/Yandex STT на стенде.

## Алерты

| Условие | Env | Действие |
|---------|-----|----------|
| `turn_latency_p95 > TELEPHONY_TURN_LATENCY_ALERT_P95_MS` | default 10000 | Warning |
| `e2r_p90 > TELEPHONY_E2R_ALERT_P90_MS` | default 850 | Warning, разбор STT/LLM/TTS |
| `stt_empty_rate > 15%` | — | Проверка микрофона / промпт |

## Связь с preview

Браузерный preview использует batch STT и не публикует latency budget — см. [SESSION_PROTOCOL.md](./SESSION_PROTOCOL.md).
