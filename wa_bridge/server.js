const fs = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const pino = require('pino');
const qrcode = require('qrcode');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
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
  String(process.env.WA_USERBOT_BROWSER_PLATFORM || 'Ubuntu').trim() || 'Ubuntu',
  String(process.env.WA_USERBOT_BROWSER_NAME || 'Chrome').trim() || 'Chrome',
  String(process.env.WA_USERBOT_BROWSER_VERSION || '122.0.0.0').trim() || '122.0.0.0',
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
const runtimeSessions = new Map();
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

function verifyAndDecodeBundle(sessionString) {
  let wrapper;
  try {
    wrapper = JSON.parse(Buffer.from(String(sessionString || ''), 'base64url').toString('utf-8'));
  } catch (error) {
    const err = new Error('Некорректный формат session_string');
    err.status = 422;
    throw err;
  }
  if (Number(wrapper?.v || 0) !== 1 || !wrapper.payload || !wrapper.signature) {
    const err = new Error('Некорректная версия или структура session_string');
    err.status = 422;
    throw err;
  }
  const payloadBytes = Buffer.from(String(wrapper.payload), 'base64url');
  const expectedSignature = crypto.createHmac('sha256', SESSION_SECRET).update(payloadBytes).digest('base64url');
  if (expectedSignature !== String(wrapper.signature)) {
    const err = new Error('Некорректная подпись session_string');
    err.status = 422;
    throw err;
  }
  let payload;
  try {
    payload = JSON.parse(payloadBytes.toString('utf-8'));
  } catch (error) {
    const err = new Error('Некорректный payload session_string');
    err.status = 422;
    throw err;
  }
  if (payload?.provider !== 'whatsapp_userbot' || typeof payload?.auth_files !== 'object' || !payload.auth_files) {
    const err = new Error('session_string не содержит auth_files WhatsApp userbot');
    err.status = 422;
    throw err;
  }
  return payload;
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

async function writeSessionFiles(sessionDir, files) {
  await fs.mkdir(sessionDir, { recursive: true });
  const entries = Object.entries(files || {});
  for (const [name, content] of entries) {
    if (!name || name.includes('/') || name.includes('\\')) continue;
    await fs.writeFile(path.join(sessionDir, name), String(content || ''), 'utf-8');
  }
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

async function waitForQrCode(sock, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      sock.ev.off('connection.update', onUpdate);
      reject(new Error('Не удалось получить QR code: timeout'));
    }, timeoutMs);
    const onUpdate = (update) => {
      if (update?.qr) {
        clearTimeout(timer);
        sock.ev.off('connection.update', onUpdate);
        resolve(String(update.qr));
      }
      // Не отклоняем при connection: open + !registered: после скана QR Baileys
      // часто открывает сокет до creds.registered (и даёт 515 + реконнект).
      // Раньше это давало ложное «Подключение открыто без QR».
    };
    sock.ev.on('connection.update', onUpdate);
  });
}

/** После реконнекта нужен либо новый QR, либо уже завершённая регистрация (без второго кадра QR). */
async function waitForQrOrAuthComplete(sock, session, timeoutMs = 60000) {
  if (sock.authState?.creds?.registered) {
    return { kind: 'auth' };
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('Не удалось получить QR или завершить вход WhatsApp: timeout'));
    }, timeoutMs);
    const cleanup = () => {
      clearTimeout(timer);
      sock.ev.off('connection.update', onConn);
      sock.ev.off('creds.update', onCreds);
    };
    const finishAuth = () => {
      cleanup();
      resolve({ kind: 'auth' });
    };
    const tryFinishAuth = () => {
      if (sock.authState?.creds?.registered) {
        finishAuth();
      }
    };
    const onCreds = () => tryFinishAuth();
    const onConn = async (update) => {
      if (update?.qr) {
        const qr = String(update.qr);
        session.qrCode = qr;
        try {
          session.qrDataUrl = await qrcode.toDataURL(qr);
        } catch {
          // keep text QR at least
        }
        cleanup();
        resolve({ kind: 'qr', qr });
        return;
      }
      tryFinishAuth();
    };
    sock.ev.on('connection.update', onConn);
    sock.ev.on('creds.update', onCreds);
    tryFinishAuth();
  });
}

