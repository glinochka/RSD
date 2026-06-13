#!/usr/bin/env node
/**
 * Unit test: energy VAD (no WS server, no Voximplant) — stage 9 CI.
 * Mirrors telephony_media_gateway/src/vad/energy_vad.ts logic in plain JS.
 */

class EnergyVad {
  constructor(frameMs, threshold) {
    this.sampleRate = 8000;
    this.frameSamples = Math.max(80, Math.floor((this.sampleRate * frameMs) / 1000));
    this.threshold = threshold;
  }

  processFrame(pcm) {
    if (pcm.length === 0) return { isSpeech: false, probability: 0 };
    let sum = 0;
    for (let i = 0; i < pcm.length; i += 1) {
      const s = pcm[i] / 32768;
      sum += s * s;
    }
    const rms = Math.sqrt(sum / pcm.length);
    const probability = Math.min(1, rms / this.threshold);
    return { isSpeech: probability >= 0.5, probability };
  }
}

function pcmTone(samples, amplitude = 8000) {
  const pcm = new Int16Array(samples);
  for (let i = 0; i < samples; i += 1) {
    pcm[i] = Math.round(amplitude * Math.sin((i / samples) * Math.PI * 8));
  }
  return pcm;
}

function pcmSilence(samples) {
  return new Int16Array(samples);
}

const vad = new EnergyVad(20, 0.02);
const frameSamples = vad.frameSamples;
let speechDetected = false;
let silenceDetected = false;

for (let i = 0; i < 12; i += 1) {
  if (vad.processFrame(pcmTone(frameSamples)).isSpeech) speechDetected = true;
}
for (let i = 0; i < 8; i += 1) {
  if (!vad.processFrame(pcmSilence(frameSamples)).isSpeech) silenceDetected = true;
}

if (!speechDetected || !silenceDetected) {
  console.error('VAD unit test failed', { speechDetected, silenceDetected });
  process.exit(1);
}
console.log(JSON.stringify({ ok: true, speechDetected, silenceDetected, frameSamples }));
process.exit(0);
