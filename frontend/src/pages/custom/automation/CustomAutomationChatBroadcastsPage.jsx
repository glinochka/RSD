import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomSelect from '../../../components/CustomSelect';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { folderOptions, matchesPreset, toggleNumericId, ubtModulePath } from './customNav';
import { DELAY_MAX_SECONDS } from './delayLimits';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_group_min: 15, delay_group_max: 40, delay_msg_min: 2, delay_msg_max: 4 },
  rec: { delay_group_min: 30, delay_group_max: 90, delay_msg_min: 3, delay_msg_max: 8 },
  max: { delay_group_min: 60, delay_group_max: 180, delay_msg_min: 6, delay_msg_max: 16 },
};

const WEEKDAYS = [
  { id: 0, label: 'Пн' },
  { id: 1, label: 'Вт' },
  { id: 2, label: 'Ср' },
  { id: 3, label: 'Чт' },
  { id: 4, label: 'Пт' },
  { id: 5, label: 'Сб' },
  { id: 6, label: 'Вс' },
];

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  completed: 'Завершено',
  error: 'Ошибка',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
};

const formatWhen = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const CustomAutomationChatBroadcastsPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [chatTab, setChatTab] = useState('links');
  const [links, setLinks] = useState('');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [blackQuery, setBlackQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
  };

  const load = useCallback(async () => {
    const payload = await customService.getChatBroadcastsModule(id);
    applyPayload(payload);
    setError(null);
  }, [id]);

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Не удалось загрузить модуль'));
  }, [load]);

  const jobs = data?.jobs || [];
  const activeJob = jobs.find((item) => ['pending', 'running'].includes(item.status)) || jobs[0] || null;

  useEffect(() => {
    if (!jobs.some((item) => ['pending', 'running'].includes(item.status))) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      load().catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [jobs, load]);

  const patch = (partial) => {
    setSettings((prev) => ({ ...prev, ...partial }));
    setDirty(true);
  };
  const selectedAccounts = new Set(settings?.account_ids || []);
  const selectedChats = new Set(settings?.chat_ids || []);
  const selectedFolders = new Set(settings?.folder_ids || []);
  const blockedAccounts = new Set(settings?.blacklisted_account_ids || []);
  const messages = settings?.messages || [];

  const accounts = useMemo(() => {
    const items = data?.accounts || [];
    const needle = accountQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (blockedAccounts.has(item.id)) {
        return false;
      }
      if (settings?.require_proxy && !item.has_proxy) {
        return false;
      }
      if (settings?.hide_in_work && item.in_work) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle);
    });
  }, [data, accountQuery, settings, blockedAccounts]);

  const dbChats = useMemo(() => {
    const items = data?.chats || [];
    const needle = dbQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (folderId && String(item.folder_id || '') !== String(folderId)) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.title} ${item.invite_link || ''}`.toLowerCase().includes(needle);
    });
  }, [data, dbQuery, folderId]);

  const chosenAccounts = (data?.accounts || []).filter((item) => selectedAccounts.has(item.id));
  const chosenChats = (data?.chats || []).filter((item) => selectedChats.has(item.id));
  const blockedAccountRows = (data?.accounts || []).filter((item) => blockedAccounts.has(item.id));
  const issues = data?.issues || [];
  const deliveredIds = new Set(data?.summary?.delivered_ids || []);
  const failedIds = new Set(data?.summary?.failed_ids || []);
  const remaining = settings?.only_joined
    ? (data?.chats || []).filter((item) => item.is_group !== false && !deliveredIds.has(item.id)).length
    : chosenChats.filter((item) => !deliveredIds.has(item.id)).length;
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);

  const persist = async (next = {}) => {
    const payload = { ...settingsRef.current, enabled: enabledRef.current, ...next };
    const result = await customService.saveChatBroadcastsModule(id, payload);
    applyPayload(result);
    setDirty(false);
    return result;
  };

  const persistFlag = (partial) => {
    setSettings(mergeSettings(settingsRef, partial));
    persist(partial).catch((err) => setError(err.message || 'Не удалось сохранить'));
  };

  const runSafe = async (fn, okText) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await fn();
      if (okText) {
        setMessage(okText);
      }
      return result;
    } catch (err) {
      setError(err.message || 'Не удалось выполнить действие');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const toggleAccount = (accountId) => {
    const next = selectedAccounts.has(accountId)
      ? settings.account_ids.filter((item) => item !== accountId)
      : [...settings.account_ids, accountId];
    patch({ account_ids: next });
  };

  const toggleChat = (chatId) => {
    const next = selectedChats.has(chatId)
      ? settings.chat_ids.filter((item) => item !== chatId)
      : [...settings.chat_ids, chatId];
    patch({ chat_ids: next, only_joined: false });
  };

  const toggleFolder = (folderId) => {
    patch({ folder_ids: toggleNumericId(settings.folder_ids, folderId), only_joined: false });
  };

  const blockAccount = (accountId) => {
    patch({
      blacklisted_account_ids: blockedAccounts.has(accountId)
        ? settings.blacklisted_account_ids.filter((item) => item !== accountId)
        : [...(settings.blacklisted_account_ids || []), accountId],
      account_ids: settings.account_ids.filter((item) => item !== accountId),
    });
  };

  const updateMessage = (index, text) => {
    const next = messages.map((item, idx) => (idx === index ? { text } : item));
    patch({ messages: next });
  };

  const addMessage = () => {
    if (messages.length >= 10) {
      return;
    }
    patch({ messages: [...messages, { text: '' }] });
  };

  const removeMessage = (index) => {
    patch({ messages: messages.filter((_, idx) => idx !== index) });
  };

  const toggleWeekday = (day) => {
    const current = settings.weekdays || [];
    patch({
      weekdays: current.includes(day) ? current.filter((item) => item !== day) : [...current, day].sort(),
    });
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка чат-рассылки...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Чат-рассылки</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Массовая рассылка цепочки текстовых сообщений в группы. Без медиа и стикеров: тот же публичный текст, что и живой аккаунт — с просмотром чата и имитацией набора.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Аккаунты <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
        </div>
        <div className="nc-split">
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Доступные аккаунты {accounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => load()}>Обновить</button>
            </div>
            <div className="nc-row">
              <input className="nc-search" value={accountQuery} onChange={(event) => setAccountQuery(event.target.value)} placeholder="Поиск по ID, телефону, username..." />
            </div>
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: accounts.filter((item) => item.eligible).map((item) => item.id) })}>Добавить все</button>
              <UbtCheck checked={Boolean(settings.require_proxy)} onChange={(value) => persistFlag({ require_proxy: value })}>Рабочие прокси</UbtCheck>
              <UbtCheck checked={Boolean(settings.hide_in_work)} onChange={(value) => persistFlag({ hide_in_work: value })}>Скрыть в работе</UbtCheck>
            </div>
            {accounts.length === 0 ? <div className="nc-empty">Нет рабочих аккаунтов</div> : (
              <div className="nc-list">
                {accounts.map((item) => (
                  <button key={item.id} type="button" className={`nc-item ${selectedAccounts.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`} · {item.proxy_label || 'без прокси'}</span>
                    </div>
                    <span>{item.in_work ? 'в работе' : item.eligible ? 'доступен' : 'недоступен'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Выбрано для чат-рассылки {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Удалить все</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Аккаунты не выбраны</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.daily_messages_sent || 0} действий сегодня</span>
                    </div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Заготовки запуска</span>
          {(settings.presets || []).map((item) => (
            <button key={item.name} type="button" className="nc-chip" onClick={() => { setSettings({ ...item.settings, presets: settings.presets }); setDirty(true); }}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Название заготовки" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveChatBroadcastsPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
        <p className="nc-hint">Выберите аккаунты, настройте запуск и нажмите «Сохранить заготовку». Дальше можно отметить несколько заготовок и запустить одной кнопкой.</p>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Группы <span className="nc-muted">{settings.only_joined ? 'по чатам аккаунта' : `${selectedFolders.size} пап. · ${selectedChats.size} групп`}</span></h2>
            <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
          </div>
          <div style={{ marginBottom: 12 }}>
            <FeatureToggle
              compact
              title="По чатам аккаунта"
              description="Список и папки игнорируются — каждый аккаунт пишет только в те чаты, где уже состоит. Никуда не вступает."
              checked={Boolean(settings.only_joined)}
              onChange={(value) => persistFlag({ only_joined: value })}
            />
          </div>
          <div className="nc-row">
            <button type="button" className={`nc-chip ${chatTab === 'links' ? 'is-on' : ''}`} onClick={() => setChatTab('links')}>@username / t.me</button>
            <button type="button" className={`nc-chip ${chatTab === 'delivered' ? 'is-on' : ''}`} onClick={() => setChatTab('delivered')}>Доставленные</button>
            <button type="button" className={`nc-chip ${chatTab === 'failed' ? 'is-on' : ''}`} onClick={() => setChatTab('failed')}>Отказавшие</button>
            <button type="button" className={`nc-chip ${chatTab === 'folder' ? 'is-on' : ''}`} onClick={() => setChatTab('folder')}>Папки</button>
          </div>
          {chatTab === 'links' ? (
            <div style={{ marginTop: 12 }}>
              <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder="@username, t.me/chat, числовой ID — через пробел или с новой строки" />
              <div className="nc-row" style={{ marginTop: 8 }}>
                <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addChatBroadcastsGroups(id, links).then((payload) => { applyPayload(payload); setLinks(''); return payload; }), 'Группы добавлены')}>+ Добавить</button>
                <span className="nc-muted">Строк: {links.split(/[\s,]+/).filter((item) => item.trim()).length}</span>
              </div>
              <p className="nc-hint">Можно вставить t.me/addlist/... — папка попадёт в задачу, разобьётся на пулы по аккаунтам, и каждый вступит через свой addlist.</p>
            </div>
          ) : null}
          {chatTab === 'delivered' ? (
            <div className="nc-list" style={{ marginTop: 12 }}>
              {(data.chats || []).filter((item) => deliveredIds.has(item.id)).length === 0 ? <div className="nc-empty">Доставленных чатов пока нет</div> : (data.chats || []).filter((item) => deliveredIds.has(item.id)).map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                </button>
              ))}
              <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 8 }} onClick={() => patch({ chat_ids: (data.chats || []).filter((item) => deliveredIds.has(item.id)).map((item) => item.id), only_joined: false })}>Взять все доставленные</button>
            </div>
          ) : null}
          {chatTab === 'failed' ? (
            <div className="nc-list" style={{ marginTop: 12 }}>
              {(data.chats || []).filter((item) => failedIds.has(item.id)).length === 0 ? <div className="nc-empty">Отказавших чатов нет</div> : (data.chats || []).filter((item) => failedIds.has(item.id)).map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                </button>
              ))}
              <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 8 }} onClick={() => patch({ chat_ids: (data.chats || []).filter((item) => failedIds.has(item.id)).map((item) => item.id), only_joined: false })}>Повторить отказавшие</button>
            </div>
          ) : null}
          {chatTab === 'folder' ? (
            <div style={{ marginTop: 12 }}>
              <UbtFolderPicker folders={data.folders} selectedIds={selectedFolders} onToggle={toggleFolder} />
              <div className="nc-row" style={{ marginTop: 12 }}>
                <CustomSelect
                  className="nc-select"
                  value={String(folderId || '')}
                  options={folderOptions(data.folders, 'Чаты внутри папки')}
                  onChange={(event) => setFolderId(event.target.value)}
                />
                <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск группы" />
                <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ chat_ids: dbChats.filter((item) => item.is_group !== false).map((item) => item.id), only_joined: false })}>Добавить найденные</button>
              </div>
              <div className="nc-list" style={{ marginTop: 8 }}>
                {dbChats.map((item) => (
                  <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.is_group === false ? 'канал — будет пропущен' : item.join_status} · {item.members_count || 0} уч.</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {!settings.only_joined && chosenChats.length ? (
            <div className="nc-list" style={{ marginTop: 12 }}>
              {chosenChats.map((item) => (
                <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleChat(item.id)}>
                  <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                  <span>×</span>
                </button>
              ))}
            </div>
          ) : null}
          <p className="nc-hint" style={{ marginTop: 10 }}>Сколько ещё не разослано: {remaining}</p>
        </div>

        <div className="nc-card">
          <div className="nc-card-head"><h2>Настройки отправки</h2></div>
          <p className="nc-muted">Первое сообщение — чем будет первое сообщение цепочки в каждом чате.</p>
          <div className="nc-mode" style={{ marginTop: 10 }}>
            <button type="button" className={settings.first_mode !== 'ai' ? 'is-on' : ''} onClick={() => patch({ first_mode: 'template' })}>Мой текст / шаблон</button>
            <button type="button" className={settings.first_mode === 'ai' ? 'is-on' : ''} onClick={() => patch({ first_mode: 'ai' })}>ИИ под каждый чат</button>
          </div>
          {settings.first_mode === 'ai' ? (
            <p className="nc-hint">Первая реплика генерируется под название чата. Остальные сообщения цепочки идут как шаблон. Ссылки из текста вырезаются.</p>
          ) : (
            <p className="nc-hint">Одно и то же первое сообщение во все чаты. Можно разбавить спинтаксом {'{вариант1|вариант2}'}.</p>
          )}
          <div className="nc-card-head" style={{ marginTop: 16 }}>
            <h2>Цепочка сообщений</h2>
            <span className="nc-muted">{messages.length} сообщений</span>
          </div>
          {messages.length === 0 ? (
            <div className="nc-empty">Цепочка пуста — добавьте первое сообщение</div>
          ) : (
            <div className="nc-chain">
              {messages.map((item, index) => (
                <div key={`msg-${index}`} className="nc-chain-item">
                  <textarea className="nc-area" value={item.text || ''} onChange={(event) => updateMessage(index, event.target.value)} placeholder={index === 0 && settings.first_mode === 'ai' ? 'Подсказка тона для ИИ (необязательно)' : `Сообщение ${index + 1}`} />
                  <button type="button" className="nc-chain-remove" onClick={() => removeMessage(index)}>×</button>
                </div>
              ))}
            </div>
          )}
          <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 10 }} disabled={messages.length >= 10} onClick={addMessage}>+ Добавить сообщение</button>
          <p className="nc-hint">{'{вариант1|вариант2}'} в тексте — бот подставит один вариант случайно при каждой отправке. Это одно сообщение, а не несколько.</p>
          <p className="nc-hint">Переменные чата: {'{group_title}'}, {'{group_username}'}. Отправитель: {'{my_name}'}, {'{my_first_name}'}, {'{my_username}'}.</p>
          <div style={{ marginTop: 12 }}>
            <FeatureToggle compact title="Пропускать ошибки" description="При ошибке отправки (нет доступа, бан) — пропустить группу и продолжить." checked={Boolean(settings.skip_errors)} onChange={(value) => persistFlag({ skip_errors: value })} />
          </div>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head">
            <h2>Темп и режим работы</h2>
            <div className="nc-row">
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.rec)}>Рекомендуемые</button>
              <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.max)}>Макс</button>
            </div>
          </div>
          <div className="nc-row">
            <span className="nc-muted">Между группами</span>
            <Stepper value={settings.delay_group_min} min={0} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_group_min: value, delay_group_max: Math.max(value, settings.delay_group_max) })} />
            <span className="nc-muted">до</span>
            <Stepper value={settings.delay_group_max} min={settings.delay_group_min} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_group_max: value })} />
            <span className="nc-muted">с</span>
          </div>
          <div className="nc-row">
            <span className="nc-muted">Между сообщениями</span>
            <Stepper value={settings.delay_msg_min} min={0} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_msg_min: value, delay_msg_max: Math.max(value, settings.delay_msg_max) })} />
            <span className="nc-muted">до</span>
            <Stepper value={settings.delay_msg_max} min={settings.delay_msg_min} max={DELAY_MAX_SECONDS} onChange={(value) => patch({ delay_msg_max: value })} />
            <span className="nc-muted">с</span>
          </div>
          <div className="nc-card-head"><h2>Объём рассылки</h2></div>
          <div className="nc-mode">
            <button type="button" className={settings.work_mode !== 'time' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'count' })}># По количеству</button>
            <button type="button" className={settings.work_mode === 'time' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'time' })}>По времени</button>
          </div>
          {settings.work_mode === 'time' ? (
            <p className="nc-hint" style={{ marginTop: 10 }}>Ограничение — часы и дни ниже. Проход идёт, пока окно открыто, без жёсткого лимита сообщений.</p>
          ) : (
            <div className="nc-slider" style={{ marginTop: 14 }}>
              <span className="nc-muted">Максимум сообщений {settings.max_messages}</span>
              <input type="range" min="1" max="500" value={settings.max_messages || 100} onChange={(event) => patch({ max_messages: Number(event.target.value) })} />
            </div>
          )}
          <div className="nc-mode" style={{ marginTop: 14 }}>
            <button type="button" className={(settings.scenario || (settings.skip_sent ? 'once' : 'loop')) !== 'once' ? 'is-on' : ''} onClick={() => patch({ scenario: 'loop', skip_sent: false })}>Круговой</button>
            <button type="button" className={(settings.scenario || (settings.skip_sent ? 'once' : 'loop')) === 'once' ? 'is-on' : ''} onClick={() => patch({ scenario: 'once', skip_sent: true })}>Единичный</button>
          </div>
          <p className="nc-hint" style={{ marginTop: 8 }}>
            {(settings.scenario || (settings.skip_sent ? 'once' : 'loop')) === 'once'
              ? 'Один проход по всем чатам — задача завершится сама.'
              : 'Круговой сценарий: задача не завершается, пока не нажмёте «Остановить». Например, каждый час снова в те же чаты.'}
          </p>
          <div style={{ marginTop: 14 }}>
            <FeatureToggle compact title="Пропускать чаты, куда уже отправляли" description="Учитывается история всех ваших аккаунтов, а не только этой задачи." checked={Boolean(settings.skip_sent)} onChange={(value) => persistFlag({ skip_sent: value, scenario: value ? 'once' : 'loop' })} />
          </div>
          <div style={{ marginTop: 8 }}>
            <FeatureToggle compact title="Ограничивать темп на аккаунт" description="После группы аккаунт уходит на целевой отдых, чтобы не писать пачкой." checked={Boolean(settings.limit_rate)} onChange={(value) => persistFlag({ limit_rate: value })} />
          </div>
        </div>

        <div className="nc-card">
          <div className="nc-card-head"><h2>Расписание и план</h2></div>
          <div className="nc-hours">
            <label className="nc-muted">
              Окончание
              <input className="nc-input" type="datetime-local" value={(settings.end_at || '').slice(0, 16)} onChange={(event) => patch({ end_at: event.target.value })} />
            </label>
            <span className="nc-muted">Часовой пояс Europe/Moscow</span>
          </div>
          <div className="nc-hours" style={{ marginTop: 12 }}>
            <span className="nc-muted">Часы работы</span>
            <input className="nc-input" type="number" min="0" max="23" placeholder="с" value={settings.work_hour_start ?? ''} onChange={(event) => patch({ work_hour_start: event.target.value === '' ? null : Number(event.target.value) })} />
            <span className="nc-muted">до</span>
            <input className="nc-input" type="number" min="0" max="23" placeholder="до" value={settings.work_hour_end ?? ''} onChange={(event) => patch({ work_hour_end: event.target.value === '' ? null : Number(event.target.value) })} />
          </div>
          <p className="nc-muted" style={{ marginTop: 12 }}>Дни недели</p>
          <div className="nc-days" style={{ marginTop: 8 }}>
            {WEEKDAYS.map((day) => (
              <button key={day.id} type="button" className={`nc-chip ${(settings.weekdays || []).includes(day.id) ? 'is-on' : ''}`} onClick={() => toggleWeekday(day.id)}>{day.label}</button>
            ))}
          </div>
          <p className="nc-hint">Пусто — без ограничений. Вне часов и дней рассылка ждёт, в «Окончание» — завершается.</p>
          <div style={{ marginTop: 12 }}>
            <FeatureToggle compact title="Ночной простой" description="С 21:30 до 07:00 по Москве рассылка не идёт — тот же фермерский ритм, что у остальных модулей." checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })} />
          </div>
          <div className="nc-card-head" style={{ marginTop: 16 }}><h2>Особые настройки</h2></div>
          <FeatureToggle compact title="Имитация набора" description="Перед отправкой аккаунт смотрит чат и печатает. Выключите — сырой send_message без набора." checked={Boolean(settings.imitate_typing)} onChange={(value) => persistFlag({ imitate_typing: value })} />
          <div className="nc-row" style={{ marginTop: 12 }}>
            <span className="nc-muted">Ошибок подряд до остановки</span>
            <Stepper value={settings.errors_until_stop} min={1} max={50} onChange={(value) => patch({ errors_until_stop: value })} />
          </div>
          <div className="nc-row" style={{ marginTop: 10 }}>
            <span className="nc-muted">Замедление непрогретых</span>
            <Stepper value={settings.warmup_slow ? 2 : 1} min={1} max={2} onChange={(value) => patch({ warmup_slow: value > 1 })} />
          </div>
          <p className="nc-hint">Непрогретые аккаунты ждут в {settings.warmup_slow ? '2' : '1'} раза дольше.</p>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>После рассылки</h2>
        </div>
        <p className="nc-intro">Входящие личные после рассылки обрабатывает перехват заявок.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{settings.only_joined ? 'по членству' : (selectedFolders.size || selectedChats.size)}</strong><span>Папки / группы</span></div>
          <div className="nc-kpi"><strong>{settings.delay_group_max}c</strong><span>Задержка макс.</span></div>
          <div className="nc-kpi"><strong>{settings.work_mode === 'time' ? 'окно' : settings.max_messages}</strong><span>Макс. отправок</span></div>
        </div>
        {issues.length ? (
          <div className="nc-alert" style={{ marginTop: 12 }}>
            <strong>Проблемы с конфигурацией</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        <div className="nc-logs" style={{ marginTop: 12 }}>
          {(activeJob?.logs || []).length === 0 ? 'Логи появятся после запуска. Хранятся 24 часа.' : (activeJob.logs || []).map((row, index) => (
            <div key={`${row.ts}-${index}`} className={row.level === 'error' ? 'nc-log-err' : ''}>{formatWhen(row.ts)} {row.message}</div>
          ))}
        </div>
        <UbtUnsaved dirty={dirty} />
        <div className="nc-launch" style={{ marginTop: 12 }}>
          <div className="nc-status">
            <span className={`nc-dot ${activeJob && ['pending', 'running'].includes(activeJob.status) ? 'is-on' : ''}`} />
            {activeJob ? `${STATUS_LABELS[activeJob.status] || activeJob.status} · ${formatWhen(activeJob.created_at)}` : 'Остановлено'}
          </div>
          <div className="nc-row">
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => persist()}>Сохранить</button>
            {activeJob?.can_cancel ? (
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.cancelAutomationJob(id, activeJob.id).then(load), 'Запуск отменён')}>Остановить</button>
            ) : null}
            <button
              type="button"
              className="acc-btn acc-btn--primary"
              disabled={busy || !enabled || (issues.length > 0 && !dirty)}
              onClick={() => runSafe(async () => {
                const saved = assertCanRun(await persist());
                await customService.runChatBroadcastsModule(id, { ...saved.settings, enabled: saved.enabled });
                await load();
              }, 'Запуск поставлен в очередь')}
            >
              + Новый запуск
            </button>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'tasks')}>Все задачи</Link>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Статистика</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=chat_broadcast`}>История рассылок</Link>
        </div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Успешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Неуспешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Процент успешных</span></div>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head"><h2>Чёрный список групп</h2></div>
          <div className="nc-row">
            <input className="nc-search" value={blackQuery} onChange={(event) => setBlackQuery(event.target.value)} placeholder="Название или ссылка группы" />
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.blackboxChatBroadcastsChat(id, { query: blackQuery }).then((payload) => { applyPayload(payload); setBlackQuery(''); return payload; }), 'Группа в чёрном списке')}>+ В ЧС</button>
          </div>
          {(data.blacklist || []).length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Пусто. Сюда попадают группы с ошибками доступа и те, что вы добавите вручную.</p> : (
            <div className="nc-list" style={{ marginTop: 10 }}>
              {(data.blacklist || []).map((item) => (
                <div key={item.id} className="nc-item">
                  <div><strong>{item.title}</strong><span>{item.reason || 'вручную'}</span></div>
                  <span>{formatWhen(item.black_boxed_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="nc-card">
          <div className="nc-card-head"><h2>Чёрный список аккаунтов</h2></div>
          <div className="nc-row">
            <input className="nc-search" value={blackAccountQuery} onChange={(event) => setBlackAccountQuery(event.target.value)} placeholder="ID, username или телефон" />
            <button
              type="button"
              className="acc-btn acc-btn--ghost"
              onClick={() => {
                const needle = blackAccountQuery.trim().toLowerCase();
                if (!needle) {
                  return;
                }
                const found = (data.accounts || []).find((item) => `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle));
                if (found) {
                  blockAccount(found.id);
                  setBlackAccountQuery('');
                }
              }}
            >
              + В ЧС
            </button>
          </div>
          {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Эти аккаунты не будут писать в группы, даже если попадут в пул.</p> : (
            <div className="nc-list" style={{ marginTop: 10 }}>
              {blockedAccountRows.map((item) => (
                <button key={item.id} type="button" className="nc-item" onClick={() => blockAccount(item.id)}>
                  <div><strong>{item.label}</strong><span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`}</span></div>
                  <span>×</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationChatBroadcastsPage;
