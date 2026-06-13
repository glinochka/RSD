export interface SttPartial {
  text: string;
  confidence?: number;
  stable?: boolean;
}

export interface StreamingSttSession {
  pushAudio(pcm16: Buffer): void;
  close(): void;
  readonly onPartial: (cb: (p: SttPartial) => void) => void;
  readonly onFinal: (cb: (p: SttPartial) => void) => void;
  readonly onError: (cb: (err: Error) => void) => void;
}

export interface StreamingSttProvider {
  readonly name: string;
  startStream(opts: { sampleRate: number; language: string }): StreamingSttSession;
}
