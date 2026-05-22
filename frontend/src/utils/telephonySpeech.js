/** Browser TTS/STT helpers for telephony voice preview */

const SSML_TAG_RE = /<[^>]+>/g;

export function stripSsml(text) {
  const raw = String(text || '').trim();
  if (!raw) return '';
  if (raw.startsWith('<speak')) {
    return raw.replace(SSML_TAG_RE, '').replace(/\s+/g, ' ').trim();
  }
  return raw;
}

export function speechRecognitionSupported() {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function createSpeechRecognition({
  lang = 'ru-RU',
  onResult,
  onError,
  continuous = false,
  interimResults = false,
  onSpeechStart,
} = {}) {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang;
  rec.interimResults = interimResults;
  rec.maxAlternatives = 1;
  rec.continuous = continuous;
  rec.onresult = (event) => {
    if (!onResult || !event.results?.length) return;
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      const chunk = result?.[0]?.transcript;
      if (!chunk) continue;
      onResult(String(chunk).trim(), { isFinal: Boolean(result.isFinal), index: i });
    }
  };
  rec.onerror = (event) => {
    if (onError) onError(event?.error || 'speech_error');
  };
  if (onSpeechStart) {
    rec.onspeechstart = onSpeechStart;
  }
  return rec;
}

/** Endpoint silence aligned with telephony_bridge (400–700 ms). */
const ENDPOINT_SILENCE_MS = 650;
const MIN_SPEECH_MS = 450;
const MAX_UTTERANCE_MS = 30_000;
const SPEECH_RMS_THRESHOLD = 0.015;
const SPEECH_ONSET_MS = 120;

function readAnalyserRms(analyser) {
  const data = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i += 1) {
    const sample = (data[i] - 128) / 128;
    sum += sample * sample;
  }
  return Math.sqrt(sum / data.length);
}

/**
 * Continuous mic listener: detects end-of-utterance by silence (like Voximplant record + endpointing).
 */
export function createVoiceActivityListener({
  onUtterance,
  onError,
  onSpeechStart,
  silenceMs = ENDPOINT_SILENCE_MS,
  minSpeechMs = MIN_SPEECH_MS,
  maxUtteranceMs = MAX_UTTERANCE_MS,
  rmsThreshold = SPEECH_RMS_THRESHOLD,
} = {}) {
  let stream = null;
  let audioContext = null;
  let analyser = null;
  let sourceNode = null;
  let capture = null;
  let rafId = 0;
  let active = false;
  let phase = 'idle';
  let loudSince = 0;
  let speechStartedAt = 0;
  let lastLoudAt = 0;
  let finalizing = false;

  const resetCapture = () => {
    capture = null;
    phase = 'idle';
    loudSince = 0;
    speechStartedAt = 0;
    lastLoudAt = 0;
  };

  const stopTracks = () => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch {
        /* ignore */
      }
      sourceNode = null;
    }
    if (audioContext) {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
    analyser = null;
  };

  const finalizeUtterance = async () => {
    if (finalizing || !capture) return;
    finalizing = true;
    const currentCapture = capture;
    resetCapture();
    let blob;
    try {
      blob = await currentCapture.stop();
    } catch {
      blob = new Blob([], { type: currentCapture.mimeType });
    }
    finalizing = false;
    if (blob.size >= 200 && onUtterance) {
      await onUtterance(blob, currentCapture.mimeType);
    }
  };

  const tick = () => {
    if (!active || !analyser || finalizing) {
      if (active) rafId = window.requestAnimationFrame(tick);
      return;
    }
    const now = Date.now();
    const rms = readAnalyserRms(analyser);
    const loud = rms >= rmsThreshold;

    if (phase === 'idle') {
      if (loud) {
        if (!loudSince) loudSince = now;
        if (now - loudSince >= SPEECH_ONSET_MS) {
          phase = 'recording';
          speechStartedAt = now;
          lastLoudAt = now;
          loudSince = 0;
          if (onSpeechStart) onSpeechStart();
          if (!capture && stream) {
            capture = createMediaRecorder(stream, { onError });
            if (capture) capture.start();
          }
        }
      } else {
        loudSince = 0;
      }
    } else if (phase === 'recording') {
      if (loud) {
        lastLoudAt = now;
      } else if (now - lastLoudAt >= silenceMs) {
        const spokeMs = lastLoudAt - speechStartedAt;
        if (spokeMs >= minSpeechMs) {
          void finalizeUtterance();
        } else {
          const discardCapture = capture;
          resetCapture();
          if (discardCapture) {
            void discardCapture.stop().catch(() => {});
          }
        }
        return;
      }
      if (now - speechStartedAt >= maxUtteranceMs) {
        void finalizeUtterance();
      }
    }
    rafId = window.requestAnimationFrame(tick);
  };

  return {
    isActive: () => active,
    async start() {
      if (active) return;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        if (onError) onError(err);
        return;
      }
      audioContext = new AudioContext();
      sourceNode = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      sourceNode.connect(analyser);
      active = true;
      resetCapture();
      rafId = window.requestAnimationFrame(tick);
    },
    stop() {
      active = false;
      if (rafId) {
        window.cancelAnimationFrame(rafId);
        rafId = 0;
      }
      resetCapture();
      stopTracks();
    },
  };
}

