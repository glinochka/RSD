import type { CallSession } from './call_session';
import { RedisSessionStore } from './redis_store';

export interface SessionStore {
  get(callId: string, connectionId: number, callerE164: string): Promise<CallSession | undefined>;
  set(session: CallSession): Promise<void>;
  delete(callId: string, connectionId: number): Promise<void>;
}

export class MemorySessionStore implements SessionStore {
  private readonly map = new Map<string, CallSession>();

  private key(callId: string, connectionId: number): string {
    return `${connectionId}:${callId}`;
  }

  async get(callId: string, connectionId: number, _callerE164: string): Promise<CallSession | undefined> {
    return this.map.get(this.key(callId, connectionId));
  }

  async set(session: CallSession): Promise<void> {
    this.map.set(this.key(session.callId, session.connectionId), session);
  }

  async delete(callId: string, connectionId: number): Promise<void> {
    this.map.delete(this.key(callId, connectionId));
  }
}

export function createSessionStore(kind: string, redisUrl?: string): SessionStore {
  if (kind === 'redis') {
    const url = (redisUrl || process.env.REDIS_URL || '').trim();
    if (!url) {
      throw new Error('REDIS_URL is required when TELEPHONY_SESSION_STORE=redis');
    }
    return new RedisSessionStore(url);
  }
  return new MemorySessionStore();
}
