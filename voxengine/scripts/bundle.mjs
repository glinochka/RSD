#!/usr/bin/env node
/**
 * Bundle rsd_inbound.js + lib/* into a single file for Voximplant Cloud IDE.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const HEADER = `/**
 * RSD inbound — единый сценарий для Voximplant Cloud IDE.
 * Скопируйте всё содержимое в сценарий rsd_inbound (один файл, без require).
 * На routing rule привяжите только rsd_inbound.
 *
 * Источник: rsd_inbound.js + lib/rsd_control.js + lib/rsd_media_gateway.js + lib/rsd_transfer.js
 * Обновляйте через: node voxengine/scripts/bundle.mjs
 *
 * Secrets приложения (обязательно для входящего PSTN — customData rule не передаётся):
 *   RSD_CONNECTION_ID, RSD_WEBHOOK_SECRET, RSD_WEBHOOK_BASE_URL, TELEPHONY_MEDIA_WS_URL
 *   RSD_REQUIRE_EXTENSION=true — приветствие «введите 4 цифры»
 * script_custom_data rule — только при ручном StartScenarios, не при звонке на номер
 */

Logger.write('[rsd] scenario loaded (bundled rsd_inbound)');

VoxEngine.addEventListener(AppEvents.Started, function () {
  Logger.write('[rsd] Application.Started customData=' + String(VoxEngine.customData() || ''));
});

`;

function stripModuleExports(source) {
  return source
    .replace(/\nmodule\.exports\s*=\s*\{[\s\S]*?\};\s*$/m, '\n')
    .replace(/^\/\*\*[\s\S]*?\*\/\s*\n/m, '');
}

function loadLib(name) {
  const file = path.join(root, 'lib', name);
  const raw = fs.readFileSync(file, 'utf8');
  const body = stripModuleExports(raw);
  return `\n// --- lib/${name} ---\n${body}\n`;
}

function removeFunctionBlock(source, fnName) {
  const marker = `function ${fnName}`;
  const start = source.indexOf(marker);
  if (start === -1) return source;
  const braceStart = source.indexOf('{', start);
  if (braceStart === -1) return source;
  let depth = 0;
  for (let i = braceStart; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') {
      depth--;
      if (depth === 0) {
        return source.slice(0, start) + source.slice(i + 1).replace(/^\s*\n/, '');
      }
    }
  }
  return source;
}

function loadMain() {
  let raw = fs.readFileSync(path.join(root, 'rsd_inbound.js'), 'utf8');
  raw = raw.replace(/^\/\*\*[\s\S]*?\*\/\s*\n/m, '');
  raw = removeFunctionBlock(raw, 'requireRsdModule');
  raw = raw.replace(
    /var rsdControl = requireRsdModule\('rsd_control'\);\s*\nvar rsdMedia = requireRsdModule\('rsd_media_gateway'\);\s*\nvar rsdTransfer = requireRsdModule\('rsd_transfer'\);\s*\n/m,
    [
      "var rsdControl = { postControlEvent: postControlEvent };",
      "var rsdMedia = {",
      "  connectMediaGateway: connectMediaGateway,",
      "  sendDtmfToGateway: sendDtmfToGateway,",
      "  sendSessionEnd: sendSessionEnd,",
      "};",
      "var rsdTransfer = { transferToPstn: transferToPstn };",
      "",
    ].join('\n'),
  );
  return `\n// --- rsd_inbound (main) ---\n${raw}`;
}

const out =
  HEADER +
  loadLib('rsd_control.js') +
  loadLib('rsd_transfer.js') +
  loadLib('rsd_media_gateway.js') +
  loadMain();

const outPath = path.join(root, 'rsd_inbound.bundled.js');
fs.writeFileSync(outPath, out, 'utf8');
console.log('Wrote', outPath, `(${out.length} bytes)`);