async function waitForSessionReady(session, timeoutMs = 15000) {
  const started = nowMs();
  while (nowMs() - started < timeoutMs) {
    const registered = Boolean(session?.sock?.authState?.creds?.registered);
    const hasUser = Boolean(session?.user?.id || session?.sock?.user?.id);
    const connected = session?.status === 'paired' || session?.status === 'connected';
    if (registered || (connected && hasUser)) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  const registered = Boolean(session?.sock?.authState?.creds?.registered);
  const hasUser = Boolean(session?.user?.id || session?.sock?.user?.id);
  const connected = session?.status === 'paired' || session?.status === 'connected';
  return registered || (connected && hasUser);
}

async function createAuthSocket(session) {
  const { state, saveCreds } = await useMultiFileAuthState(session.sessionDir);
  const versionInfo = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 0] }));
  const sock = makeWASocket({
    auth: state,
    version: versionInfo.version,
    logger: pino({ level: 'silent' }),
    markOnlineOnConnect: false,
    printQRInTerminal: false,
    browser: WA_BROWSER_SIGNATURE[0] ? WA_BROWSER_SIGNATURE : Browsers.ubuntu('Chrome'),
  });
  session.sock = sock;

  const reconnectIfNeeded = async (statusCode) => {
    if (session.reconnecting) return;
    const reconnectable = new Set([
      DisconnectReason.restartRequired,
      DisconnectReason.connectionClosed,
      DisconnectReason.connectionLost,
      DisconnectReason.timedOut,
      515,
      505,
      408,
      428,
    ]);
    if (!reconnectable.has(statusCode)) return;
    if (session.expiresAt <= nowMs()) return;
    if (sock.authState?.creds?.registered) return;
    session.reconnecting = true;
    session.status = 'reconnecting';
    try {
      try {
        sock.end(new Error('reconnect required'));
      } catch {
        // ignore
      }
      const nextSock = await createAuthSocket(session);
      if (session.authMethod === 'qr') {
        await waitForQrOrAuthComplete(nextSock, session, 60000);
      }
    } catch (error) {
      session.status = 'failed';
      session.lastError = `Reconnect failed: ${error?.message || error}`;
    } finally {
      session.reconnecting = false;
    }
  };

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async (update) => {
    if (session.authMethod === 'qr' && update.qr) {
      session.qrCode = String(update.qr);
      qrcode
        .toDataURL(session.qrCode)
        .then((value) => {
          session.qrDataUrl = value;
        })
        .catch(() => {
          // keep previous QR if conversion failed
        });
    }
    if (update.connection === 'open') {
      if (sock.authState?.creds?.registered) {
        session.status = 'paired';
      } else {
        session.status = 'connected';
      }
      session.user = sock.user || null;
    } else if (update.connection === 'close') {
      const statusCode = new Boom(update.lastDisconnect?.error)?.output?.statusCode;
      session.lastDisconnectCode = statusCode || null;
      session.lastError = `WhatsApp disconnect (${statusCode || 'unknown'})`;
      await reconnectIfNeeded(statusCode || 0);
      if (!session.reconnecting) {
        session.status = 'failed';
      }
    }
  });

  return sock;
}

async function createAuthSession(phoneNumber, authMethod = 'qr') {
  const authId = `wauth_${crypto.randomBytes(18).toString('base64url')}`;
  const sessionDir = path.join(DATA_DIR, authId);
  await fs.mkdir(sessionDir, { recursive: true });

  const session = {
    authId,
    phoneNumber,
    phoneDigits: phoneNumber.replace(/\D/g, ''),
    sessionDir,
    sock: null,
    pairingCode: null,
    qrCode: null,
    qrDataUrl: null,
    authMethod,
    status: 'pending',
    user: null,
    attemptsLeft: AUTH_MAX_ATTEMPTS,
    createdAt: nowMs(),
    expiresAt: nowMs() + AUTH_TTL_SECONDS * 1000,
    lastError: null,
    lastDisconnectCode: null,
    reconnecting: false,
  };
  authSessions.set(authId, session);

  const sock = await createAuthSocket(session);
  if (authMethod === 'qr') {
    session.qrCode = await waitForQrCode(sock);
    session.qrDataUrl = await qrcode.toDataURL(session.qrCode);
  } else {
    session.pairingCode = await waitForPairingCode(sock, session.phoneDigits);
  }
  return session;
}

