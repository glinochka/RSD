import { config } from '../config';

/** μ-law @ 8 kHz: bytes per 20 ms frame. */
export function expectedFrameBytes(frameMs: number = config.audioFrameMs): number {
  return Math.max(1, Math.floor((8000 * frameMs) / 1000));
}

export interface RtfSnapshot {
  frames: number;
  bytes: number;
  rtf: number;
  avg_bytes_per_frame: number;
}

/**
 * Tracks wall-clock vs audio duration for incoming μ-law (RTF ≈ processing / realtime).
 */
export class RtfTracker {
  private frames = 0;
  private bytes = 0;
  private lastAt = 0;
  private rtfSum = 0;

  constructor(private readonly frameMs: number = config.audioFrameMs) {}

  recordFrame(payloadBytes: number): RtfSnapshot {
    const now = Date.now();
    const audioMs = (payloadBytes / 8000) * 1000;
    let rtf = 0;
    if (this.lastAt > 0 && audioMs > 0) {
      const wallMs = now - this.lastAt;
      rtf = wallMs / audioMs;
      this.rtfSum += rtf;
    }
    this.lastAt = now;
    this.frames += 1;
    this.bytes += payloadBytes;

    return {
      frames: this.frames,
      bytes: this.bytes,
      rtf: Math.round(rtf * 1000) / 1000,
      avg_bytes_per_frame: this.frames > 0 ? Math.round(this.bytes / this.frames) : 0,
    };
  }

  averageRtf(): number {
    return this.frames > 1 ? Math.round((this.rtfSum / (this.frames - 1)) * 1000) / 1000 : 0;
  }
}

export function shouldLogRtf(frames: number): boolean {
  if (config.logLevel === 'silent') return false;
  return frames === 1 || frames % 50 === 0;
}
