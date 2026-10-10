import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import CustomSelect from '../../../components/CustomSelect';
import UbtCheck from '../../../components/custom/UbtCheck';
import UbtFolderPicker from '../../../components/custom/UbtFolderPicker';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import UbtJoinDelay from '../../../components/custom/UbtJoinDelay';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { folderOptions, toggleNumericId, ubtModulePath } from './customNav';
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  completed: 'Завершено',
  error: 'Ошибка',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
};

const INTENSITY = [
  { id: 'cautious', title: 'Осторожный', hint: 'Новые аккаунты, 0–7 дней: короткая сессия, без реакций и контактов.' },
  { id: 'normal', title: 'Нормальный', hint: '7–30 дней: чтение, сторис, реакции, иногда контакт комментатора.' },
  { id: 'trusted', title: 'Доверенный', hint: '30+ дней: полный набор жестов, включая Saved Messages.' },
];

const DURATION_CHIPS = [
  { value: 0, label: 'Авто' },
  { value: 2, label: '2 мин' },
  { value: 4, label: '4 мин' },
  { value: 6, label: '6 мин' },
];

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

const CustomAutomationWarmupPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [usernames, setUsernames] = useState(['', '', '']);
  const [messages, setMessages] = useState(['', '', '']);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [targetTab, setTargetTab] = useState('links');
  const [links, setLinks] = useState('');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [fineOpen, setFineOpen] = useState(false);

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
    if (payload.is_admin) {
      const nextUsers = [...(payload.usernames || [])];
      const nextMsgs = [...(payload.messages || [])];
      setUsernames([nextUsers[0] || '', nextUsers[1] || '', nextUsers[2] || '']);
      setMessages([nextMsgs[0] || '', nextMsgs[1] || '', nextMsgs[2] || '']);
    }
  };

  const load = useCallback(async () => {
    const payload = await customService.getWarmupModule(id);
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
  const issues = data?.issues || [];
  const warnings = data?.warnings || [];
  const nowHour = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' });
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);
  const usernamesRef = useLiveRef(usernames);
  const messagesRef = useLiveRef(messages);

  const persistBody = (next = {}) => {
    const payload = { ...settingsRef.current, ...next, enabled: next.enabled !== undefined ? next.enabled : enabledRef.current };
    if (data?.is_admin) {
      payload.usernames = usernamesRef.current;
      payload.messages = messagesRef.current;
    }
    return payload;
  };

  const persist = async (next = {}) => {
    const result = await customService.saveWarmupModule(id, persistBody(next));
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
    patch({ chat_ids: next });
  };

  const toggleFolder = (folderId) => {
    patch({ folder_ids: toggleNumericId(settings.folder_ids, folderId) });
  };

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка прогрева...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <div>
            <h2>Прогрев аккаунтов</h2>
            <p className="nc-intro">После первичного прогрева аккаунт сам живёт рабочий день: онлайн, перерывы, чтение, тайпинг, реакции, контакты. Модуль не нужен для этого — он только добавляет диалоги с доверенными юзернеймами и отдельные чаты.</p>
          </div>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Выбор аккаунтов <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'accounts')}>Менеджер аккаунтов ›</Link>
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
                      <span>{item.username ? `@${item.username}` : item.phone_number || `#${item.id}`} · {item.stage_label} · {item.warmup_label}</span>
                    </div>
                    <span>{item.in_work ? 'в работе' : item.eligible ? 'доступен' : 'недоступен'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Выбрано для прогрева {chosenAccounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: [] })}>Удалить все</button>
            </div>
            {chosenAccounts.length === 0 ? <div className="nc-empty">Пустой список — берём все рабочие аккаунты</div> : (
              <div className="nc-list">
                {chosenAccounts.map((item) => (
                  <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleAccount(item.id)}>
                    <div>
                      <strong>{item.label}</strong>
                      <span>{item.warmup_label}{item.warmup_dialog_count ? ` · диалогов ${item.warmup_dialog_count}` : ''}</span>
                    </div>
                    <span>×</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Настройки прогрева</h2>
          <div className="nc-mode" style={{ maxWidth: 220 }}>
            <button type="button" className={settings.mode === 'manual' ? 'is-on' : ''} onClick={() => persistFlag({ mode: 'manual' })}>Ручной</button>
            <button type="button" className={settings.mode === 'auto' ? 'is-on' : ''} onClick={() => persistFlag({ mode: 'auto' })}>Авто</button>
          </div>
        </div>
        <p className="nc-muted">{settings.mode === 'auto' ? 'Планировщик сам крутит диалоги, сессии чтения и переписку между аккаунтами.' : 'Планировщик эти три слота не трогает — запуск только кнопкой ниже.'}</p>
        <div className="nc-row" style={{ marginTop: 12 }}>
          <span className="nc-muted">Заготовки</span>
          {(settings.presets || []).map((item) => (
            <button key={item.name} type="button" className="nc-chip" onClick={() => { setSettings({ ...item.settings, presets: settings.presets }); setDirty(true); }}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Имя заготовки" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveWarmupPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить</button>
        </div>
        <div className="nc-split" style={{ marginTop: 14 }}>
          <div>
            <span className="nc-muted">Расписание активности</span>
            <p className="nc-note">Москва, UTC+3. Окно фермы по умолчанию 08:00–20:00, ночью действий нет. Сейчас {nowHour}.</p>
            <p className="nc-muted" style={{ marginTop: 8 }}>Случайные перерывы всегда включены: 15–30 мин после сессии, 20–40 мин в первую неделю. Диалоги с доверенными — раз в 1–2 часа, у новых 2–4 часа.</p>
          </div>
          <div>
            <span className="nc-muted">Интенсивность прогрева</span>
            <div className="nc-picks" style={{ marginTop: 8 }}>
              {INTENSITY.map((item) => (
                <button key={item.id} type="button" className={`nc-pick ${settings.intensity === item.id ? 'is-on' : ''}`} onClick={() => patch({ intensity: item.id })}>
                  <strong>{item.title}</strong>
                  <span className="nc-muted">{item.hint} Сейчас в пуле: {data.stages?.[item.id] || 0}</span>
                </button>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <FeatureToggle compact title="Автоадаптация по стадии аккаунта" description="Сами берём осторожный / нормальный / доверенный по возрасту сессии. Если выключить — всем выбранным применится карточка выше." checked={settings.intensity === 'auto'} onChange={(value) => persistFlag({ intensity: value ? 'auto' : 'normal' })} />
            </div>
          </div>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Лимиты безопасности</h2></div>
        <p className="nc-note">Прогрев не ест суточный лимит комментариев. Целевые действия (комменты, шиллинг, ЛС) живут на другом таймере 40–70 мин и разгоне 30% → 100% за 7 дней.</p>
        <div style={{ marginTop: 12 }}>
          <span className="nc-muted">Длительность сессии гуманизации на один аккаунт</span>
          <div className="nc-durations" style={{ marginTop: 8 }}>
            {DURATION_CHIPS.map((item) => (
              <button key={item.value} type="button" className={Number(settings.session_minutes || 0) === item.value ? 'is-on' : ''} onClick={() => patch({ session_minutes: item.value })}>{item.label}</button>
            ))}
          </div>
          <p className="nc-hint">Авто: 1.5–3 мин новым, 3–6 мин обычным, 4–7 мин доверенным. Это не сутки прогрева, а одна живая сессия чтения.</p>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Действия прогрева</h2></div>
        <FeatureToggle compact title="Диалоги с доверенными" description="2–3 коротких реплики на второй и третий день. Юзернеймы задаёт администратор, текст слегка варьируется." checked={Boolean(settings.do_warmup_dms)} onChange={(value) => persistFlag({ do_warmup_dms: value })} />
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Диалоги между аккаунтами" description="Свои аккаунты переписываются в личке бытовыми фразами. Нужно минимум два с username." checked={Boolean(settings.do_peer_dialogs)} onChange={(value) => persistFlag({ do_peer_dialogs: value })} />
        </div>
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Читать каналы" description="Открываем подписки, листаем ленту, иногда ставим прочитано. Не случайный парсер чужих чатов." checked={Boolean(settings.do_read_channels)} onChange={(value) => persistFlag({ do_read_channels: value })} />
        </div>
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Просмотр сторис" description="Смотрим сторис из ленты подписок." checked={Boolean(settings.do_stories)} onChange={(value) => persistFlag({ do_stories: value })} />
        </div>
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Реакции" description="Иногда ставим 👍🔥❤ в подписках. Новые аккаунты (0–7 дней) это не делают, даже если тумблер включён." checked={Boolean(settings.do_reactions)} onChange={(value) => persistFlag({ do_reactions: value })} />
        </div>
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Повышение доверия" description="Редко добавляем автора комментария в контакты — не Telegram Premium и не ежедневная квота." checked={Boolean(settings.do_comment_contacts)} onChange={(value) => persistFlag({ do_comment_contacts: value })} />
        </div>
        <div style={{ marginTop: 8 }}>
          <FeatureToggle compact title="Вступать в группы" description="Только цели из папок ниже. Случайные публичные чаты сами не ищем." checked={Boolean(settings.do_joins)} onChange={(value) => persistFlag({ do_joins: value })} />
          {settings.do_joins ? <UbtJoinDelay settings={settings} onPatch={patch} /> : null}
        </div>
        <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 12 }} onClick={() => setFineOpen((prev) => !prev)}>{fineOpen ? 'Скрыть тонкую настройку' : 'Тонкая настройка действий'}</button>
        {fineOpen ? (
          <p className="nc-note">В сессии ещё есть набор жестов по стадии: набор без отправки, черновик, профиль, поиск, Saved Messages у доверенных. Их не выключаем по отдельности — они часть живого слота.</p>
        ) : null}
        {data.is_admin ? (
          <div className="nc-split" style={{ marginTop: 14 }}>
            <div>
              <span className="nc-muted">Доверенные юзернеймы</span>
              {usernames.map((value, index) => (
                <input key={`u-${index}`} className="nc-input" style={{ marginTop: 8, width: '100%' }} value={value} onChange={(event) => { setUsernames((prev) => prev.map((item, idx) => (idx === index ? event.target.value : item))); setDirty(true); }} placeholder={`@username ${index + 1}`} />
              ))}
            </div>
            <div>
              <span className="nc-muted">Реплики диалога</span>
              {messages.map((value, index) => (
                <input key={`m-${index}`} className="nc-input" style={{ marginTop: 8, width: '100%' }} value={value} onChange={(event) => { setMessages((prev) => prev.map((item, idx) => (idx === index ? event.target.value : item))); setDirty(true); }} placeholder={index === 0 ? 'Привет' : index === 1 ? 'Как дела?' : 'Что нового?'} />
              ))}
            </div>
          </div>
        ) : (
          <p className="nc-muted" style={{ marginTop: 12 }}>Доверенных юзернеймов: {data.username_count || 0}. Их видит только администратор.</p>
        )}
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Целевые группы / каналы</h2>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
        </div>
        <p className="nc-hint">Сюда попадают чаты, в которые аккаунт может вступить после прогрева. Пусто = вступления идут из общего списка чатов, не из случайного интернета.</p>
        <div className="nc-row" style={{ marginTop: 8 }}>
          <button type="button" className={`nc-chip ${targetTab === 'links' ? 'is-on' : ''}`} onClick={() => setTargetTab('links')}>Ссылки</button>
          <button type="button" className={`nc-chip ${targetTab === 'folder' ? 'is-on' : ''}`} onClick={() => setTargetTab('folder')}>Папки</button>
        </div>
        {targetTab === 'links' ? (
          <div style={{ marginTop: 10 }}>
            <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder={'@cryptogroup\n@newsChannel\nhttps://t.me/joinchat/...'} />
            <div className="nc-row" style={{ marginTop: 8 }}>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addWarmupTargets(id, links).then((payload) => { applyPayload(payload); setLinks(''); if (payload.add_errors?.length) { setError(payload.add_errors.join('; ')); } return payload; }), 'Цели добавлены')}>+ Добавить</button>
            </div>
          </div>
        ) : (
          <div style={{ marginTop: 10 }}>
            <UbtFolderPicker folders={data.folders} selectedIds={selectedFolders} onToggle={toggleFolder} />
            <div className="nc-row" style={{ marginTop: 12 }}>
              <CustomSelect
                className="nc-select"
                value={String(folderId || '')}
                options={folderOptions(data.folders, 'Чаты внутри папки')}
                onChange={(event) => setFolderId(event.target.value)}
              />
              <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск" />
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ chat_ids: dbChats.map((item) => item.id) })}>Добавить найденные</button>
            </div>
            <div className="nc-list" style={{ marginTop: 8 }}>
              {dbChats.map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.join_status}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
        {chosenChats.length ? (
          <div className="nc-list" style={{ marginTop: 10 }}>
            {chosenChats.map((item) => (
              <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleChat(item.id)}>
                <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                <span>×</span>
              </button>
            ))}
          </div>
        ) : <p className="nc-muted" style={{ marginTop: 10 }}>Цели не выбраны. Аккаунт не вступает в случайные группы.</p>}
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{selectedAccounts.size || (data.accounts || []).filter((item) => item.eligible).length}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{settings.session_minutes ? `${settings.session_minutes}м` : 'авто'}</strong><span>Сессия</span></div>
          <div className="nc-kpi"><strong>{data.username_count || 0}</strong><span>Доверенных</span></div>
          <div className="nc-kpi"><strong>{chosenChats.length || 'база'}</strong><span>Вступления</span></div>
        </div>
        {issues.length ? (
          <div className="nc-alert" style={{ marginTop: 12 }}>
            <strong>Нельзя запустить</strong>
            {issues.map((item) => <div key={item}>{item}</div>)}
          </div>
        ) : null}
        {warnings.length ? (
          <p className="nc-note">{warnings.join(' ')}</p>
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
                const saved = assertCanRun(await persist(), 'Прогрев выключен');
                await customService.runWarmupModule(id, { ...saved.settings, enabled: saved.enabled });
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
          <h2>История</h2>
          <Link className="acc-btn acc-btn--ghost" to={`${ubtModulePath(id, 'stats')}?history=warmup`}>Открыть полную историю →</Link>
        </div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Успешно</span></div>
          <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Ошибки</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Процент успеха</span></div>
        </div>
        <p className="nc-muted" style={{ marginTop: 8 }}>Диалоги: {data.summary?.dms || 0} · между аккаунтами: {data.summary?.peers || 0} · контакты: {data.summary?.contacts || 0}</p>
      </div>
    </div>
  );
};

export default CustomAutomationWarmupPage;
