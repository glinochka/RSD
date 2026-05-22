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

export function createSpeechRecognition({ lang = 'ru-RU', onResult, onError }) {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang;
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  rec.continuous = false;
  rec.onresult = (event) => {
    const chunk = event.results?.[0]?.[0]?.transcript;
    if (chunk && onResult) onResult(String(chunk).trim());
  };
  rec.onerror = (event) => {
    if (onError) onError(event?.error || 'speech_error');
  };
  return rec;
}

let activeUtterance = null;
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
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  activeUtterance = null;
}

function speechTimeoutMs(text) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean).length;
  return Math.min(30_000, Math.max(4_000, words * 450 + 2_000));
}

export function speakPlainText(text, { lang = 'ru-RU', rate = 0.95 } = {}) {
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
