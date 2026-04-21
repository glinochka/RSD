const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');

const APP_TITLE = 'WhatsApp Userbot Bridge';
const APP_ENV = (process.env.WA_USERBOT_ENV || 'production').trim().toLowerCase();
const AUTH_TTL_SECONDS = Number.parseInt(process.env.WA_USERBOT_AUTH_TTL_SECONDS || '600', 10);
const AUTH_MAX_ATTEMPTS = Number.parseInt(process.env.WA_USERBOT_AUTH_MAX_ATTEMPTS || '5', 10);
const BRIDGE_API_KEY = (process.env.WA_USERBOT_BRIDGE_API_KEY || '').trim();
const SESSION_SECRET = process.env.WA_USERBOT_SESSION_SECRET || '';
const REQUEST_WINDOW_SECONDS = Number.parseFloat(process.env.WA_USERBOT_REQUEST_WINDOW_SECONDS || '60');
const REQUEST_LIMIT = Number.parseInt(process.env.WA_USERBOT_REQUESTS_PER_PHONE_LIMIT || '5', 10);
const VERIFY_WINDOW_SECONDS = Number.parseFloat(process.env.WA_USERBOT_VERIFY_WINDOW_SECONDS || '60');
const VERIFY_LIMIT = Number.parseInt(process.env.WA_USERBOT_VERIFY_PER_PHONE_LIMIT || '10', 10);
const DATA_DIR = process.env.WA_USERBOT_DATA_DIR || '/data/wa-auth';
const HTTP_PORT = Number.parseInt(process.env.PORT || '8090', 10);
const WA_BROWSER_SIGNATURE = [
  String(process.env.WA_USERBOT_BROWSER_PLATFORM || 'Windows').trim() || 'Windows',
  String(process.env.WA_USERBOT_BROWSER_NAME || 'Edge').trim() || 'Edge',
  String(process.env.WA_USERBOT_BROWSER_VERSION || '127.0.0.0').trim() || '127.0.0.0',
];

if (!BRIDGE_API_KEY) {
  throw new Error('WA_USERBOT_BRIDGE_API_KEY must be set');
}
if (!SESSION_SECRET || SESSION_SECRET.length < 32) {
  throw new Error('WA_USERBOT_SESSION_SECRET must be set and at least 32 chars');
}
if (APP_ENV === 'production' && process.env.WA_USERBOT_DEV_EXPOSE_CODE === 'true') {
  throw new Error('WA_USERBOT_DEV_EXPOSE_CODE=true is forbidden in production');
}

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });
const app = express();
app.use(express.json({ limit: '256kb' }));

const authSessions = new Map();
const requestRate = new Map();
const verifyRate = new Map();

function nowMs() {
  return Date.now();
}

function normalizePhone(phone) {
  const raw = String(phone || '').trim();
  const digits = raw.replace(/\D/g, '');
  if (digits.length < 5) {
    const error = new Error('Некорректный номер WhatsApp');
    error.status = 422;
    throw error;
  }
  return `+${digits}`;
}

function normalizeCode(value) {
  const text = String(value || '').trim();
  const compact = text.replace(/\D/g, '');
  return compact || text;
}

function enforceApiKey(req, res, next) {
  const key = String(req.header('X-API-Key') || '').trim();
  if (key !== BRIDGE_API_KEY) {
    return res.status(401).json({ detail: 'Invalid bridge API key' });
  }
  return next();
}

function rateLimit(map, key, limit, windowSeconds, detail) {
  const ts = nowMs();
  const border = ts - Math.max(1, windowSeconds) * 1000;
  const list = (map.get(key) || []).filter((v) => v > border);
  if (list.length >= Math.max(1, limit)) {
    const error = new Error(detail);
    error.status = 429;
    throw error;
  }
  list.push(ts);
  map.set(key, list);
}

function cleanupExpired() {
  const ts = nowMs();
  for (const [authId, session] of authSessions.entries()) {
    if (session.expiresAt <= ts) {
      if (session.sock) {
        try {
          session.sock.end(new Error('auth expired'));
        } catch {
          // ignore
        }
      }
      authSessions.delete(authId);
    }
  }
}

function signBundle(bundle) {
  const payload = Buffer.from(JSON.stringify(bundle), 'utf-8');
  const signature = crypto.createHmac('sha256', SESSION_SECRET).update(payload).digest('base64url');
  return Buffer.from(
    JSON.stringify({
      v: 1,
      payload: payload.toString('base64url'),
      signature,
    }),
    'utf-8'
  ).toString('base64url');
}

async function readSessionFiles(sessionDir) {
  const files = await fs.readdir(sessionDir, { withFileTypes: true });
  const output = {};
  for (const entry of files) {
    if (!entry.isFile()) continue;
    const abs = path.join(sessionDir, entry.name);
    const content = await fs.readFile(abs, 'utf-8');
    output[entry.name] = content;
  }
  return output;
}

