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
  return JSON.stringify({
    event: 'start',
    sequenceNumber: counter.nextSeq(),
    start: {
      mediaFormat: {
        // Voximplant ожидает PCM16 (16-bit signed integer, 8kHz, mono)
        // НЕ ИЗМЕНЯЙТЕ этот формат без консультации с поддержкой Voximplant!
        encoding: 'audio/l16',
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

export function buildVoxMediaMessage(payload: Buffer, ws?: unknown): string {
  const counter = ws ? getCounter(ws) : new VoxSequenceCounter();
  const timestamp = Date.now();
  // Конвертируем LE → BE, т.к. audio/l16 требует big-endian (RFC 3551)
  const bePayload = pcm16LeToBe(payload);
  return JSON.stringify({
    event: 'media',
    sequenceNumber: counter.nextSeq(),
    media: {
      chunk: counter.nextChunk(),
      timestamp,
      payload: bePayload.toString('base64'),
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
