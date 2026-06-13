#!/usr/bin/env node
/**
 * Download Silero VAD ONNX model into ./models/silero_vad.onnx
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, '..', 'models');
const outFile = path.join(outDir, 'silero_vad.onnx');
const url =
  'https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx';

async function main() {
  fs.mkdirSync(outDir, { recursive: true });
  console.log('Downloading', url);
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status} ${res.statusText}`);
  }
  const buf = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outFile, buf);
  console.log('Saved', outFile, `(${buf.length} bytes)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