async function waitForPairingCode(sock, phoneDigits, timeoutMs = 30000) {
  const start = nowMs();
  let lastError = null;
  while (nowMs() - start < timeoutMs) {
    try {
      const code = await sock.requestPairingCode(phoneDigits);
      if (code) return code;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
  throw new Error(`Не удалось получить pairing code: ${lastError ? lastError.message : 'timeout'}`);
}

async function createAuthSession(phoneNumber) {
  const authId = `wauth_${crypto.randomBytes(18).toString('base64url')}`;
  const sessionDir = path.join(DATA_DIR, authId);
  await fs.mkdir(sessionDir, { recursive: true });

  const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
  const versionInfo = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 0] }));
  const sock = makeWASocket({
    auth: state,
    version: versionInfo.version,
    logger: pino({ level: 'silent' }),
    markOnlineOnConnect: false,
    printQRInTerminal: false,
    browser: WA_BROWSER_SIGNATURE,
  });

  const session = {
    authId,
    phoneNumber,
    phoneDigits: phoneNumber.replace(/\D/g, ''),
    sessionDir,
    sock,
    pairingCode: null,
    status: 'pending',
    user: null,
    attemptsLeft: AUTH_MAX_ATTEMPTS,
    createdAt: nowMs(),
    expiresAt: nowMs() + AUTH_TTL_SECONDS * 1000,
    lastError: null,
  };
  authSessions.set(authId, session);

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    if (update.connection === 'open') {
      if (sock.authState?.creds?.registered) {
        session.status = 'paired';
      } else {
        session.status = 'connected';
      }
      session.user = sock.user || null;
    } else if (update.connection === 'close') {
      const statusCode = new Boom(update.lastDisconnect?.error)?.output?.statusCode;
      if (statusCode && statusCode >= 400 && statusCode < 500) {
        session.status = 'failed';
        session.lastError = `WhatsApp disconnect (${statusCode})`;
      }
    }
  });

  session.pairingCode = await waitForPairingCode(sock, session.phoneDigits);
  return session;
}

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: APP_TITLE, env: APP_ENV });
});

app.post('/auth/request_code', enforceApiKey, async (req, res) => {
  try {
    cleanupExpired();
    const phoneNumber = normalizePhone(req.body?.phone_number);
    rateLimit(
      requestRate,
      `request:${phoneNumber}`,
      REQUEST_LIMIT,
      REQUEST_WINDOW_SECONDS,
      'Слишком много запросов кода для этого номера. Попробуйте позже.'
    );

    const session = await createAuthSession(phoneNumber);
    return res.status(200).json({
      auth_id: session.authId,
      delivery: 'pairing_code',
      hint:
        'Откройте WhatsApp на телефоне -> Связанные устройства -> Привязать устройство и введите pairing code.',
      pairing_code: session.pairingCode,
      expires_in_seconds: AUTH_TTL_SECONDS,
    });
  } catch (error) {
    logger.error({ err: error }, 'request_code failed');
    return res.status(error.status || 500).json({ detail: error.message || 'request_code failed' });
  }
});

app.post('/auth/verify_code', enforceApiKey, async (req, res) => {
  try {
    cleanupExpired();
    const authId = String(req.body?.auth_id || '').trim();
    const phoneNumber = normalizePhone(req.body?.phone_number);
    const code = normalizeCode(req.body?.code);
    if (!authId) {
      return res.status(422).json({ detail: 'auth_id is required' });
    }
    if (!code) {
      return res.status(422).json({ detail: 'code is required' });
    }
    rateLimit(
      verifyRate,
      `verify:${phoneNumber}`,
      VERIFY_LIMIT,
      VERIFY_WINDOW_SECONDS,
      'Слишком много попыток подтверждения. Попробуйте позже.'
    );

    const session = authSessions.get(authId);
    if (!session || session.expiresAt <= nowMs()) {
      return res.status(404).json({ detail: 'Сессия подтверждения не найдена или истекла' });
    }
    if (session.phoneNumber !== phoneNumber) {
      return res.status(422).json({ detail: 'Номер телефона не совпадает с сессией подтверждения' });
    }
    if (session.attemptsLeft <= 0) {
      authSessions.delete(authId);
      return res.status(429).json({ detail: 'Превышено число попыток подтверждения' });
    }
    if (normalizeCode(session.pairingCode) !== code) {
      session.attemptsLeft -= 1;
      return res.status(422).json({ detail: 'Неверный pairing code' });
    }
    if (!session.sock?.authState?.creds?.registered) {
      return res.status(409).json({
        detail:
          'Подтверждение в WhatsApp еще не завершено. Введите pairing code на телефоне и повторите проверку.',
      });
    }

    const files = await readSessionFiles(session.sessionDir);
    const sessionString = signBundle({
      provider: 'whatsapp_userbot',
      issued_at: new Date().toISOString(),
      phone_number: phoneNumber,
      auth_files: files,
    });
    return res.status(200).json({
      session_string: sessionString,
      phone_number: phoneNumber,
      external_user_id: String(session.user?.id || phoneNumber.replace(/\D/g, '')),
      display_name: String(session.user?.name || `WA ${phoneNumber}`),
    });
  } catch (error) {
    logger.error({ err: error }, 'verify_code failed');
    return res.status(error.status || 500).json({ detail: error.message || 'verify_code failed' });
  }
});

app.listen(HTTP_PORT, async () => {
  await fs.mkdir(DATA_DIR, { recursive: true });
  logger.info({ port: HTTP_PORT, env: APP_ENV }, `${APP_TITLE} started`);
});