/**
 * Hands-free STT via Web Speech API (continuous), when supported in the browser.
 */
export function createContinuousSpeechListener({ onUtterance, onError, onSpeechStart } = {}) {
  let rec = null;
  let active = false;
  let restarting = false;

  const stop = () => {
    active = false;
    restarting = false;
    if (rec) {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
      rec = null;
    }
  };

  const startRecognition = () => {
    if (!active) return;
    rec = createSpeechRecognition({
      continuous: true,
      interimResults: true,
      onSpeechStart,
      onResult: (text, meta) => {
        if (!meta?.isFinal || !text) return;
        stop();
        if (onUtterance) void onUtterance(text);
      },
      onError: (code) => {
        if (code === 'aborted' || !active) return;
        if (code === 'no-speech' && active && !restarting) {
          restarting = true;
          window.setTimeout(() => {
            restarting = false;
            startRecognition();
          }, 300);
          return;
        }
        stop();
        if (onError) onError(code);
      },
    });
    if (!rec) {
      stop();
      if (onError) onError('unsupported');
      return;
    }
    try {
      rec.start();
    } catch (err) {
      stop();
      if (onError) onError(err);
    }
  };

  return {
    isActive: () => active,
    start() {
      if (active) return;
      active = true;
      startRecognition();
    },
    stop,
  };
}

let activeUtterance = null;
let activeAudio = null;
let voicesReady = false;

function ensureSpeechVoicesLoaded() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length > 0) {
    voicesReady = true;
    return;
  }
  if (voicesReady) return;
  const onVoices = () => {
    voicesReady = true;
    window.speechSynthesis.removeEventListener('voiceschanged', onVoices);
  };
  window.speechSynthesis.addEventListener('voiceschanged', onVoices);
  // Chrome on Android often needs a nudge before voices appear.
  try {
    window.speechSynthesis.getVoices();
  } catch {
    /* ignore */
  }
}

export function stopSpeaking() {
  if (activeAudio) {
    try {
      activeAudio.pause();
      activeAudio.src = '';
    } catch {
      /* ignore */
    }
    activeAudio = null;
  }
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  activeUtterance = null;
}

function playAudioBlob(blob) {
  return new Promise((resolve) => {
    if (!blob?.size || typeof window === 'undefined') {
      resolve();
      return;
    }
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (activeAudio?.src) {
        try {
          URL.revokeObjectURL(activeAudio.src);
        } catch {
          /* ignore */
        }
      }
      activeAudio = null;
      resolve();
    };
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    activeAudio = audio;
    const timer = window.setTimeout(finish, 90_000);
    const done = () => {
      window.clearTimeout(timer);
      finish();
    };
    audio.onended = done;
    audio.onerror = done;
    audio.play().catch(done);
  });
}

export async function playAudioBase64(base64, mimeType = 'audio/ogg') {
  if (!base64) return;
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mimeType || 'audio/ogg' });
  stopSpeaking();
  await playAudioBlob(blob);
}

/**
 * Озвучка реплики оператора: внешний TTS (Yandex/OpenAI) или fallback на браузер.
 */
