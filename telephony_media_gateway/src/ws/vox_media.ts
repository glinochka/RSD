/**
 * Voximplant WebSocket media JSON (call.sendMediaTo ↔ gateway).
 * @see https://voximplant.com/docs/guides/media-streams/websocket
 * @see ../../../docs/telephony/VOXIMPLANT_MEDIA_FORMAT.md
 *
 * ⚠️ КРИТИЧЕСКИ ВАЖНО: Формат сообщений строго определен документацией Voximplant.
 * Любые изменения могут привести к потере звука агента для абонента!
 *
 * Порядок событий (ОБЯЗАТЕЛЕН):
 * 1. Сначала отправляется event: "start" с mediaFormat
 * 2. Затем отправляются события event: "media" с аудио-данными
 * 3. В конце отправляется event: "stop"
 *
 * Без события "start" Voximplant не распознает медиа и звук не будет слышен!
 *
 * История: Ранее была проблема - звук агента не воспроизводился абоненту.
 * Причина: медиа передавалось в неверном формате.
 * Решение: строгое следование документации Voximplant.
 */

/**
 * Сообщение медиа-чанка от gateway к Voximplant.
 * Используется в событии event: "media" после отправки event: "start".
 *
 * Пример:
 * {
 *   "event": "media",
 *   "sequenceNumber": 2,
 *   "media": {
 *     "chunk": 1,
 *     "timestamp": 5,
 *     "payload": "no+JhoaJjpzSHxAKBgYJ...=="
 *   }
 * }
 */
export interface VoxMediaMessage {
  event: 'media';
  sequenceNumber: number;
  media: { chunk: number; timestamp: number; payload: string };
}

/** Per-session sequence counter for Voximplant media messages. */
class VoxSequenceCounter {
  private seq = 0;
  private chunk = 0;

  nextSeq(): number {
    return this.seq++;
  }

  nextChunk(): number {
    return this.chunk++;
  }

  reset(): void {
    this.seq = 0;
    this.chunk = 0;
  }
}

/** Map to track sequence counters per WebSocket connection. */
const wsSequenceCounters = new WeakMap<object, VoxSequenceCounter>();

function getCounter(ws: unknown): VoxSequenceCounter {
  let counter = wsSequenceCounters.get(ws as object);
  if (!counter) {
    counter = new VoxSequenceCounter();
    wsSequenceCounters.set(ws as object, counter);
  }
  return counter;
}

/**
 * События от Voximplant, которые нужно игнорировать без ошибки.
 * Voximplant отправляет эти события до/после медиа-фреймов.
 *
 * ВАЖНО: 'start' и 'stop' здесь — это события ОТ Voximplant (uplink),
 * а не те, что мы отправляем В Voximplant (downlink).
 */
const VOX_IGNORED_EVENTS = new Set(['start', 'stop', 'connected', 'playback_started', 'playback_finished']);

export function parseVoxMediaMessage(text: string): Buffer | null | 'ignore' {
  try {
    const data = JSON.parse(text) as { event?: string; media?: { payload?: string } };
    const event = String(data.event || '').trim().toLowerCase();
    if (!event) return null;
    if (VOX_IGNORED_EVENTS.has(event)) return 'ignore';
    if (event !== 'media' || !data.media?.payload) return null;
    return Buffer.from(data.media.payload, 'base64');
  } catch {
    return null;
  }
}

