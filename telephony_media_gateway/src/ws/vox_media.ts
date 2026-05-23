/**
 * Voximplant WebSocket media JSON (call.sendMediaTo → gateway).
 * @see https://voximplant.com/docs/guides/media-streams/websocket
 */

export interface VoxMediaMessage {
  event: 'media';
  media: { payload: string; tag?: string };
}

export function parseVoxMediaMessage(text: string): Buffer | null {
  try {
    const data = JSON.parse(text) as { event?: string; media?: { payload?: string } };
    if (data.event !== 'media' || !data.media?.payload) return null;
    return Buffer.from(data.media.payload, 'base64');
  } catch {
    return null;
  }
}

export function buildVoxMediaMessage(payload: Buffer): string {
  return JSON.stringify({
    event: 'media',
    media: {
      payload: payload.toString('base64'),
      tag: 'rsd_loopback',
    },
  });
}
