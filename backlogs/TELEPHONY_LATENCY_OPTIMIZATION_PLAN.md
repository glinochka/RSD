# План оптимизации latency телефонии

Документ основан на анализе кода: `telephony_media_gateway/`, `backend/app/telephony/`, `backend/app/channels/telephony_dialogue.py`.

**Цель:** снизить time-to-first-audio (E2R) в QA-диалоге с типичных 1200–2500 ms до **600–900 ms p90**, не ломая CRM-путь и barge-in.

---

## Текущее состояние

### Целевые метрики (код)

| Метрика | Target p90 (`latency_budget.py`) | Алерт (`config`) |
|---------|----------------------------------|------------------|
| `vad_ms` | 450 | — |
| `stt_final_ms` | 400 | — |
| `llm_ttft_ms` | 300 | — |
| `tts_ttfa_ms` | 150 | — |
| `crm_execute_ms` | 1000 | — |
| `e2r_ms` | 3000 | `TELEPHONY_E2R_ALERT_P90_MS` = 3000 |

### Фактический критический путь (QA)

```
µ-law → PCM16 → VAD (350ms silence) → STT (+50ms wait)
  → Redis stt.final
  → Orchestrator prep (DB, Redis, RAG)
  → LLM stream (буфер синтагм ≥12 символов)
  → TTS (Yandex: batch на синтагм / ElevenLabs: 40ms buffer)
  → Redis base64 × N фреймов
  → Gateway pacer (20ms) + downlink.ready (до 250ms)
  → Vox base64 PCM16
```

### Главные проблемы

1. **E2R метрика завышена** — `wall_ms` всего `handle_stt_final` (включая полное озвучивание) перезаписывает компонентную сумму.
2. **TTS Yandex не стримит** — `asyncio.to_thread(_stream_pcm_chunks)` собирает весь синтагм до первого `yield`; глобальный `_stub_lock`.
3. **LLM и TTS последовательны** — `await stream_syntagma_pcm16()` блокирует получение следующей синтагмы из LLM.
4. **Prep до стриминга** — PostgreSQL, portrait, RAG на каждый turn.
5. **Triple base64** — orchestrator → Redis → gateway → Vox на каждый 20ms фрейм.
6. **Playback gate** — pacer ждёт `downlink.ready` (fallback 250ms).
7. **Debug fetch на hot path** — `fetch(127.0.0.1:7864)` в `agent_playback.ts` / `agent_playback_pacer.ts`.

---

## Фазы работ

### Фаза 0 — Измерения и baseline (1–2 дня)

Без оптимизаций — зафиксировать baseline, иначе непонятно, что сработало.

| # | Задача | Файлы | Критерий готовности |
|---|--------|-------|---------------------|
| 0.1 | Добавить `first_audio_ms` — timestamp от `stt.final` до первого `publish_agent_audio_chunk` | `orchestrator_worker.py`, `stream_pipeline.py`, `latency_budget.py` | Поле в `latency_budget`, отдельно от `wall_ms` |
| 0.2 | Исправить `e2r_ms`: использовать `first_audio_ms`, не `wall_ms` | `latency_budget.py`, `orchestrator_worker.py` | `e2r_ms ≈ stt_final + llm_ttft + tts_ttfa` ± prep |
| 0.3 | Dashboard / curl baseline: 50 коротких фраз RU, p50/p90 по компонентам | `GET /api/internal/telephony/metrics` | Таблица до/после в этом документе (секция «Результаты») |
| 0.4 | Убрать debug `fetch` из production hot path (или за `NODE_ENV !== 'production'`) | `agent_playback.ts`, `agent_playback_pacer.ts` | Нет HTTP на 127.0.0.1 при звонке |

**Ожидаемый выигрыш:** 0 ms на TTFA, но корректные метрики для всех следующих фаз.

---

### Фаза 1 — Quick wins (2–4 дня, −200…400 ms TTFA)

Низкий риск, точечные правки.