// =====================================================================================
// ФОРМАТ АУДИО ДЛЯ VOXIMPLANT WEBSOCKET MEDIA (рабочее решение, не менять без тестов!)
// =====================================================================================
// Voximplant WebSocket media JSON-протокол интерпретирует payload как PCM16/L16
// в порядке байт LITTLE-ENDIAN (подтверждено: WebSocket.MediaEventStarted encoding=PCM16
// + успешный звонок при отправке PCM16 LE как есть).
//
// ❌ Что НЕ работает (приводит к шуму/треску вместо речи):
//   - AUDIO_FORMAT=mulaw: объявление audio/x-mulaw в mediaFormat НЕ меняет интерпретацию
//     payload — Voximplant всё равно читает его как PCM16, и mulaw-байты звучат как шум.
//   - Конверсия PCM16 LE → BE (RFC 3551): Voximplant ждёт little-endian, BE даёт шум.
//
// ✅ Что работает: AUDIO_FORMAT=l16 (по умолчанию) + PCM16 LE БЕЗ конверсии endianness.
//
// История: формат уже ломали дважды (LE→BE в коммите 4aba41a, mulaw в 99580a8).
// Подробности: docs/telephony/VOXIMPLANT_MEDIA_FORMAT.md
//
// AUDIO_FORMAT=l16 (по умолчанию) - PCM16 (16-bit) little-endian, отправляется как есть.
// AUDIO_FORMAT=mulaw - μ-law (НЕ использовать, пока поддержка Voximplant не подтвердит прием mulaw payload).
const AUDIO_FORMAT = process.env.AUDIO_FORMAT || 'l16';

/**
 * Строит событие `start` для Voximplant WebSocket media.
 *
 * ⚠️ КРИТИЧЕСКИ ВАЖНО:
 * Это событие ОБЯЗАТЕЛЬНО должно быть отправлено перед любыми медиа-данными!
 * Без него Voximplant не распознает последующие сообщения как медиа,
 * и звук агента не будет слышен абоненту.
 *
 * Формат соответствует документации:
 * https://voximplant.com/docs/guides/media-streams/websocket
 *
 * @example
 * {
 *   "event": "start",
 *   "sequenceNumber": 0,
 *   "start": {
 *     "mediaFormat": {
 *       "encoding": "audio/l16",
 *       "sampleRate": 8000,
 *       "channels": 1
 *     }
 *   }
 * }
 *
 * @param ws - WebSocket соединение (опционально, для сброса счетчика)
 * @returns JSON-строка события start
 */
export function buildVoxStartMessage(ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  if (ws) {
    counter.reset();
  }

  const isMulaw = AUDIO_FORMAT === 'mulaw';
  const encoding = isMulaw ? 'audio/x-mulaw' : 'audio/l16';

  console.info(
    '[media-gateway] buildVoxStartMessage:',
    JSON.stringify({ format: AUDIO_FORMAT, encoding }),
  );

  return JSON.stringify({
    event: 'start',
    sequenceNumber: counter.nextSeq(),
    start: {
      mediaFormat: {
        encoding,
        sampleRate: 8000,
        channels: 1,
      },
    },
  });
}

/**
 * Строит событие `media` для передачи аудио-данных в Voximplant.
 *
 * ⚠️ КРИТИЧЕСКИ ВАЖНО:
 * Это событие должно отправляться ТОЛЬКО после отправки события `start`!
 * Иначе Voximplant не распознает данные как медиа.
 *
 * Формат соответствует документации Voximplant:
 * https://voximplant.com/docs/guides/media-streams/websocket
 *
 * @example
 * {
 *   "event": "media",
 *   "sequenceNumber": 2,
 *   "media": {
 *     "chunk": 1,
 *     "timestamp": 1623456789000,
 *     "payload": "no+JhoaJjpzSHxAKBgYJ...=="
 *   }
 * }
 *
 * @param payload - Бинарные аудио-данные (PCM16)
 * @param ws - WebSocket соединение (для отслеживания sequence)
 * @returns JSON-строка события media
 */
/**
 * Конвертирует PCM16 little-endian в big-endian (network byte order).
 * RFC 3551 определяет L16 как big-endian.
 * ElevenLabs и большинство систем отдают PCM16 в little-endian.
 */
function pcm16LeToBe(leBuffer: Buffer): Buffer {
  const beBuffer = Buffer.alloc(leBuffer.length);
  for (let i = 0; i < leBuffer.length; i += 2) {
    // Меняем порядок байт: [low, high] → [high, low]
    beBuffer[i] = leBuffer[i + 1];
    beBuffer[i + 1] = leBuffer[i];
  }
  return beBuffer;
}