export async function speakAgentLine(
  text,
  { agentId, useExternalTts = true, speakApi, onExternalTtsError } = {}
) {
  const plain = stripSsml(text);
  if (!plain) return { provider: 'none' };

  if (useExternalTts && agentId && speakApi) {
    try {
      const data = await speakApi({ agent_id: agentId, text: plain });
      if (data?.audio_base64) {
        await playAudioBase64(data.audio_base64, data.mime_type || 'audio/mpeg');
        return { provider: data.provider || 'external' };
      }
      throw new Error('Пустой ответ TTS с сервера');
    } catch (error) {
      if (onExternalTtsError) {
        onExternalTtsError(error);
      }
      console.warn('External TTS failed, falling back to browser speechSynthesis', error);
    }
  }

  await speakPlainText(plain);
  return { provider: 'browser' };
}

function speechTimeoutMs(text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean).length;
  return Math.min(30_000, Math.max(4_000, words * 450 + 2_000));
}

export function speakPlainText(text, { lang = 'ru-RU', rate = 0.96, pitch = 1.0 } = {}) {
  return new Promise((resolve) => {
    const plain = stripSsml(text);
    if (!plain || typeof window === 'undefined' || !window.speechSynthesis) {
      resolve();
      return;
    }
    ensureSpeechVoicesLoaded();
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      activeUtterance = null;
      resolve();
    };
    const timeoutMs = speechTimeoutMs(plain);
    const timer = window.setTimeout(finish, timeoutMs);

    stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(plain);
    utterance.lang = lang;
    utterance.rate = rate;
    if (typeof pitch === 'number' && pitch > 0) {
      utterance.pitch = pitch;
    }
    const voices = window.speechSynthesis.getVoices() || [];
    const ruVoice = voices.find((v) => (v.lang || '').toLowerCase().startsWith('ru'));
    if (ruVoice) utterance.voice = ruVoice;
    utterance.onend = () => {
      window.clearTimeout(timer);
      finish();
    };
    utterance.onerror = () => {
      window.clearTimeout(timer);
      finish();
    };
    activeUtterance = utterance;
    try {
      window.speechSynthesis.speak(utterance);
      // Some mobile browsers (incl. Android WebView) never fire onend; polling fallback.
      const startedAt = Date.now();
      const poll = window.setInterval(() => {
        if (settled) {
          window.clearInterval(poll);
          return;
        }
        const synth = window.speechSynthesis;
        if (!synth.speaking && !synth.pending && Date.now() - startedAt > 400) {
          window.clearInterval(poll);
          window.clearTimeout(timer);
          finish();
        }
      }, 250);
    } catch {
      window.clearTimeout(timer);
      finish();
    }
  });
}

export async function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = String(reader.result || '');
      const comma = dataUrl.indexOf(',');
      resolve(comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export function pickRecorderMimeType() {
  if (typeof MediaRecorder === 'undefined') return '';
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || '';
}

const RECORDER_TIMESLICE_MS = 250;

/**
 * Collect audio chunks reliably on Android (requires timeslice + requestData before stop).
 */
export function createMediaRecorder(stream, { onError } = {}) {
  const mime = pickRecorderMimeType();
  let recorder;
  try {
    recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  } catch (err) {
    if (onError) onError(err);
    return null;
  }
  const chunks = [];
  recorder.addEventListener('dataavailable', (e) => {
    if (e.data && e.data.size > 0) chunks.push(e.data);
  });
  recorder.addEventListener('error', () => {
    if (onError) onError(new Error('MediaRecorder error'));
  });

  const start = () => {
    chunks.length = 0;
    recorder.start(RECORDER_TIMESLICE_MS);
  };

  const stop = () =>
    new Promise((resolve) => {
      if (recorder.state === 'inactive') {
        resolve(new Blob(chunks, { type: recorder.mimeType || mime || 'audio/webm' }));
        return;
      }
      const finalize = () => {
        resolve(new Blob(chunks, { type: recorder.mimeType || mime || 'audio/webm' }));
      };
      recorder.addEventListener('stop', finalize, { once: true });
      try {
        if (recorder.state === 'recording' && typeof recorder.requestData === 'function') {
          recorder.requestData();
        }
      } catch {
        /* ignore */
      }
      recorder.stop();
    });

  return {
    recorder,
    mimeType: recorder.mimeType || mime || 'audio/webm',
    start,
    stop,
    isRecording: () => recorder.state === 'recording',
  };
}