| # | Задача | Ожидаемый выигрыш | Файлы |
|---|--------|-------------------|-------|
| 1.1 | Снизить `TELEPHONY_DOWNLINK_READY_TIMEOUT_MS` с 250 → **50** или стартовать pacer сразу после `agent.audio.start` | −0…200 ms на первый фрейм | `telephony_media_gateway/src/config.ts`, `agent_playback_pacer.ts` |
| 1.2 | `markPlaybackReady` при `agent.audio.start`, не ждать Vox `downlink.ready` | −50…250 ms | `agent_playback.ts` |
| 1.3 | Снизить `TELEPHONY_SYNTAGMA_MIN_CHARS` с 12 → **6** (или TTS по первым 8 токенам без пунктуации) | −100…300 ms на короткие ответы | `config/__init__.py`, `streaming.py` |
| 1.4 | Кеш `call` + `agent` в Redis после `session.start`, не грузить PG на каждый `stt.final` | −30…80 ms | `orchestrator_worker.py`, `session_cache.py` |
| 1.5 | Пропускать `_resolve_chat_portrait` если `enable_phone_portrait` / `enable_chat_portrait` = false (уже так; проверить агентов) | −0…500 ms | конфиг агентов |
| 1.6 | Согласовать TTS: один провайдер в env + убрать хардкод voice в orchestrator → `TELEPHONY_VOICE_ID` | −0…100 ms (меньше fallback) | `orchestrator_worker.py`, `stream_tts.py` |

**Целевой E2R после фазы 1 (QA):** p90 **900–1200 ms**.

---

### Фаза 2 — TTS streaming (3–5 дней, −150…400 ms TTFA)

Самый большой выигрыш на озвучке.

| # | Задача | Детали | Файлы |
|---|--------|--------|-------|
| 2.1 | **Yandex TTS: истинный stream** — yield фреймы по мере прихода gRPC chunks, без `pcm_parts` collect-all | Убрать batch `_stream_pcm_chunks` → async iterator | `yandex_tts_stream.py` |
| 2.2 | Убрать глобальный `_stub_lock` или заменить на per-call / channel pool | Параллельные звонки не блокируют друг друга | `yandex_tts_stream.py` |
| 2.3 | Запросить 8 kHz LINEAR16 напрямую (уже в proto) — убрать лишний endian-heuristic если формат стабилен | Меньше CPU на turn | `yandex_tts_stream.py` |
| 2.4 | ElevenLabs: уменьшить buffer 40ms → **20ms** (640 bytes @ 16kHz) | −20 ms TTFA при fallback | `stream_tts.py` |
| 2.5 | Прогрев TTS channel / HTTP connection pool | −30…50 ms на первый синтагм | `stream_tts.py`, gateway init |

**Альтернатива:** если Yandex stream сложен — переключить prod на ElevenLabs turbo (`TELEPHONY_STREAM_TTS_PROVIDER=elevenlabs`) как interim.

**Целевой `tts_ttfa_ms` p90:** **< 120 ms**.

---

### Фаза 3 — LLM ↔ TTS pipeline overlap (3–5 дней, −200…500 ms TTFA)

| # | Задача | Детали | Файлы |
|---|--------|--------|-------|
| 3.1 | `asyncio.Queue[str]` между LLM producer и TTS consumer | LLM пишет синтагмы, TTS читает параллельно | `stream_pipeline.py` |
| 3.2 | Первый синтагм — flush по таймауту **300 ms** даже без пунктуации | Не ждать запятую для длинных предложений | `streaming.py` |
| 3.3 | RAG: запускать `search_knowledge_base` параллельно с `process_phone_turn` prep | `asyncio.gather` | `stream_pipeline.py` |
| 3.4 | Small-talk fast path уже есть — расширить эвристику `_looks_like_small_talk` | Меньше ложных RAG-запросов | `stream_pipeline.py`, `search_service.py` |

**Целевой `llm_ttft_ms` + overlap:** первый звук не ждёт окончания TTS синтагмы 1 для старта синтагмы 2.

---

### Фаза 4 — Транспорт аудио (5–7 дней, −50…150 ms + CPU)

| # | Задача | Детали | Файлы |
|---|--------|--------|-------|
| 4.1 | Redis: batch нескольких PCM-фреймов в один `agent.audio.chunk` (например 100ms = 5×320 bytes) | Меньше pub/sub round-trips | `outbound_publish.py`, `agent_playback.ts` |
| 4.2 | Опционально: binary payload в Redis (не base64) или dedicated Redis Stream | −30% CPU на encode/decode | `outbound_publish.py`, `reply_hub.ts` |
| 4.3 | Gateway → Vox: рассмотреть raw binary WS вместо JSON+base64 per frame | Требует проверки Vox API | `vox_media.ts`, `voxengine/` |

**Приоритет ниже фаз 1–3** — выигрыш на TTFA меньше, на длинных ответах и CPU — заметнее.

---

### Фаза 5 — CRM и inbound (по необходимости)