// Отладка: логируем первые 16 байт как hex для анализа
function logPayloadBytes(label: string, buf: Buffer): void {
  if (buf.length === 0) return;
  const hexBytes = Array.from(buf.slice(0, 16))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join(' ');
  const leValues: number[] = [];
  const beValues: number[] = [];
  for (let i = 0; i + 1 < Math.min(buf.length, 16); i += 2) {
    leValues.push(buf.readInt16LE(i));
    beValues.push(buf.readInt16BE(i));
  }
  console.info(
    `[media-gateway] payload debug ${label}:`,
    JSON.stringify({
      hex: hexBytes,
      leSamples: leValues.slice(0, 4),
      beSamples: beValues.slice(0, 4),
    }),
  );
}

// Voximplant WebSocket media L16 payload интерпретируется как little-endian.
// Поэтому по умолчанию PCM16 LE отправляется КАК ЕСТЬ (рабочее поведение до коммита 4aba41a).
// Конверсию LE → BE (RFC 3551) можно включить только явно через FORCE_ENDIAN_BE=true,
// если поддержка Voximplant подтвердит, что нужен big-endian.
const FORCE_ENDIAN_BE = process.env.FORCE_ENDIAN_BE === 'true';

// Таблица линейного преобразования PCM16 → MULAW
// Based on ITU-T G.711
const MULAW_BIAS = 0x84;
const MULAW_CLIP = 32635;

function pcm16ToMulaw(sample: number): number {
  // Convert to signed 16-bit
  let sign = 0;
  if (sample < 0) {
    sign = 0x80;
    sample = -sample;
  }
  sample += MULAW_BIAS;
  if (sample > MULAW_CLIP) sample = MULAW_CLIP;

  let exponent = 7;
  for (let expMask = 0x4000; (sample & expMask) === 0 && exponent > 0; expMask >>= 1) {
    exponent--;
  }

  const mantissa = (sample >> (exponent + 3)) & 0x0f;
  const compressedByte = ~(sign | (exponent << 4) | mantissa) & 0xff;
  return compressedByte;
}

function pcm16LeToMulaw(leBuffer: Buffer): Buffer {
  const mulawBuffer = Buffer.alloc(leBuffer.length / 2);
  for (let i = 0, j = 0; i < leBuffer.length; i += 2, j++) {
    const sample = leBuffer.readInt16LE(i);
    mulawBuffer[j] = pcm16ToMulaw(sample);
  }
  return mulawBuffer;
}

export function buildVoxMediaMessage(payload: Buffer, ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  const timestamp = Date.now();

  // Отладка: смотрим входные данные
  logPayloadBytes('input', payload);

  let finalPayload: Buffer;
  const isMulaw = AUDIO_FORMAT === 'mulaw';

  if (isMulaw) {
    // Конвертируем PCM16 LE → MULAW (8-bit, 8kHz)
    finalPayload = pcm16LeToMulaw(payload);
    console.info('[media-gateway] format conv: PCM16 LE → MULAW');
  } else if (FORCE_ENDIAN_BE) {
    // Опционально: конвертируем LE → BE (только при FORCE_ENDIAN_BE=true)
    finalPayload = pcm16LeToBe(payload);
    console.info('[media-gateway] format conv: PCM16 LE → BE');
  } else {
    // Дефолт для l16: PCM16 LE как есть — Voximplant ожидает little-endian
    finalPayload = payload;
    console.info('[media-gateway] format conv: PCM16 LE (as-is)');
  }

  // Отладка: смотрим выходные данные
  logPayloadBytes('output', finalPayload);

  return JSON.stringify({
    event: 'media',
    sequenceNumber: counter.nextSeq(),
    media: {
      chunk: counter.nextChunk(),
      timestamp,
      payload: finalPayload.toString('base64'),
    },
  });
}

/**
 * Строит событие `stop` для завершения передачи медиа в Voximplant.
 *
 * Отправляется после передачи всех аудио-чанков для корректного
 * завершения медиа-потока.
 *
 * @example
 * {
 *   "event": "stop",
 *   "sequenceNumber": 100
 * }
 *
 * @param ws - WebSocket соединение (для отслеживания sequence)
 * @returns JSON-строка события stop
 */
export function buildVoxStopMessage(ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  return JSON.stringify({
    event: 'stop',
    sequenceNumber: counter.nextSeq(),
  });
}
