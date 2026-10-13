import React, { useCallback, useEffect, useMemo, useState } from 'react';
import customService from '../../services/customService';

const TASK_CHATS_PER_ACCOUNT = 50;
const KIND_HINT = {
  channel: 'В пул этой задачи попадают только каналы — чаты из папок отсекаются.',
  chat: 'В пул этой задачи попадают только чаты и группы — каналы из папок отсекаются.',
  any: 'Каналы и чаты из выбранных папок перемешиваются в рабочих слотах.',
};
const KIND_UNIT = {
  channel: 'каналов',
  chat: 'чатов',
  any: 'каналов',
};

const chatLink = (chat) => {
  if (!chat) {
    return '';
  }
  const invite = String(chat.invite_link || chat.link || '').trim();
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
  const shuffled = [...links].sort(() => Math.random() - 0.5);
  shuffled.forEach((link) => {
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

const MixBar = ({ mix = [] }) => {
  const working = mix.reduce((sum, item) => sum + (item.assigned || 0), 0) || 1;
  if (!mix.length) {
    return null;
  }
  return (
    <div className="nc-pool-mix">
      {mix.map((item) => {
        const share = Math.round(((item.assigned || 0) / working) * 100);
        return (
          <div key={`${item.id || 0}-${item.name}`} className="nc-pool-mix-row">
            <span className="nc-pool-mix-name">{item.name}</span>
            <span className="nc-pool-mix-track">
              <span style={{ width: `${item.assigned ? Math.max(4, share) : 0}%` }} />
            </span>
            <span className="nc-muted">{item.assigned || 0} в работе · {item.reserve || 0} запас · {share}% слотов</span>
          </div>
        );
      })}
    </div>
  );
};

const ChatChip = ({ chat }) => {
  const title = chat.title || chat.link || `#${chat.id}`;
  const label = chat.folder_name ? `${chat.folder_name} · ${title}` : title;
  return (
    <span className={`nc-pool-chip ${chat.joined ? 'is-joined' : ''}`} title={chat.link || label}>
      {chat.joined ? 'вступил · ' : ''}{label}
    </span>
  );
};

const UbtDistributeChats = ({
  automationId,
  taskKey,
  accounts = [],
  chats = [],
  folders = [],
  settings,
  onApplied,
}) => {
  const [pool, setPool] = useState(null);
  const [open, setOpen] = useState(false);
  const [picker, setPicker] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [reserveDraft, setReserveDraft] = useState('');
  const [expanded, setExpanded] = useState({});
  const [showReserve, setShowReserve] = useState(false);
  const [pickedAccounts, setPickedAccounts] = useState([]);
  const [pickedFolders, setPickedFolders] = useState([]);
  const [messageHint, setMessageHint] = useState(null);

  const loadPool = useCallback(async () => {
    if (!automationId || !taskKey) {
      return null;
    }
    const data = await customService.getTaskPool(automationId, taskKey);
    setPool(data);
    return data;
  }, [automationId, taskKey]);

  useEffect(() => {
    loadPool().catch(() => {});
  }, [loadPool, settings?.account_ids, settings?.folder_ids, settings?.chat_assignments, settings?.reserve_chat_ids]);

  useEffect(() => {
    if (!messageHint) {
      return undefined;
    }
    const timer = window.setTimeout(() => setMessageHint(null), 4000);
    return () => window.clearTimeout(timer);
  }, [messageHint]);

  const applyPool = (data) => {
    setPool(data);
    onApplied?.({
      account_ids: data.account_ids || [],
      folder_ids: data.folder_ids || [],
      chat_ids: data.chat_ids?.length ? data.chat_ids : settings?.chat_ids,
      chat_assignments: data.assignments || {},
      reserve_chat_ids: data.reserve_chat_ids || [],
    });
  };

  const selectedAccounts = useMemo(() => {
    const ids = new Set(pool?.account_ids || settings?.account_ids || []);
    const fromPool = pool?.accounts || [];
    if (fromPool.length) {
      return fromPool;
    }
    return accounts.filter((item) => ids.has(item.id)).map((item) => ({
      id: item.id,
      label: item.label || item.username || `#${item.id}`,
      username: item.username,
      phone_number: item.phone_number,
      assigned: [],
      assigned_count: (settings?.chat_assignments?.[String(item.id)] || []).length,
      joined_count: 0,
    }));
  }, [pool, accounts, settings]);

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

  const availableAccounts = pool?.available_accounts || accounts;
  const availableFolders = pool?.available_folders || folders;
  const mix = pool?.folder_mix || [];
  const reserve = pool?.reserve || [];
  const cap = pool?.cap || TASK_CHATS_PER_ACCOUNT;
  const resourceKind = pool?.resource_kind || pool?.resourceKind || 'any';
  const unit = KIND_UNIT[resourceKind] || KIND_UNIT.any;
  const assignedCount = pool?.assigned_count ?? selectedAccounts.reduce((sum, item) => sum + (item.assigned_count || 0), 0);
  const reserveCount = pool?.reserve_count ?? (settings?.reserve_chat_ids || []).length;

  const openModal = () => {
    const accountIds = selectedAccounts.map((item) => item.id);
    const stored = pool?.assignments || settings?.chat_assignments || {};
    const byId = Object.fromEntries(chats.map((item) => [String(item.id), chatLink(item)]));
    const linkOf = (cid) => byId[String(cid)] || String(cid);
    let next = {};
    const hasStored = Object.keys(stored).some((key) => (stored[key] || []).length) || selectedAccounts.some((item) => (item.assigned || []).length);
    let leftover = [];
    if (hasStored) {
      accountIds.forEach((id) => {
        const acc = selectedAccounts.find((row) => row.id === id);
        const fromCards = (acc?.assigned || []).map((chat) => chat.link || linkOf(chat.id)).filter(Boolean);
        next[id] = (fromCards.length ? fromCards : (stored[String(id)] || stored[id] || []).map(linkOf).filter(Boolean)).slice(0, TASK_CHATS_PER_ACCOUNT);
      });
      const used = new Set(accountIds.flatMap((id) => next[id] || []));
      leftover = (pool?.reserve || []).map((item) => item.link || linkOf(item.id)).filter((link) => link && !used.has(link));
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

  const saveManual = async () => {
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
      onApplied?.({
        chat_assignments: data.assignments || {},
        chat_ids: data.chat_ids?.length ? data.chat_ids : settings?.chat_ids,
        reserve_chat_ids: data.reserve_chat_ids || [],
      });
      await loadPool();
      setOpen(false);
    } catch (err) {
      setError(err.message || 'Не удалось сохранить распределение');
    } finally {
      setBusy(false);
    }
  };

  const runPool = async (body, okMessage) => {
    setBusy(true);
    setError(null);
    try {
      const data = await customService.saveTaskPool(automationId, { taskKey, ...body });
      applyPool(data);
      setPicker(null);
      setMessageHint(okMessage);
    } catch (err) {
      setError(err.message || 'Не удалось обновить пул');
    } finally {
      setBusy(false);
    }
  };

  const openAccountPicker = () => {
    setPickedAccounts((pool?.account_ids || settings?.account_ids || []).map(Number));
    setPicker('accounts');
    setError(null);
  };

  const openFolderPicker = () => {
    setPickedFolders((pool?.folder_ids || settings?.folder_ids || []).map(Number));
    setPicker('folders');
    setError(null);
  };

  const togglePick = (list, setList, ident) => {
    setList((prev) => (prev.includes(ident) ? prev.filter((item) => item !== ident) : [...prev, ident]));
  };

  return (
    <div className="nc-pool">
      <div className="nc-pool-head">
        <div>
          <strong>Пул задачи</strong>
          <p className="nc-muted">
            {selectedAccounts.length} аккаунтов · {assignedCount} {unit} в работе · {reserveCount} в запасе
            {pool?.live ? ' · задача в работе — изменения применятся сразу' : ''}
          </p>
        </div>
        <div className="nc-row">
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={openAccountPicker}>Аккаунты</button>
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={openFolderPicker}>Папки</button>
          <button
            type="button"
            className="acc-btn acc-btn--ghost"
            disabled={busy || !selectedAccounts.length}
            onClick={() => runPool({
              accountIds: settings?.account_ids || pool?.account_ids,
              folderIds: settings?.folder_ids || pool?.folder_ids,
              mode: 'mix',
            }, 'Пул перемешан')}
          >
            Перемешать
          </button>
          <button type="button" className="acc-btn acc-btn--ghost" disabled={!selectedAccounts.length} onClick={openModal}>
            Вручную
          </button>
        </div>
      </div>
      <p className="nc-hint">
        {KIND_HINT[resourceKind] || KIND_HINT.any} До {cap} на аккаунт, остальные — запас.
        Новые папки лучше добавлять кнопкой «Папки». Уже вступившие остаются у своих аккаунтов; если аккаунт уже работал в папке, она к нему возвращается.
      </p>
      {messageHint ? <p className="acc-flash">{messageHint}</p> : null}
      {error && !open && !picker ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      <MixBar mix={mix} />
      {!selectedAccounts.length ? (
        <p className="nc-muted">Выберите аккаунты — здесь появится, кому какие каналы достались.</p>
      ) : (
        <div className="nc-pool-list">
          {selectedAccounts.map((item) => {
            const openRow = Boolean(expanded[item.id]);
            const count = item.assigned_count || (item.assigned || []).length;
            return (
              <div key={item.id} className="nc-pool-account">
                <button
                  type="button"
                  className="nc-pool-account-btn"
                  onClick={() => setExpanded((prev) => ({ ...prev, [item.id]: !prev[item.id] }))}
                >
                  <span>
                    <strong>{item.label || item.username || item.phone_number || `аккаунт #${item.id}`}</strong>
                    <span className="nc-muted">{item.status ? item.status : (item.username ? `@${item.username}` : item.phone_number || '')}</span>
                  </span>
                  <span className="nc-pool-count">{item.joined_count || 0} вступил · {count}/{cap}</span>
                </button>
                <div className="nc-pool-meter">
                  <span style={{ width: `${Math.min(100, Math.round((count / cap) * 100))}%` }} />
                </div>
                {openRow ? (
                  <div className="nc-pool-chips">
                    {(item.assigned || []).length
                      ? item.assigned.map((chat) => <ChatChip key={chat.id} chat={chat} />)
                      : <span className="nc-muted">Пока пусто — нажмите «Перемешать» или «Вручную»</span>}
                  </div>
                ) : null}
              </div>
            );
          })}
          <div className="nc-pool-account">
            <button type="button" className="nc-pool-account-btn" onClick={() => setShowReserve((prev) => !prev)}>
              <span>
                <strong>Запасной пул</strong>
                <span className="nc-muted">Подменят канал, если его закроют или заблокируют</span>
              </span>
              <span className="nc-pool-count">{reserveCount}</span>
            </button>
            {showReserve ? (
              <div className="nc-pool-chips">
                {reserve.length
                  ? reserve.slice(0, 80).map((chat) => <ChatChip key={chat.id} chat={chat} />)
                  : <span className="nc-muted">Запас пуст</span>}
                {reserve.length > 80 ? <span className="nc-muted">ещё {reserve.length - 80}</span> : null}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {picker === 'accounts' ? (
        <div className="nc-modal-backdrop" onClick={() => setPicker(null)}>
          <div className="nc-modal" onClick={(event) => event.stopPropagation()}>
            <div className="nc-card-head">
              <h2>Аккаунты задачи</h2>
              <button type="button" className="acc-icon-btn" onClick={() => setPicker(null)}>×</button>
            </div>
            <p className="nc-muted">Новые аккаунты забирают каналы из запаса, уже вступившие никуда не переезжают.</p>
            {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
            <div className="nc-list" style={{ marginTop: 10, maxHeight: 360, overflow: 'auto' }}>
              {!availableAccounts.length ? <p className="nc-muted">Нет аккаунтов в пуле</p> : null}
              {availableAccounts.map((item) => {
                const on = pickedAccounts.includes(Number(item.id));
                const blocked = item.eligible === false;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`nc-item ${on ? 'is-on' : ''} ${blocked ? 'is-off' : ''}`}
                    disabled={blocked}
                    onClick={() => { if (!blocked) togglePick(pickedAccounts, setPickedAccounts, Number(item.id)); }}
                  >
                    <div>
                      <strong>{item.label || item.username || `#${item.id}`}</strong>
                      <span>{item.username ? `@${item.username}` : item.phone_number || ''}</span>
                    </div>
                    <span>{item.status || (blocked ? 'не готов' : on ? 'в задаче' : 'добавить')}</span>
                  </button>
                );
              })}
            </div>
            <div className="nc-row" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => setPicker(null)}>Отмена</button>
              <button
                type="button"
                className="acc-btn acc-btn--primary"
                disabled={busy || !pickedAccounts.length}
                onClick={() => runPool({ accountIds: pickedAccounts, folderIds: settings?.folder_ids || pool?.folder_ids, mode: 'fill' }, 'Аккаунты обновлены')}
              >
                {busy ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {picker === 'folders' ? (
        <div className="nc-modal-backdrop" onClick={() => setPicker(null)}>
          <div className="nc-modal" onClick={(event) => event.stopPropagation()}>
            <div className="nc-card-head">
              <h2>Папки задачи</h2>
              <button type="button" className="acc-icon-btn" onClick={() => setPicker(null)}>×</button>
            </div>
            <p className="nc-muted">Новая папка перемешивается с текущим пулом. Уже вступившие каналы остаются у своих аккаунтов.</p>
            {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
            <div className="nc-list" style={{ marginTop: 10, maxHeight: 360, overflow: 'auto' }}>
              {!availableFolders.length ? <p className="nc-muted">Загрузите папки в разделе «Чаты и каналы»</p> : null}
              {availableFolders.map((item) => {
                const on = pickedFolders.includes(Number(item.id));
                return (
                  <button key={item.id} type="button" className={`nc-item ${on ? 'is-on' : ''}`} onClick={() => togglePick(pickedFolders, setPickedFolders, Number(item.id))}>
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.count ?? item.chats_count ?? 0} шт.</span>
                    </div>
                    <span>{on ? 'в задаче' : 'добавить'}</span>
                  </button>
                );
              })}
            </div>
            <div className="nc-row" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => setPicker(null)}>Отмена</button>
              <button
                type="button"
                className="acc-btn acc-btn--primary"
                disabled={busy || !pickedFolders.length}
                onClick={() => runPool({ accountIds: settings?.account_ids || pool?.account_ids, folderIds: pickedFolders, mode: 'mix' }, 'Папки добавлены и перемешаны')}
              >
                {busy ? 'Сохранение...' : 'Сохранить и перемешать'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {open ? (
        <div className="nc-modal-backdrop" onClick={() => setOpen(false)}>
          <div className="nc-modal nc-modal--wide" onClick={(event) => event.stopPropagation()}>
            <div className="nc-card-head">
              <h2>Ручное распределение</h2>
              <button type="button" className="acc-icon-btn" onClick={() => setOpen(false)}>×</button>
            </div>
            <p className="nc-muted">
              Не больше {TASK_CHATS_PER_ACCOUNT} ссылок на аккаунт. Лишнее уйдёт в запас.
            </p>
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
                <textarea className="nc-area" rows={12} value={reserveDraft} readOnly />
                <span className="nc-muted">Строк: {linesOf(reserveDraft).length}</span>
              </div>
            </div>
            <div className="nc-row" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => setOpen(false)}>Отмена</button>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={saveManual}>
                {busy ? 'Сохранение...' : 'Сохранить распределение'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default UbtDistributeChats;