async function connectRuntimeSession(connectionId, sessionString) {
  const existing = runtimeSessions.get(connectionId);
  if (existing?.sock) {
    return existing;
  }

  const decoded = verifyAndDecodeBundle(sessionString);
  const runtimeDir = path.join(DATA_DIR, `runtime_${connectionId}`);
  await writeSessionFiles(runtimeDir, decoded.auth_files);
  const { state, saveCreds } = await useMultiFileAuthState(runtimeDir);
  const versionInfo = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 0] }));
  const sock = makeWASocket({
    auth: state,
    version: versionInfo.version,
    logger: pino({ level: 'silent' }),
    markOnlineOnConnect: false,
    printQRInTerminal: false,
    browser: WA_BROWSER_SIGNATURE,
  });

  const runtime = {
    connectionId,
    phoneNumber: decoded.phone_number || null,
    sessionDir: runtimeDir,
    sock,
    queue: [],
    status: 'connecting',
    lastError: null,
    user: null,
  };
  runtimeSessions.set(connectionId, runtime);

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    if (update.connection === 'open') {
      runtime.status = 'online';
      runtime.user = sock.user || null;
    } else if (update.connection === 'close') {
      runtime.status = 'closed';
      const statusCode = new Boom(update.lastDisconnect?.error)?.output?.statusCode;
      runtime.lastError = statusCode ? `disconnect (${statusCode})` : 'disconnect';
    }
  });
  sock.ev.on('messages.upsert', (upsert) => {
    const items = Array.isArray(upsert?.messages) ? upsert.messages : [];
    for (const item of items) {
      const remoteJid = String(item?.key?.remoteJid || '').trim();
      if (!remoteJid) continue;
      runtime.queue.push({
        id: item?.key?.id || null,
        remote_jid: remoteJid,
        from_me: Boolean(item?.key?.fromMe),
        push_name: item?.pushName || null,
        message_timestamp: item?.messageTimestamp || null,
        message: item?.message || {},
      });
      if (runtime.queue.length > 1000) {
        runtime.queue.splice(0, runtime.queue.length - 1000);
      }
    }
  });

  // Let socket establish in background; manager polls status/messages.
  return runtime;
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

    const session = await createAuthSession(phoneNumber, 'qr');
    return res.status(200).json({
      auth_id: session.authId,
      delivery: 'qr',
      hint: 'Откройте WhatsApp на телефоне -> Связанные устройства -> Привязать устройство и отсканируйте QR.',
      qr_data_url: session.qrDataUrl,
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
    if (!authId) {
      return res.status(422).json({ detail: 'auth_id is required' });
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
    const isReady = await waitForSessionReady(session, 15000);
    if (!isReady) {
      return res.status(409).json({
        detail: 'Подтверждение в WhatsApp еще не завершено. Отсканируйте QR на телефоне и повторите проверку.',
        status: session.status || 'pending',
        last_error: session.lastError || null,
        last_disconnect_code: session.lastDisconnectCode || null,
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

app.post('/auth/status', enforceApiKey, async (req, res) => {
  try {
    cleanupExpired();
    const authId = String(req.body?.auth_id || '').trim();
    if (!authId) {
      return res.status(422).json({ detail: 'auth_id is required' });
    }
    const session = authSessions.get(authId);
    if (!session || session.expiresAt <= nowMs()) {
      return res.status(404).json({ detail: 'Сессия подтверждения не найдена или истекла' });
    }
    return res.status(200).json({
      auth_id: authId,
      status: session.status || 'pending',
      qr_data_url: session.qrDataUrl || null,
      last_error: session.lastError || null,
      last_disconnect_code: session.lastDisconnectCode || null,
      expires_in_seconds: Math.max(0, Math.floor((session.expiresAt - nowMs()) / 1000)),
    });
  } catch (error) {
    logger.error({ err: error }, 'auth/status failed');
    return res.status(error.status || 500).json({ detail: error.message || 'auth/status failed' });
  }
});

app.post('/session/connect', enforceApiKey, async (req, res) => {
  try {
    const connectionId = String(req.body?.connection_id || '').trim();
    const sessionString = String(req.body?.session_string || '').trim();
    if (!connectionId) {
      return res.status(422).json({ detail: 'connection_id is required' });
    }
    if (!sessionString) {
      return res.status(422).json({ detail: 'session_string is required' });
    }
    const runtime = await connectRuntimeSession(connectionId, sessionString);
    return res.status(200).json({
      connection_id: connectionId,
      status: runtime.status,
      phone_number: runtime.phoneNumber,
      user: runtime.user || null,
    });
  } catch (error) {
    logger.error({ err: error }, 'session/connect failed');
    return res.status(error.status || 500).json({ detail: error.message || 'session/connect failed' });
  }
});

app.post('/session/pull', enforceApiKey, async (req, res) => {
  try {
    const connectionId = String(req.body?.connection_id || '').trim();
    const limitRaw = Number.parseInt(String(req.body?.limit || '20'), 10);
    const limit = Math.max(1, Math.min(200, Number.isFinite(limitRaw) ? limitRaw : 20));
    if (!connectionId) {
      return res.status(422).json({ detail: 'connection_id is required' });
    }
    const runtime = runtimeSessions.get(connectionId);
    if (!runtime) {
      return res.status(404).json({ detail: 'Runtime session not found' });
    }
    const messages = runtime.queue.splice(0, limit);
    return res.status(200).json({
      connection_id: connectionId,
      status: runtime.status,
      last_error: runtime.lastError,
      messages,
    });
  } catch (error) {
    logger.error({ err: error }, 'session/pull failed');
    return res.status(error.status || 500).json({ detail: error.message || 'session/pull failed' });
  }
});

app.post('/session/send', enforceApiKey, async (req, res) => {
  try {
    const connectionId = String(req.body?.connection_id || '').trim();
    const toJid = String(req.body?.to_jid || '').trim();
    const text = String(req.body?.text || '').trim();
    if (!connectionId || !toJid || !text) {
      return res.status(422).json({ detail: 'connection_id, to_jid and text are required' });
    }
    const runtime = runtimeSessions.get(connectionId);
    if (!runtime?.sock) {
      return res.status(404).json({ detail: 'Runtime session not found' });
    }
    await runtime.sock.sendMessage(toJid, { text });
    return res.status(200).json({ status: 'ok' });
  } catch (error) {
    logger.error({ err: error }, 'session/send failed');
    return res.status(error.status || 500).json({ detail: error.message || 'session/send failed' });
  }
});

app.listen(HTTP_PORT, async () => {
  await fs.mkdir(DATA_DIR, { recursive: true });
  logger.info({ port: HTTP_PORT, env: APP_ENV }, `${APP_TITLE} started`);
});
