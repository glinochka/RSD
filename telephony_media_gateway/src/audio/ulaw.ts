/** G.711 μ-law → PCM16 (8 kHz telephony). */

const ULAW_BIAS = 0x84;
const ULAW_CLIP = 32635;

function ulawExpand(uval: number): number {
  let u = (~uval) & 0xff;
  const sign = u & 0x80;
  let exponent = (u >> 4) & 0x07;
  let mantissa = u & 0x0f;
  mantissa = (mantissa << 3) + ULAW_BIAS;
  let sample = mantissa << exponent;
  sample -= ULAW_BIAS;
  return sign !== 0 ? -sample : sample;
}

/** Decode μ-law buffer to signed 16-bit PCM (little-endian samples as Int16). */
export function ulawToPcm16(ulaw: Buffer): Int16Array {
  const out = new Int16Array(ulaw.length);
  for (let i = 0; i < ulaw.length; i += 1) {
    out[i] = ulawExpand(ulaw[i]!);
  }
  return out;
}

/** Decode μ-law to little-endian PCM16 byte buffer. */
export function ulawToPcm16Buffer(ulaw: Buffer): Buffer {
  if (!ulaw.length) return Buffer.alloc(0);
  const samples = ulawToPcm16(ulaw);
  const out = Buffer.allocUnsafe(samples.length * 2);
  for (let i = 0; i < samples.length; i += 1) {
    out.writeInt16LE(samples[i]!, i * 2);
  }
  return out;
}

/** PCM16 → μ-law (for loopback / tests). */
export function pcm16ToUlaw(pcm: Int16Array): Buffer {
  const out = Buffer.allocUnsafe(pcm.length);
  for (let i = 0; i < pcm.length; i += 1) {
    out[i] = linearToUlaw(pcm[i]!);
  }
  return out;
}

function linearToUlaw(sample: number): number {
  const sign = sample < 0 ? 0x80 : 0;
  if (sample < 0) sample = -sample;
  if (sample > ULAW_CLIP) sample = ULAW_CLIP;
  sample += ULAW_BIAS;
  let exponent = 7;
  for (let expMask = 0x4000; (sample & expMask) === 0 && exponent > 0; exponent -= 1) {
    expMask >>= 1;
  }
  const mantissa = (sample >> (exponent + 3)) & 0x0f;
  return ~(sign | (exponent << 4) | mantissa) & 0xff;
}
