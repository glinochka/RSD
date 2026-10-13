const RPC_RU = {
  GetHistoryRequest: 'прочитал ленту',
  GetMessagesRequest: 'открыл сообщения',
  SendMessageRequest: 'отправил сообщение',
  SendMediaRequest: 'отправил медиа',
  SendReactionRequest: 'поставил реакцию',
  SetTypingRequest: 'показал «печатает»',
  ReadHistoryRequest: 'прочитал историю',
  JoinChannelRequest: 'вступил в канал',
  LeaveChannelRequest: 'вышел из канала',
  ImportChatInviteRequest: 'вступил по приглашению',
  GetDialogsRequest: 'открыл список чатов',
  GetFullChannelRequest: 'открыл карточку канала',
  GetFullUserRequest: 'открыл профиль',
  UpdateStatusRequest: 'сменил статус онлайн',
  GetRepliesRequest: 'открыл комментарии',
  ResolveUsernameRequest: 'нашёл канал по имени',
};

const STATUS_RU = {
  joined: 'вступил',
  blackbox: 'канал ушёл в чёрный список',
  rate_limited: 'Telegram попросил подождать',
  failed: 'не удалось вступить',
  banned: 'аккаунт заблокирован в чате',
  skipped: 'пропустил',
  unknown: 'статус неизвестен',
};

export const humanizeUbtLog = (raw) => {
  let text = String(raw || '').trim();
  if (!text) {
    return '';
  }
  text = text.replace(/\b([A-Z][A-Za-z0-9]+Request)\b/g, (_, name) => RPC_RU[name] || 'обратился к Telegram');
  text = text.replace(/\b([A-Z][A-Za-z0-9]+Error)\b/g, 'ошибка Telegram');
  text = text.replace(/FloodWait\s*\/\s*too many attempts/gi, 'Telegram ограничил частоту действий');
  text = text.replace(/\bFloodWait(?:Error)?\b:?\s*\d*s?/gi, 'Telegram ограничил частоту действий');
  text = text.replace(/вступление (.+): ([a-z_]+)$/i, (_, title, status) => {
    const mapped = STATUS_RU[status] || status;
    if (status === 'joined') {
      return `вступил в ${title}`;
    }
    return `${mapped}: ${title}`;
  });
  return text.replace(/\s+/g, ' ').trim();
};
