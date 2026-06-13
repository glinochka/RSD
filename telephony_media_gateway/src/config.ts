import path from 'path';

const sttProviderRaw = (process.env.STT_PROVIDER || 'yandex').trim().toLowerCase();
const nodeEnv = (process.env.NODE_ENV || 'development').trim().toLowerCase();

if (nodeEnv === 'production' && sttProviderRaw === 'mock') {
  throw new Error('STT_PROVIDER=mock is not allowed in production');
}

export const config = {
  port: Number.parseInt(process.env.PORT || '8200', 10),
  wsPath: (process.env.TELEPHONY_MEDIA_WS_PATH || '/ws').trim() || '/ws',
  maxControlMessageBytes: Math.max(
    1024,
    Number.parseInt(process.env.TELEPHONY_MEDIA_MAX_CONTROL_BYTES || '65536', 10),
  ),
  audioFrameMs: Math.max(
    10,
    Math.min(50, Number.parseInt(process.env.TELEPHONY_MEDIA_AUDIO_FRAME_MS || '20', 10)),
  ),
  logLevel: (process.env.TELEPHONY_MEDIA_LOG_LEVEL || 'info').trim().toLowerCase(),
  loopbackTransport: (
    process.env.TELEPHONY_MEDIA_LOOPBACK_TRANSPORT || 'vox'
  ).trim().toLowerCase() as 'vox' | 'binary' | 'both',
  loopbackMode: (process.env.TELEPHONY_MEDIA_LOOPBACK_MODE || 'echo').trim().toLowerCase() as
    | 'echo'
    | 'silence',

  /** Stage 3: VAD + streaming STT pipeline (disable for stage-2 loopback only). */
  pipelineEnabled: (process.env.TELEPHONY_MEDIA_PIPELINE_ENABLED || 'true').trim().toLowerCase() !== 'false',
  sttProvider: (['yandex', 'deepgram', 'mock'].includes(sttProviderRaw)
    ? sttProviderRaw
    : 'mock') as 'yandex' | 'deepgram' | 'mock',
  sttLanguage: (process.env.TELEPHONY_STT_LANGUAGE || 'ru-RU').trim(),
  /** Turn silence detection - reduced for faster response. */
  turnSilenceMs: Math.max(
    200,
    Math.min(2000, Number.parseInt(process.env.TURN_SILENCE_MS || '350', 10)),
  ),
  vadModelPath: (
    process.env.VAD_MODEL_PATH || path.join(process.cwd(), 'models', 'silero_vad.onnx')
  ).trim(),
  vadSpeechThreshold: Math.max(
    0.1,
    Math.min(0.99, Number.parseFloat(process.env.VAD_SPEECH_THRESHOLD || '0.35')),
  ),
  vadEnergyThreshold: Number.parseFloat(process.env.VAD_ENERGY_THRESHOLD || '0.02'),
  sttPartialLogEvery: Math.max(1, Number.parseInt(process.env.STT_PARTIAL_LOG_EVERY || '5', 10)),
  /** Wait for provider final after VAD utterance end (ms). Reduced for lower latency. */
  sttFinalWaitMs: Math.max(20, Number.parseInt(process.env.STT_FINAL_WAIT_MS || '50', 10)),

  yandexSpeechkitApiKey: (process.env.YANDEX_SPEECHKIT_API_KEY || '').trim(),
  yandexSpeechkitFolderId: (process.env.YANDEX_SPEECHKIT_FOLDER_ID || '').trim(),
  deepgramApiKey: (process.env.DEEPGRAM_API_KEY || '').trim(),

  /** Stage 4: Redis pub/sub to dialog orchestrator */
  redisUrl: (process.env.REDIS_URL || '').trim(),
  orchEventsEnabled: (process.env.TELEPHONY_ORCH_EVENTS_ENABLED || 'true').trim().toLowerCase() !== 'false',
  orchEventsChannel: (process.env.TELEPHONY_ORCH_EVENTS_CHANNEL || 'telephony:orch:events').trim(),
  orchRepliesChannel: (process.env.TELEPHONY_ORCH_REPLIES_CHANNEL || 'telephony:orch:replies').trim(),

  /** Stage 6: barge-in while agent.audio.* is active */
  bargeInEnabled: (process.env.TELEPHONY_BARGE_IN_ENABLED || 'true').trim().toLowerCase() !== 'false',
  /** Ignore barge-in during the first playback milliseconds after agent.audio.start.
   *  Reduced from 600ms to 300ms for lower latency (target 1.5-2s response time). */
  bargeInPlaybackGraceMs: Math.max(
    0,
    Math.min(5000, Number.parseInt(process.env.TELEPHONY_BARGE_IN_PLAYBACK_GRACE_MS || '300', 10)),
  ),
  /** Ignore barge-in shortly after DTMF to avoid tone-as-speech false positives. */
  bargeInDtmfSuppressMs: Math.max(
    0,
    Math.min(5000, Number.parseInt(process.env.TELEPHONY_BARGE_IN_DTMF_SUPPRESS_MS || '1000', 10)),
  ),
  /** Fallback: unblock playout if downlink.ready was not observed in time. */
  downlinkReadyTimeoutMs: Math.max(
    0,
    Math.min(5000, Number.parseInt(process.env.TELEPHONY_DOWNLINK_READY_TIMEOUT_MS || '250', 10)),
  ),
  /** Consecutive VAD speech frames (~20ms each) before barge_in */
  bargeInSpeechFrames: Math.max(1, Math.min(10, Number.parseInt(process.env.TELEPHONY_BARGE_IN_SPEECH_FRAMES || '2', 10))),
};
