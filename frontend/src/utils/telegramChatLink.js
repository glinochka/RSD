const TELEGRAM_HOSTS = new Set([
  't.me',
  'www.t.me',
  'telegram.me',
  'www.telegram.me',
  'telegram.dog',
  'www.telegram.dog',
]);

const RESERVED_PATHS = new Set([
  'addstickers',
  'addemoji',
  'addtheme',
  'share',
  'proxy',
  'socks',
  'setlanguage',
  'iv',
  'login',
  'confirmphone',
  'invoice',
  'giftcode',
  'nft',
  'boost',
  'boosts',
  'addlist',
  'contact',
  'joinchat',
  'a',
  'k',
  'm',
]);

const USERNAME_RE = /^[A-Za-z][A-Za-z0-9_]{3,31}$/;
const INVITE_HASH_RE = /^[A-Za-z0-9_-]{8,64}$/;
const CHANNEL_ID_RE = /^-100\d{6,}$/;
const DIGITS_RE = /^\d{6,}$/;
const BARE_HOST_RE = /^(?:https?:\/\/)?(?:t\.me|telegram\.me|telegram\.dog)\//i;

const FORMAT_ERROR = 'Некорректная ссылка. Можно: https://t.me/name, t.me/name, @name или name';

function usernameRef(username) {
  const name = String(username || '')
    .trim()
    .replace(/^@/, '')
    .replace(/\/+$/, '');
  if (!USERNAME_RE.test(name)) {
    return { ok: false, error: 'Некорректное имя канала или чата' };
  }
  const slug = name.toLowerCase();
  return {
    ok: true,
    kind: 'username',
    value: slug,
    canonical: `https://t.me/${slug}`,
    isPrivate: false,
  };
}

function inviteRef(hashValue) {
  let inviteHash = decodeURIComponent(String(hashValue || '').trim()).replace(/^\+/, '');
  if (inviteHash.toLowerCase().startsWith('joinchat/')) {
    inviteHash = inviteHash.split('/').slice(1).join('/');
  }
  if (/^\d+$/.test(inviteHash)) {
    return { ok: false, error: 'Это похоже на номер телефона. Нужна ссылка на чат или канал' };
  }
  if (!INVITE_HASH_RE.test(inviteHash)) {
    return { ok: false, error: 'Некорректная ссылка-приглашение' };
  }
  return {
    ok: true,
    kind: 'invite',
    value: inviteHash,
    canonical: `https://t.me/+${inviteHash}`,
    isPrivate: true,
  };
}

function channelIdRef(rawId) {
  const digits = String(rawId || '').trim();
  const internal = digits.startsWith('-100') ? digits.slice(4) : digits;
  const full = digits.startsWith('-100') ? digits : `-100${digits}`;
  if (!/^\d{6,}$/.test(internal)) {
    return { ok: false, error: 'Некорректный id канала' };
  }
  return {
    ok: true,
    kind: 'channel_id',
    value: full,
    canonical: `https://t.me/c/${internal}`,
    isPrivate: true,
  };
}

function fromTgScheme(text) {
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    return { ok: false, error: 'Некорректная Telegram-ссылка' };
  }
  const host = (parsed.host || '').toLowerCase();
  const path = parsed.pathname.replace(/^\/+/, '').toLowerCase();
  if (host === 'join' || path === 'join') {
    return inviteRef(parsed.searchParams.get('invite') || '');
  }
  const domain = parsed.searchParams.get('domain');
  if (domain) {
    return usernameRef(domain);
  }
  return { ok: false, error: 'Некорректная Telegram-ссылка' };
}

function fromUrl(text) {
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    return { ok: false, error: FORMAT_ERROR };
  }
  const scheme = parsed.protocol.replace(':', '').toLowerCase();
  if (scheme !== 'http' && scheme !== 'https') {
    return { ok: false, error: FORMAT_ERROR };
  }
  const host = parsed.hostname.toLowerCase();
  if (!TELEGRAM_HOSTS.has(host)) {
    return { ok: false, error: 'Нужна ссылка t.me, @username или имя канала' };
  }
  const parts = parsed.pathname
    .split('/')
    .map((part) => decodeURIComponent(part))
    .filter(Boolean);
  if (!parts.length) {
    return { ok: false, error: 'В ссылке нет имени чата или канала' };
  }
  const first = parts[0];
  const firstLower = first.toLowerCase();
  if (first.startsWith('+')) {
    return inviteRef(first.slice(1));
  }
  if (firstLower === 'joinchat') {
    if (parts.length < 2) {
      return { ok: false, error: 'Некорректная ссылка-приглашение' };
    }
    return inviteRef(parts[1]);
  }
  if (firstLower === 's' && parts.length >= 2) {
    return usernameRef(parts[1].split('?')[0]);
  }
  if (firstLower === 'c' && parts.length >= 2) {
    return channelIdRef(parts[1].split('?')[0]);
  }
  if (RESERVED_PATHS.has(firstLower)) {
    return { ok: false, error: 'Это не ссылка на чат или канал' };
  }
  return usernameRef(first.split('?')[0]);
}

export function parseTelegramChatRef(raw) {
  if (raw == null) {
    return { ok: false, empty: true, error: 'Укажите ссылку, @username или имя канала' };
  }
  const text = String(raw).trim().replace(/^['"]|['"]$/g, '');
  if (!text) {
    return { ok: false, empty: true, error: 'Укажите ссылку, @username или имя канала' };
  }

  const lower = text.toLowerCase();
  if (lower.startsWith('tg://') || lower.startsWith('tg:')) {
    return fromTgScheme(text);
  }
  const withScheme = BARE_HOST_RE.test(text) && !text.includes('://') ? `https://${text}` : text;
  if (withScheme.includes('://')) {
    return fromUrl(withScheme);
  }
  if (text.startsWith('@')) {
    return usernameRef(text.slice(1));
  }
  if (text.startsWith('+')) {
    return inviteRef(text.slice(1));
  }
  if (lower.startsWith('joinchat/')) {
    return inviteRef(text.split('/').slice(1).join('/'));
  }
  if (CHANNEL_ID_RE.test(text) || DIGITS_RE.test(text)) {
    return channelIdRef(text);
  }
  if (USERNAME_RE.test(text)) {
    return usernameRef(text);
  }
  return { ok: false, error: FORMAT_ERROR };
}