| # | Задача | Детали |
|---|--------|--------|
| 5.1 | CRM filler threshold 1500 → **500 ms** | `TELEPHONY_CRM_FILLER_THRESHOLD_MS` |
| 5.2 | Прогрев filler PCM в RAM при `session.start` | `filler_audio.py`, `orchestrator_worker.py` |
| 5.3 | CRM: streaming partial tool results → ранний TTS «промежуточного» ответа | `stream_pipeline.py`, `template_runtime` |
| 5.4 | Inbound: `TURN_SILENCE_MS` 350 → **280–300** (A/B на стенде) | `telephony_media_gateway/src/config.ts` |
| 5.5 | STT: не пересоздавать gRPC сессию на каждую реплику, если API позволяет | `inbound_pipeline.ts`, `yandex_stream.ts` |

**Целевой CRM E2R:** первый звук (filler) **< 600 ms**, полный ответ — по `crm_execute_ms`.

---

## Порядок внедрения (рекомендуемый)

```
Фаза 0 (метрики)  →  Фаза 1 (quick wins)  →  Фаза 2 (TTS stream)
        ↓                                        ↓
   Baseline зафиксирован              Фаза 3 (LLM↔TTS overlap)
                                               ↓
                                    Фаза 4 (транспорт) — по мере нагрузки
                                    Фаза 5 (CRM/inbound) — параллельно с 3–4
```

---

## Риски и ограничения

| Изменение | Риск | Митигация |
|-----------|------|-----------|
| Меньше `TURN_SILENCE_MS` | Обрезание конца фразы | A/B, barge-in тесты |
| Меньше `SYNTAGMA_MIN_CHARS` | Рваная интонация | Минимум 6 символов + merge коротких хвостов |
| Yandex TTS stream refactor | Регрессия звука / endian | Golden audio tests, `test_telephony_tts.py` |
| LLM↔TTS queue | Race при barge-in | Существующий `stream_cancel` + drain queue |
| Batch Redis chunks | Задержка при barge-in | Flush queue on `agent.audio.end` / cancel |
| Ранний pacer без downlink.ready | Шум в первых ms | Grace 50ms или первые 2 фрейма в буфер |

---

## Критерии приёмки

### QA-агент (50 фраз RU, стенд РФ)

| Метрика | Сейчас (оценка) | Цель |
|---------|-----------------|------|
| `first_audio_ms` p90 | 1200–2500 | **600–900** |
| `llm_ttft_ms` p90 | 200–500 | **< 300** |
| `tts_ttfa_ms` p90 | 150–400 | **< 120** |
| `stt_final_ms` p90 | 400–700 | **< 400** (без снижения VAD на первом этапе) |
| Barge-in | работает | без регрессии |
| STT empty rate | < 15% | без роста |

### CRM-агент

| Метрика | Цель |
|---------|------|
| Filler audible | **< 500 ms** после `stt.final` |
| `crm_execute_ms` p90 | **< 1000** (без изменений логики tools) |

---

## Чеклист перед prod rollout

- [ ] `first_audio_ms` в метриках и алертах
- [ ] Debug fetch убран из gateway hot path
- [ ] `test_telephony_streaming*.py` зелёные
- [ ] `test_telephony_orchestrator_integration.py` зелёные
- [ ] Ручной звонок: welcome + 3 QA turns + barge-in
- [ ] p90 `first_audio_ms` на стенде ≤ цели
- [ ] Нет роста `stt_empty_rate` и false barge-in

---

## Результаты (заполнять после внедрения)

| Дата | Фаза | first_audio p50 | first_audio p90 | tts_ttfa p90 | llm_ttft p90 | Примечания |
|------|------|-----------------|-----------------|--------------|--------------|------------|
| — | baseline | | | | | |
| | | | | | | |

---

## Связанные файлы

| Компонент | Путь |
|-----------|------|
| Latency budget | `backend/app/telephony/latency_budget.py` |
| Orchestrator | `backend/app/telephony/orchestrator_worker.py` |
| Stream pipeline | `backend/app/telephony/stream_pipeline.py` |
| TTS | `backend/app/telephony/stream_tts.py`, `yandex_tts_stream.py` |
| LLM streaming | `backend/app/telephony/streaming.py` |
| Outbound publish | `backend/app/telephony/outbound_publish.py` |
| Media gateway config | `telephony_media_gateway/src/config.ts` |
| Inbound pipeline | `telephony_media_gateway/src/pipeline/inbound_pipeline.ts` |
| Playback | `telephony_media_gateway/src/orch/agent_playback.ts`, `agent_playback_pacer.ts` |
| Config | `backend/app/config/__init__.py` |
| Тесты | `backend/app/tests/test_telephony_latency_budget.py`, `test_telephony_streaming*.py` |
