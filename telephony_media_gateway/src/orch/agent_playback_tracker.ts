/**
 * Tracks agent TTS playback window for barge-in (stage 6).
 */

export interface AgentPlaybackState {
  active: boolean;
  startedAt: number;
  bargeInFired: boolean;
}

const byCallId = new Map<string, AgentPlaybackState>();

export function markAgentPlaybackStart(callId: string): void {
  const id = callId.trim();
  if (!id) return;
  byCallId.set(id, { active: true, startedAt: Date.now(), bargeInFired: false });
}

export function markAgentPlaybackEnd(callId: string): void {
  const id = callId.trim();
  if (!id) return;
  const prev = byCallId.get(id);
  if (prev) {
    byCallId.set(id, { ...prev, active: false });
  }
}

export function isAgentPlaybackActive(callId: string): boolean {
  const st = byCallId.get(callId.trim());
  return Boolean(st?.active && !st.bargeInFired);
}

export function markBargeInFired(callId: string): boolean {
  const id = callId.trim();
  const st = byCallId.get(id);
  if (!st || st.bargeInFired) return false;
  byCallId.set(id, { ...st, active: false, bargeInFired: true });
  return true;
}

export function agentPlaybackStartedAt(callId: string): number {
  return byCallId.get(callId.trim())?.startedAt ?? 0;
}

export function clearAgentPlayback(callId: string): void {
  byCallId.delete(callId.trim());
}

export function isPlaybackBlocked(callId: string): boolean {
  const st = byCallId.get(callId.trim());
  return Boolean(st?.bargeInFired);
}
