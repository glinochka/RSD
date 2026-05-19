import { CallSession } from './call_session';
import type { SessionStore } from './store';

type SessionPayload = {
  state: CallSession['state'];
  callDbId: number | null;
  resolved: CallSession['resolved'];
  disclaimerPlayed: boolean;
  turnCount: number;
  answeredAtMs: number | null;
  partialTranscript: string;
  partialConfidence: number | null;
  callerE164: string;
};

const SESSION_TTL_SEC = 3600;

export class RedisSessionStore implements SessionStore {
  private client: import('ioredis').default | null = null;

  constructor(private readonly redisUrl: string) {}

  private async getClient(): Promise<import('ioredis').default> {
    if (this.client) {
      return this.client;
    }
    const Redis = (await import('ioredis')).default;
    this.client = new Redis(this.redisUrl, { maxRetriesPerRequest: 2, lazyConnect: true });
    await this.client.connect();
    return this.client;
  }

  private key(callId: string, connectionId: number): string {
    return `telephony:session:${connectionId}:${callId}`;
  }

  private serialize(session: CallSession): string {
    const payload: SessionPayload = {
      state: session.state,
      callDbId: session.callDbId,
      resolved: session.resolved,
      disclaimerPlayed: session.disclaimerPlayed,
      turnCount: session.turnCount,
      answeredAtMs: session.answeredAtMs,
      partialTranscript: session.partialTranscript,
      partialConfidence: session.partialConfidence,
      callerE164: session.callerE164,
    };
    return JSON.stringify(payload);
  }

  private hydrate(callId: string, connectionId: number, raw: string): CallSession {
    const data = JSON.parse(raw) as SessionPayload;
    const session = new CallSession(callId, connectionId, data.callerE164 || '+00000000000');
    session.state = data.state;
    session.callDbId = data.callDbId;
    session.resolved = data.resolved;
    session.disclaimerPlayed = data.disclaimerPlayed;
    session.turnCount = data.turnCount;
    session.answeredAtMs = data.answeredAtMs;
    session.partialTranscript = data.partialTranscript || '';
    session.partialConfidence = data.partialConfidence ?? null;
    return session;
  }

  async get(callId: string, connectionId: number, callerE164: string): Promise<CallSession | undefined> {
    const client = await this.getClient();
    const raw = await client.get(this.key(callId, connectionId));
    if (!raw) {
      return undefined;
    }
    const session = this.hydrate(callId, connectionId, raw);
    if (!session.callerE164 || session.callerE164 === '+00000000000') {
      session.callerE164 = callerE164;
    }
    return session;
  }

  async set(session: CallSession): Promise<void> {
    const client = await this.getClient();
    await client.setex(this.key(session.callId, session.connectionId), SESSION_TTL_SEC, this.serialize(session));
  }

  async delete(callId: string, connectionId: number): Promise<void> {
    const client = await this.getClient();
    await client.del(this.key(callId, connectionId));
  }
}
