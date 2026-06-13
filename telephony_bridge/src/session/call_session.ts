export type CallSessionState = 'IDLE' | 'RINGING' | 'GREETING' | 'END';

const TRANSITIONS: Record<CallSessionState, CallSessionState[]> = {
  IDLE: ['RINGING', 'END'],
  RINGING: ['GREETING', 'END'],
  GREETING: ['END'],
  END: [],
};

export type ResolvedChannelConfig = {
  welcome_message?: string | null;
  voice_id?: string;
  record_calls?: boolean;
  disclaimer_played?: boolean;
  operator_transfer_e164?: string;
};

export class CallSession {
  state: CallSessionState = 'IDLE';
  callDbId: number | null = null;
  resolved: ResolvedChannelConfig | null = null;
  disclaimerPlayed = false;
  answeredAtMs: number | null = null;

  constructor(
    readonly callId: string,
    readonly connectionId: number,
    public callerE164: string,
  ) {}

  markAnswered(): void {
    if (this.answeredAtMs === null) {
      this.answeredAtMs = Date.now();
    }
  }

  transition(next: CallSessionState): void {
    const allowed = TRANSITIONS[this.state] || [];
    if (!allowed.includes(next) && this.state !== next) {
      throw new Error(`Invalid transition ${this.state} -> ${next}`);
    }
    this.state = next;
  }
}

export function initialStateForEvent(event: string): CallSessionState {
  switch (event) {
    case 'call.inbound':
      return 'RINGING';
    case 'call.answered':
      return 'GREETING';
    case 'call.hangup':
      return 'END';
    default:
      return 'RINGING';
  }
}
