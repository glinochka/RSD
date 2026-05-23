import Redis from 'ioredis';

import { config } from '../config';

let client: Redis | null = null;

function getClient(): Redis | null {
  if (!config.orchEventsEnabled || !config.redisUrl) {
    return null;
  }
  if (!client) {
    client = new Redis(config.redisUrl, { maxRetriesPerRequest: 2, lazyConnect: true });
  }
  return client;
}

export async function publishOrchEvent(payload: Record<string, unknown>): Promise<void> {
  const redis = getClient();
  if (!redis) return;
  try {
    if (redis.status !== 'ready') {
      await redis.connect();
    }
    await redis.publish(config.orchEventsChannel, JSON.stringify(payload));
  } catch (err) {
    console.warn(
      '[media-gateway] orch publish failed',
      err instanceof Error ? err.message : err,
    );
  }
}
