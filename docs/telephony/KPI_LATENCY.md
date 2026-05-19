# KPI задержки телефонии (этап 0)

Метрики используются для приёмки MVP (этапы 2–4) и оптимизации (этапы 5–6). Замеры — на тестовом стенде Voximplant + `telephony_bridge` + backend.

## Целевые значения

| Метрика | Определение | MVP (допустимо) | Цель (production) |
|---------|-------------|-----------------|-------------------|
| **TTFA** (time to first agent audio) | От `call.inbound` / answer до начала первого TTS агента | < 4 с (p95) | < 1.2 с (p95) |
| **E2R** (end-of-speech → reply start) | От конца реплики абонента (VAD/тишина) до первого байта ответа агента | 3–8 с (p95) | < 1.5 с (p95) |
| **Barge-in** | Прерывание TTS при речи абонента | Нет | Да (< 200 ms stop) |
| **Concurrency** | Одновременные активные звонки на одного агента | 1–3 (тест) | N (по тарифу) |

## Как измерять

### TTFA

```
TTFA_ms = t(first_tts_play_start) - t(call.answered | call.inbound)
```

Логировать в `agent_telephony_calls.metadata` и/или bridge: `latency.ttfa_ms`.

### E2R

```
E2R_ms = t(agent_tts_start) - t(user_speech_end)
```

На MVP: `user_speech_end` = момент окончания записи фразы (тишина 1.5–2.5 с). На этапе 5: endpointing по partial STT.

Логировать по ходам: `agent_telephony_turns.latency_ms` (STT + LLM + TTS).

### Регрессия (этап 5+)

- Набор из 50 WAV-фраз (короткие/длинные, шум).
- Поля: `eos_to_first_audio_ms`, `stt_final_ms`, `llm_first_token_ms`, `tts_first_byte_ms`.

## Алерты (этап 4+)

| Условие | Действие |
|---------|----------|
| `turn_latency_p95 > 10 s` (MVP) | Warning, разбор STT/LLM |
| `turn_latency_p95 > 2 s` (post-этап 5) | Alert |
| `stt_empty_rate > 15%` | Проверка микрофона / промпт «повторите» |

## Связь с продуктом

До этапа 5 позиционировать пилот как **бета по задержке**; baseline замерить после первого E2E на этапе 2 и зафиксировать в `metadata` первых 20 звонков.
