/**
 * Voximplant WebSocket media JSON (call.sendMediaTo ↔ gateway).
 * @see https://voximplant.com/docs/guides/media-streams/websocket
 */

export interface VoxMediaMessage {
  event: 'media';
  media: { payload: string };
}

/** Voximplant may send start/stop before media frames — ignore without error. */
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

export function buildVoxStartMessage(): string {
  return JSON.stringify({
    event: 'start',
    start: {
      mediaFormat: {
        // Downlink to VoxEngine call is emitted as PCM16 LE bytes.
        // This format is consistently decoded by WebSocket->Call media bridge.
        encoding: 'audio/x-l16',
        sampleRate: 8000,
      },
    },
  });
}

export function buildVoxMediaMessage(payload: Buffer): string {
  return JSON.stringify({
    event: 'media',
    media: {
      payload: payload.toString('base64'),
    },
  });
}

export function buildVoxStopMessage(): string {
  return JSON.stringify({ event: 'stop' });
}
