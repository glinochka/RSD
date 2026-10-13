import React, { useMemo, useState } from 'react';
import customService from '../../services/customService';

const chatLink = (chat) => {
  if (!chat) {
    return '';
  }
  return chat.invite_link || (chat.username ? `https://t.me/${chat.username}` : '') || String(chat.id);
};

const evenSplit = (accountIds, links) => {
  const assignment = {};
  accountIds.forEach((id) => {
    assignment[id] = [];
  });
  links.forEach((link, index) => {
    if (!accountIds.length) {
      return;
    }
    assignment[accountIds[index % accountIds.length]].push(link);
  });
  return assignment;
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

  const selectedAccounts = useMemo(
    () => accounts.filter((item) => (settings?.account_ids || []).includes(item.id)),
    [accounts, settings],
  );
  const selectedChats = useMemo(
    () => chats.filter((item) => (settings?.chat_ids || []).includes(item.id)),
    [chats, settings],
  );

  const openModal = () => {
    const accountIds = selectedAccounts.map((item) => item.id);
    const stored = settings?.chat_assignments || {};
    const byId = Object.fromEntries(chats.map((item) => [String(item.id), chatLink(item)]));
    let next = {};
    const hasStored = Object.keys(stored).some((key) => (stored[key] || []).length);
    if (hasStored) {
      accountIds.forEach((id) => {
        next[id] = (stored[String(id)] || stored[id] || []).map((cid) => byId[String(cid)] || String(cid)).filter(Boolean);
      });
    } else {
      next = evenSplit(accountIds, selectedChats.map(chatLink).filter(Boolean));
    }
    const texts = {};
    accountIds.forEach((id) => {
      texts[id] = (next[id] || []).join('\n');
    });
    setDrafts(texts);
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
        task_key: taskKey,
        assignments,
      });
      const mapped = data.assignments || {};
      onApplied?.({
        chat_assignments: mapped,
        chat_ids: data.chat_ids?.length ? data.chat_ids : settings.chat_ids,
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
              По одному аккаунту — свой столбик ссылок, одна ссылка в строке. Если окно не открывать, система распределит каналы сама.
            </p>
            {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
            <div className="nc-distribute">
              {selectedAccounts.map((item) => (
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
                  <span className="nc-muted">Строк: {linesOf(drafts[item.id]).length}</span>
                </div>
              ))}
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
