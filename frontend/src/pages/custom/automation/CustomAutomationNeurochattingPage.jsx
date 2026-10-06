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
import { assertCanRun, mergeSettings, useLiveRef } from './ubtPersist';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_before_min: 20, delay_before_max: 40 },
  rec: { delay_before_min: 42, delay_before_max: 78 },
  max: { delay_before_min: 90, delay_before_max: 150 },
};

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

const CustomAutomationNeurochattingPage = () => {
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
  const [promptName, setPromptName] = useState('');
  const [blackQuery, setBlackQuery] = useState('');
  const [presetName, setPresetName] = useState('');
  const [blackAccountQuery, setBlackAccountQuery] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
  };

  const load = useCallback(async () => {
    const payload = await customService.getNeurochattingModule(id);
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
  const blockedAccountRows = (data?.accounts || []).filter((item) => blockedAccounts.has(item.id));
  const issues = data?.issues || [];
  const settingsRef = useLiveRef(settings);
  const enabledRef = useLiveRef(enabled);

  const persist = async (next = {}) => {
    const payload = { ...settingsRef.current, enabled: enabledRef.current, ...next };
    const result = await customService.saveNeurochattingModule(id, payload);
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

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка нейрочаттинга...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Нейрочаттинг</h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <p className="nc-intro">Автоматический чаттинг в Telegram-группах. Аккаунты следят за разговором и отвечают короткими естественными репликами — без ссылок и рекламы.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Выбор аккаунтов <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
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
            {accounts.length === 0 ? <div className="nc-empty">Нет аккаунтов, соответствующих фильтрам</div> : (
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
              <strong>Выбрано для чаттинга {chosenAccounts.length}</strong>
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
          <span className="nc-muted">Пресеты настроек</span>
          {(settings.presets || []).map((item) => (
            <button key={item.name} type="button" className="nc-chip" onClick={() => { setSettings({ ...item.settings, presets: settings.presets }); setDirty(true); }}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Название пресета" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveNeurochattingPreset(id, presetName); }, 'Пресет сохранён')}>Сохранить</button>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head"><h2>Режим реакции</h2></div>
          <div className="nc-mode">
            <button type="button" className={settings.reply_mode === 'interval' ? 'is-on' : ''} onClick={() => patch({ reply_mode: 'interval' })}>По интервалу</button>
            <button type="button" className={settings.reply_mode === 'triggers' ? 'is-on' : ''} onClick={() => patch({ reply_mode: 'triggers' })}>На триггеры</button>
          </div>
          <div className="nc-slider" style={{ marginTop: 14 }}>
            <span className="nc-muted">Вероятность ответа {settings.probability}%</span>
            <input type="range" min="0" max="100" value={settings.probability} onChange={(event) => patch({ probability: Number(event.target.value) })} />
          </div>
          {settings.reply_mode === 'triggers' ? (
            <textarea className="nc-area" style={{ marginTop: 12 }} value={(settings.keywords || []).join(', ')} onChange={(event) => patch({ keywords: event.target.value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean) })} placeholder="Ключевые слова и фразы — отвечаем, только если они есть в сообщении" />
          ) : <p className="nc-muted" style={{ marginTop: 12 }}>Периодический проход по группам. Ответ выбирается случайно с заданной вероятностью.</p>}
        </div>
        <div className="nc-card">
          <div className="nc-card-head"><h2>Режим работы</h2></div>
          <div className="nc-mode">
            <button type="button" className={settings.work_mode === 'count' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'count' })}>По количеству</button>
            <button type="button" className={settings.work_mode === 'time' ? 'is-on' : ''} onClick={() => patch({ work_mode: 'time', work_always: false })}>По времени</button>
          </div>
          <div className="nc-row" style={{ marginTop: 14 }}>
            <span className="nc-muted">Макс. сообщений на группу / день</span>
            <Stepper value={settings.max_per_chat} min={1} max={20} onChange={(value) => patch({ max_per_chat: value })} />
          </div>
          {settings.work_mode === 'time' ? (
            <div style={{ marginTop: 12 }}>
              <FeatureToggle compact title="Работать всегда" description="Игнорировать окна активности. Ночной простой по Москве можно оставить отдельно." checked={Boolean(settings.work_always)} onChange={(value) => persistFlag({ work_always: value })} />
            </div>
          ) : <p className="nc-muted" style={{ marginTop: 12 }}>По умолчанию не больше одного ответа на группу в сутки — чтобы не выглядеть ботом.</p>}
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Целевые группы <span className="nc-muted">{selectedFolders.size} пап. · {selectedChats.size} гр.</span></h2>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты и каналы</Link>
        </div>
        <div className="nc-row">
          <button type="button" className={`nc-chip ${chatTab === 'links' ? 'is-on' : ''}`} onClick={() => setChatTab('links')}>Юзернейм / ссылка</button>
          <button type="button" className={`nc-chip ${chatTab === 'jobs' ? 'is-on' : ''}`} onClick={() => setChatTab('jobs')}>Прошлые задачи</button>
          <button type="button" className={`nc-chip ${chatTab === 'folder' ? 'is-on' : ''}`} onClick={() => setChatTab('folder')}>Папки</button>
        </div>
        {chatTab === 'links' ? (
          <div style={{ marginTop: 12 }}>
            <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder="@group или https://t.me/group — каждая ссылка с новой строки" />
            <div className="nc-row" style={{ marginTop: 8 }}>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addNeurochattingGroups(id, links).then((payload) => { applyPayload(payload); setLinks(''); return payload; }), 'Группы добавлены')}>+ Добавить</button>
              <span className="nc-muted">Строк: {links.split('\n').filter((item) => item.trim()).length}</span>
            </div>
          </div>
        ) : null}
        {chatTab === 'jobs' ? (
          <div className="nc-list" style={{ marginTop: 12 }}>
            {jobs.length === 0 ? <div className="nc-empty">Прошлых запусков нет</div> : jobs.map((item) => (
              <button key={item.id} type="button" className="nc-item" onClick={() => patch({ chat_ids: item.params?.chat_ids || settings.chat_ids, account_ids: item.params?.account_ids || settings.account_ids })}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{STATUS_LABELS[item.status] || item.status} · {formatWhen(item.created_at)}</span>
                </div>
                <span>{(item.params?.chat_ids || []).length} гр.</span>
              </button>
            ))}
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
        {chosenChats.length ? (
          <div className="nc-list" style={{ marginTop: 12 }}>
            {chosenChats.map((item) => (
              <button key={item.id} type="button" className="nc-item is-on" onClick={() => toggleChat(item.id)}>
                <div><strong>{item.title}</strong><span>{item.invite_link || ''}</span></div>
                <span>×</span>
              </button>
            ))}
          </div>
        ) : null}
        <div style={{ marginTop: 12 }}>
          <FeatureToggle compact title="Не вступать — писать только туда, где аккаунт уже состоит" description="Новые вступления не ставим в очередь. Группы без членства пропускаются." checked={Boolean(settings.only_joined)} onChange={(value) => persistFlag({ only_joined: value })} />
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Настройки сообщений</h2>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(id)}>Все промпты</Link>
        </div>
        <div className="nc-prompts">
          {(data.prompts || []).map((prompt) => (
            <button key={prompt.id} type="button" className={`nc-prompt ${settings.prompt_id === prompt.id || (!settings.prompt_id && prompt.is_active) ? 'is-on' : ''}`} onClick={() => patch({ prompt_id: prompt.id })}>
              <strong>{prompt.name}</strong>
              <div className="nc-muted">{prompt.is_system ? 'Системный' : 'Мой промпт'}</div>
            </button>
          ))}
          <div className="nc-prompt">
            <input className="nc-input" value={promptName} onChange={(event) => setPromptName(event.target.value)} placeholder="Новый промпт" />
            <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 8 }} disabled={busy} onClick={() => runSafe(() => customService.createNeurochattingPrompt(id, { name: promptName || 'Мой промпт' }).then(applyPayload), 'Промпт создан')}>+ Создать</button>
          </div>
        </div>
        <label className="nc-muted" style={{ display: 'block', marginTop: 14 }}>Отвечать только если...</label>
        <textarea className="nc-area" style={{ marginTop: 8 }} value={settings.reply_condition || ''} onChange={(event) => patch({ reply_condition: event.target.value })} placeholder="Например: человек задаёт вопрос по теме чата. На рекламу и объявления не отвечать." />
        <div style={{ marginTop: 14 }}>
          <FeatureToggle compact title="Ночной простой" description="С 21:30 до 07:00 по Москве ответы не отправляются." checked={Boolean(settings.respect_night_hours)} onChange={(value) => persistFlag({ respect_night_hours: value })} />
        </div>
        <div className="nc-slider" style={{ marginTop: 16 }}>
          <span className="nc-muted">Контекст разговора: {settings.context_depth === 0 ? 'без контекста' : `${settings.context_depth} сообщений`}</span>
          <input type="range" min="0" max="12" value={settings.context_depth || 0} onChange={(event) => patch({ context_depth: Number(event.target.value) })} />
        </div>
        <p className="nc-muted" style={{ marginTop: 8 }}>0 = как раньше, одно сообщение. Больше контекста — точнее тон ответа.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Настройка задержек</h2>
          <div className="nc-row">
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.rec)}>Рекомендуемые</button>
            <button type="button" className={`nc-chip ${matchesPreset(settings, DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => patch(DELAY_PRESETS.max)}>Макс</button>
          </div>
        </div>
        <div className="nc-row">
          <span className="nc-muted">Задержка перед отправкой</span>
          <Stepper value={settings.delay_before_min} min={0} max={3600} onChange={(value) => patch({ delay_before_min: value, delay_before_max: Math.max(value, settings.delay_before_max) })} />
          <span className="nc-muted">до</span>
          <Stepper value={settings.delay_before_max} min={settings.delay_before_min} max={3600} onChange={(value) => patch({ delay_before_max: value })} />
          <span className="nc-muted">сек</span>
        </div>
        <p className="nc-muted" style={{ marginTop: 10 }}>Не отвечаем на слишком свежие сообщения — антибот-пауза. FloodWait Telegram обрабатывается сам.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{selectedFolders.size || selectedChats.size}</strong><span>Папки / группы</span></div>
          <div className="nc-kpi"><strong>{settings.delay_before_max}s</strong><span>Макс. интервал</span></div>
          <div className="nc-kpi"><strong>{settings.max_per_chat}</strong><span>Макс. сообщений</span></div>
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
                await customService.runNeurochattingModule(id, { ...saved.settings, enabled: saved.enabled });
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
          <h2>История сообщений</h2>
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'stats')}>История сообщений</Link>
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
            <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.blackboxNeurochattingChat(id, { query: blackQuery }).then((payload) => { applyPayload(payload); setBlackQuery(''); return payload; }), 'Группа в чёрном списке')}>+ В ЧС</button>
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
          {blockedAccountRows.length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Эти аккаунты не будут читать чаты и отвечать, даже если попадут в пул.</p> : (
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

export default CustomAutomationNeurochattingPage;
