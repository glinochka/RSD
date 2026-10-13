import React, { useMemo, useState } from 'react';
import customService from '../../services/customService';

const TASK_CHATS_PER_ACCOUNT = 50;

const chatLink = (chat) => {
  if (!chat) {
    return '';
  }
  const invite = String(chat.invite_link || '').trim();
  if (invite) {
    return invite;
  }
  const username = String(chat.username || '').trim().replace(/^@/, '');
  if (username) {
    return `https://t.me/${username}`;
  }
  const title = String(chat.title || '').trim();
  if (/^(https?:\/\/|t\.me\/|@)/i.test(title)) {
    return title.startsWith('@') ? `https://t.me/${title.slice(1)}` : title;
  }
  return '';
};

const evenSplit = (accountIds, links, cap = TASK_CHATS_PER_ACCOUNT) => {
  const assignment = {};
  accountIds.forEach((id) => {
    assignment[id] = [];
  });
  const leftover = [];
  links.forEach((link) => {
    const aid = accountIds
      .filter((id) => (assignment[id] || []).length < cap)
      .sort((a, b) => (assignment[a].length - assignment[b].length) || (a - b))[0];
    if (aid == null) {
      leftover.push(link);
      return;
    }
    assignment[aid].push(link);
  });
  return { assignment, leftover };
};

const linesOf = (value) => String(value || '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

const UbtDistributeChats = ({
  automationId,
  taskKey,
  accounts = [],
  chats = [],
  settings,
  onApplied,
}) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [reserveDraft, setReserveDraft] = useState('');

  const selectedAccounts = useMemo(
    () => accounts.filter((item) => (settings?.account_ids || []).includes(item.id)),
    [accounts, settings],
  );
  const selectedChats = useMemo(() => {
    const chatIds = new Set((settings?.chat_ids || []).map(Number));
    const folderIds = new Set((settings?.folder_ids || []).map(Number));
    return chats.filter((item) => {
      if (chatIds.has(Number(item.id))) {
        return true;
      }
      if (item.folder_id != null && folderIds.has(Number(item.folder_id))) {
        return true;
      }
      return false;
    });
  }, [chats, settings]);

  const openModal = () => {
    const accountIds = selectedAccounts.map((item) => item.id);
    const stored = settings?.chat_assignments || {};
    const byId = Object.fromEntries(chats.map((item) => [String(item.id), chatLink(item)]));
    const linkOf = (cid) => byId[String(cid)] || String(cid);
    let next = {};
    const hasStored = Object.keys(stored).some((key) => (stored[key] || []).length);
    let leftover = [];
    if (hasStored) {
      accountIds.forEach((id) => {
        next[id] = (stored[String(id)] || stored[id] || []).map(linkOf).filter(Boolean).slice(0, TASK_CHATS_PER_ACCOUNT);
      });
      const used = new Set(accountIds.flatMap((id) => next[id] || []));
      const storedReserve = (settings?.reserve_chat_ids || []).map(linkOf).filter(Boolean);
      leftover = storedReserve.filter((link) => !used.has(link));
      selectedChats.map(chatLink).filter(Boolean).forEach((link) => {
        if (!used.has(link) && !leftover.includes(link)) {
          leftover.push(link);
        }
      });
    } else {
      const split = evenSplit(accountIds, selectedChats.map(chatLink).filter(Boolean));
      next = split.assignment;
      leftover = split.leftover;
    }
    const texts = {};
    accountIds.forEach((id) => {
      texts[id] = (next[id] || []).join('\n');
    });
    setDrafts(texts);
    setReserveDraft(leftover.join('\n'));
    setError(null);
    setOpen(true);
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const assignments = {};
      selectedAccounts.forEach((item) => {
        assignments[String(item.id)] = linesOf(drafts[item.id]);
      });
      const data = await customService.saveTaskDistribute(automationId, {
        taskKey,
        assignments,
      });
      const mapped = data.assignments || {};
      onApplied?.({
        chat_assignments: mapped,
        chat_ids: data.chat_ids?.length ? data.chat_ids : settings.chat_ids,
        reserve_chat_ids: data.reserve_chat_ids || [],
      });
      setOpen(false);
    } catch (err) {
      setError(err.message || 'Не удалось сохранить распределение');
    } finally {
      setBusy(false);
    }
  };

  if (!selectedAccounts.length) {
    return null;
  }

  return (
    <>
      <button type="button" className="acc-btn acc-btn--ghost" onClick={openModal}>
        Распределить
      </button>
      {open ? (
        <div className="nc-modal-backdrop" onClick={() => setOpen(false)}>
          <div className="nc-modal nc-modal--wide" onClick={(event) => event.stopPropagation()}>
            <div className="nc-card-head">
              <h2>Распределение каналов</h2>
              <button type="button" className="acc-icon-btn" onClick={() => setOpen(false)}>×</button>
            </div>
            <p className="nc-muted">
              На один аккаунт — не больше {TASK_CHATS_PER_ACCOUNT} ссылок. Лишние попадают в запасной пул:
              если канал уйдёт в чёрный список (закрыты комментарии или модерация), вместо него подтянется запасной.
            </p>
            <p className="nc-muted">
              Вступления ступенчатые: 15–20 случайных каналов на аккаунт по всем задачам сразу, затем пауза этот и следующий день.
              Если те же папки уже распределены в другой задаче, каналы остаются у тех же аккаунтов — второй раз вступать не нужно.
            </p>
            {!selectedChats.length ? (
              <p className="nc-muted">Нет ссылок: выберите чаты или папку, в которой уже есть каналы.</p>
            ) : null}
            {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
            <div className="nc-distribute">
              {selectedAccounts.map((item) => {
                const count = linesOf(drafts[item.id]).length;
                const over = count > TASK_CHATS_PER_ACCOUNT;
                return (
                  <div key={item.id} className="nc-distribute-col">
                    <strong>{item.label || item.username || `#${item.id}`}</strong>
                    <span className="nc-muted">{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`}</span>
                    <textarea
                      className="nc-area"
                      rows={12}
                      value={drafts[item.id] || ''}
                      onChange={(event) => setDrafts((prev) => ({ ...prev, [item.id]: event.target.value }))}
                      placeholder={'https://t.me/channel\n@username'}
                    />
                    <span className={over ? 'acc-flash acc-flash--error' : 'nc-muted'}>
                      Строк: {count} / {TASK_CHATS_PER_ACCOUNT}{over ? ' — лишнее уйдёт в запас' : ''}
                    </span>
                  </div>
                );
              })}
              <div className="nc-distribute-col">
                <strong>Запасной пул</strong>
                <span className="nc-muted">Не назначены аккаунту</span>
                <textarea
                  className="nc-area"
                  rows={12}
                  value={reserveDraft}
                  readOnly
                  placeholder="Сюда попадут ссылки сверх 50 на аккаунт"
                />
                <span className="nc-muted">Строк: {linesOf(reserveDraft).length}</span>
              </div>
            </div>
            <div className="nc-row" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => setOpen(false)}>Отмена</button>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={save}>
                {busy ? 'Сохранение...' : 'Сохранить распределение'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
};

export default UbtDistributeChats;
