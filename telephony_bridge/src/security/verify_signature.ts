import crypto from 'crypto';

export function verifyWebhookSignature(params: {
  secret: string;
  timestamp: string;
  connectionId: number;
  rawBody: Buffer;
  signatureHex: string;
  ttlSeconds: number;
}): boolean {
  const { secret, timestamp, connectionId, rawBody, signatureHex, ttlSeconds } = params;
  const ts = Number.parseInt(timestamp, 10);
  if (!Number.isFinite(ts)) {
    return false;
  }
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - ts) > ttlSeconds) {
    return false;
  }
  const prefix = Buffer.from(`v1\n${timestamp}\n${connectionId}\n`, 'utf8');
  const message = Buffer.concat([prefix, rawBody]);
  const expected = crypto.createHmac('sha256', secret).update(message).digest('hex');
  const provided = (signatureHex || '').trim().toLowerCase();
  if (expected.length !== provided.length) {
    return false;
  }
  return crypto.timingSafeEqual(Buffer.from(expected, 'utf8'), Buffer.from(provided, 'utf8'));
}
