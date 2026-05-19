export type CallSessionState =
  | 'IDLE'
  | 'RINGING'
  | 'GREETING'
  | 'LISTENING'
  | 'PROCESSING'
  | 'SPEAKING'
  | 'TRANSFER'
  | 'END';

const TRANSITIONS: Record<CallSessionState, CallSessionState[]> = {
  IDLE: ['RINGING', 'END'],
  RINGING: ['GREETING', 'LISTENING', 'TRANSFER', 'END'],
  GREETING: ['LISTENING', 'SPEAKING', 'TRANSFER', 'END'],
  LISTENING: ['PROCESSING', 'TRANSFER', 'END'],
  PROCESSING: ['SPEAKING', 'TRANSFER', 'END'],
  SPEAKING: ['LISTENING', 'TRANSFER', 'END'],
  TRANSFER: ['END'],
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
  turnCount = 0;
  answeredAtMs: number | null = null;
  /** Accumulated streaming STT (stage 5). */
  partialTranscript = '';
  partialConfidence: number | null = null;
  /** Stage 6: text being spoken when subscriber barges in. */
  interruptedAgentText = '';
  bargedInPending = false;
  utteranceStartedAtMs: number | null = null;
  backchannelPlayed = false;
  sttEmptyCount = 0;
  activeTurnAbort: AbortController | null = null;
  speakingStartedAtMs: number | null = null;

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

  incrementTurn(): void {
    this.turnCount += 1;
  }

  isMaxTurns(maxTurns: number): boolean {
    return this.turnCount >= Math.max(1, maxTurns);
  }

  isCallExpired(maxCallMinutes: number): boolean {
    if (this.answeredAtMs === null) {
      return false;
    }
    const limitMs = Math.max(1, maxCallMinutes) * 60 * 1000;
    return Date.now() - this.answeredAtMs >= limitMs;
  }

  transition(next: CallSessionState): void {
    const allowed = TRANSITIONS[this.state] || [];
    if (!allowed.includes(next) && this.state !== next) {
      if (this.state !== next) {
        throw new Error(`Invalid transition ${this.state} -> ${next}`);
      }
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
    case 'call.recording_ready':
      return 'PROCESSING';
    case 'call.partial_transcript':
      return 'LISTENING';
    case 'call.hangup':
      return 'END';
    default:
      return 'LISTENING';
  }
}
