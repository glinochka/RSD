import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { ubtModulePath } from './customNav';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const DELAY_PRESETS = {
  min: { delay_before_min: 60, delay_before_max: 120 },
  rec: { delay_before_min: 180, delay_before_max: 240 },
  max: { delay_before_min: 300, delay_before_max: 520 },
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

const Stepper = ({ value, min = 0, max = 999, onChange }) => (
  <div className="nc-step">
    <button type="button" onClick={() => onChange(Math.max(min, Number(value || 0) - 1))}>−</button>
    <strong>{value}</strong>
    <button type="button" onClick={() => onChange(Math.min(max, Number(value || 0) + 1))}>+</button>
  </div>
);

const CustomAutomationNeurocommentingPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [settings, setSettings] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('neurocommenting');
  const [chatTab, setChatTab] = useState('links');
  const [links, setLinks] = useState('');
  const [folderId, setFolderId] = useState('');
  const [dbQuery, setDbQuery] = useState('');
  const [promptName, setPromptName] = useState('');
  const [blackQuery, setBlackQuery] = useState('');
  const [presetName, setPresetName] = useState('');

  const applyPayload = (payload) => {
    setData(payload);
    setSettings(payload.settings);
    setEnabled(Boolean(payload.enabled));
  };

  const load = useCallback(async () => {
    const payload = await customService.getNeurocommentingModule(id);
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

  const patch = (partial) => setSettings((prev) => ({ ...prev, ...partial }));
  const selectedAccounts = new Set(settings?.account_ids || []);
  const selectedChats = new Set(settings?.chat_ids || []);

  const accounts = useMemo(() => {
    const items = data?.accounts || [];
    const needle = accountQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (settings?.require_proxy && !item.has_proxy) {
        return false;
      }
      if (settings?.hide_in_work && item.in_work) {
        return false;
      }
      if (roleFilter && !(item.roles || []).includes(roleFilter) && roleFilter !== 'all') {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${item.label} ${item.username || ''} ${item.phone_number || ''} ${item.id}`.toLowerCase().includes(needle);
    });
  }, [data, accountQuery, roleFilter, settings]);

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

  const persist = async (next = {}) => {
    const payload = { ...settings, enabled, ...next };
    const result = await customService.saveNeurocommentingModule(id, payload);
    applyPayload(result);
    return result;
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

  if (!settings || !data) {
    return (
      <div className="nc-page">
        <div className="nc-card"><p className="nc-muted">Загрузка нейрокомментинга...</p></div>
      </div>
    );
  }

  return (
    <div className="nc-page">
      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Выбор аккаунтов <span className="nc-muted">{selectedAccounts.size} выбрано</span></h2>
          <FeatureToggle compact title={enabled ? 'Модуль включён' : 'Модуль выключен'} checked={enabled} onChange={(value) => { setEnabled(value); persist({ enabled: value }); }} />
        </div>
        <div className="nc-split">
          <div className="nc-pane">
            <div className="nc-pane-head">
              <strong>Доступные аккаунты {accounts.length}</strong>
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => load()}>Обновить</button>
            </div>
            <div className="nc-row">
              <input className="nc-search" value={accountQuery} onChange={(event) => setAccountQuery(event.target.value)} placeholder="Поиск по ID, телефону, username..." />
              <select className="nc-select" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="all">Все роли</option>
                <option value="neurocommenting">Нейрокомментинг</option>
                <option value="lead_intercept">Перехват</option>
                <option value="shilling">Шиллинг</option>
              </select>
            </div>
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ account_ids: accounts.filter((item) => item.eligible).map((item) => item.id) })}>Добавить все</button>
              <label className="check"><input type="checkbox" checked={Boolean(settings.require_proxy)} onChange={(event) => patch({ require_proxy: event.target.checked })} /> Рабочие прокси</label>
              <label className="check"><input type="checkbox" checked={Boolean(settings.hide_in_work)} onChange={(event) => patch({ hide_in_work: event.target.checked })} /> Скрыть в работе</label>
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
              <strong>Выбрано для комментирования {chosenAccounts.length}</strong>
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
            <button key={item.name} type="button" className="nc-chip" onClick={() => setSettings({ ...item.settings, presets: settings.presets })}>{item.name}</button>
          ))}
          <input className="nc-input" value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Имя заготовки" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(async () => { await persist(); return customService.saveNeurocommentingPreset(id, presetName); }, 'Заготовка сохранена')}>Сохранить заготовку</button>
        </div>
      </div>

      <div className="nc-split">
        <div className="nc-card">
          <div className="nc-card-head"><h2>Режим комментирования</h2></div>
          <div className="nc-row">
            <button type="button" className={`nc-chip ${settings.post_filter === 'new' ? 'is-on' : ''}`} onClick={() => patch({ post_filter: 'new' })}>Новые посты</button>
            <button type="button" className={`nc-chip ${settings.post_filter === 'keywords' ? 'is-on' : ''}`} onClick={() => patch({ post_filter: 'keywords' })}>По ключевым словам</button>
          </div>
          <div className="nc-slider" style={{ marginTop: 12 }}>
            <span className="nc-muted">Вероятность комментирования {settings.probability}%</span>
            <input type="range" min="0" max="100" value={settings.probability} onChange={(event) => patch({ probability: Number(event.target.value) })} />
          </div>
          {settings.post_filter === 'keywords' ? (
            <textarea className="nc-area" style={{ marginTop: 12 }} value={(settings.keywords || []).join(', ')} onChange={(event) => patch({ keywords: event.target.value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean) })} placeholder="Ключевые слова через запятую" />
          ) : <p className="nc-muted" style={{ marginTop: 12 }}>Комментируем только свежие посты, которые вотчер ещё не видел.</p>}
        </div>
        <div className="nc-card">
          <div className="nc-card-head"><h2>Лимиты</h2></div>
          <div className="nc-row">
            <span className="nc-muted">Макс. комментариев на чат / день</span>
            <Stepper value={settings.max_per_chat} min={1} max={50} onChange={(value) => patch({ max_per_chat: value })} />
          </div>
          <div className="nc-row" style={{ marginTop: 10 }}>
            <span className="nc-muted">Мин. слов в посте</span>
            <Stepper value={settings.min_words} min={0} max={500} onChange={(value) => patch({ min_words: value })} />
          </div>
          <p className="nc-muted" style={{ marginTop: 12 }}>Суточный лимит аккаунта берётся из прогрева и ротации.</p>
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Целевые каналы <span className="nc-muted">{selectedChats.size}</span></h2>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>Чаты</Link>
        </div>
        <div className="nc-row">
          <button type="button" className={`nc-chip ${chatTab === 'links' ? 'is-on' : ''}`} onClick={() => setChatTab('links')}>Юзернейм / ссылка</button>
          <button type="button" className={`nc-chip ${chatTab === 'jobs' ? 'is-on' : ''}`} onClick={() => setChatTab('jobs')}>Прошлые задачи</button>
          <button type="button" className={`nc-chip ${chatTab === 'folder' ? 'is-on' : ''}`} onClick={() => setChatTab('folder')}>Папки</button>
        </div>
        {chatTab === 'links' ? (
          <div style={{ marginTop: 12 }}>
            <textarea className="nc-area" value={links} onChange={(event) => setLinks(event.target.value)} placeholder="@username или https://t.me/channel — каждая ссылка с новой строки" />
            <div className="nc-row" style={{ marginTop: 8 }}>
              <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={() => runSafe(() => customService.addNeurocommentingChannels(id, links).then((payload) => { applyPayload(payload); setLinks(''); return payload; }), 'Каналы добавлены')}>+ Добавить</button>
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
                <span>{(item.params?.chat_ids || []).length} кан.</span>
              </button>
            ))}
          </div>
        ) : null}
        {chatTab === 'folder' ? (
          <div style={{ marginTop: 12 }}>
            <div className="nc-row">
              <select className="nc-select" value={folderId} onChange={(event) => setFolderId(event.target.value)}>
                <option value="">Все папки</option>
                {(data.folders || []).map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
              </select>
              <input className="nc-search" value={dbQuery} onChange={(event) => setDbQuery(event.target.value)} placeholder="Поиск канала" />
              <button type="button" className="acc-btn acc-btn--ghost" onClick={() => patch({ chat_ids: dbChats.map((item) => item.id) })}>Добавить найденные</button>
            </div>
            <div className="nc-list" style={{ marginTop: 8 }}>
              {dbChats.map((item) => (
                <button key={item.id} type="button" className={`nc-item ${selectedChats.has(item.id) ? 'is-on' : ''}`} onClick={() => toggleChat(item.id)}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.join_status} · {item.comments_open === false ? 'комментарии закрыты' : item.comments_open ? 'открыты' : 'не проверены'}</span>
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
            <button type="button" className="acc-btn acc-btn--ghost" style={{ marginTop: 8 }} disabled={busy} onClick={() => runSafe(() => customService.createNeurocommentingPrompt(id, { name: promptName || 'Мой промпт' }).then(applyPayload), 'Промпт создан')}>+ Создать</button>
          </div>
        </div>
        <div className="nc-split" style={{ marginTop: 14 }}>
          <div className="nc-setting" style={{ border: 0, padding: 0 }}>
            <div className="nc-setting-copy">
              <strong>Прогрев новых аккаунтов</strong>
              <span>Общий разгон живёт в подразделе «Прогрев», здесь его не дублируем.</span>
            </div>
            <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'warmup')}>Прогрев</Link>
          </div>
          <FeatureToggle compact title="Ночной простой" description="С 21:30 до 07:00 по Москве комментарии не отправляются." checked={Boolean(settings.respect_night_hours)} onChange={(value) => patch({ respect_night_hours: value })} />
        </div>
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Настройка задержек</h2>
          <div className="nc-row">
            <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.min)}>Мин</button>
            <button type="button" className="nc-chip is-on" onClick={() => patch(DELAY_PRESETS.rec)}>Рекомендуемые</button>
            <button type="button" className="nc-chip" onClick={() => patch(DELAY_PRESETS.max)}>Макс</button>
          </div>
        </div>
        <div className="nc-row">
          <span className="nc-muted">Задержка перед комментарием</span>
          <Stepper value={settings.delay_before_min} min={0} max={3600} onChange={(value) => patch({ delay_before_min: value, delay_before_max: Math.max(value, settings.delay_before_max) })} />
          <span className="nc-muted">до</span>
          <Stepper value={settings.delay_before_max} min={settings.delay_before_min} max={3600} onChange={(value) => patch({ delay_before_max: value })} />
          <span className="nc-muted">сек</span>
        </div>
        <p className="nc-muted" style={{ marginTop: 10 }}>Это антибот-пауза после публикации поста. FloodWait Telegram обрабатывается сам: короткие ждут на месте, длинные откладывают задачу.</p>
      </div>

      <div className="nc-card">
        <div className="nc-card-head"><h2>Запуск и логи</h2></div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{selectedAccounts.size}</strong><span>Аккаунты</span></div>
          <div className="nc-kpi"><strong>{selectedChats.size}</strong><span>Каналы</span></div>
          <div className="nc-kpi"><strong>{settings.delay_before_max}s</strong><span>Макс. интервал</span></div>
          <div className="nc-kpi"><strong>{settings.max_per_chat}</strong><span>Лимит на канал</span></div>
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
              disabled={busy}
              onClick={() => runSafe(async () => {
                await persist();
                await customService.runNeurocommentingModule(id, { ...settings, enabled });
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
          <Link className="acc-btn acc-btn--ghost" to={ubtModulePath(id, 'stats')}>История комментариев</Link>
        </div>
        <div className="nc-kpis">
          <div className="nc-kpi"><strong>{data.summary?.attempts || 0}</strong><span>Всего попыток</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success || 0}</strong><span>Успешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.failed || 0}</strong><span>Неуспешных</span></div>
          <div className="nc-kpi"><strong>{data.summary?.success_pct || 0}%</strong><span>Процент успешных</span></div>
        </div>
        <div className="nc-row" style={{ marginTop: 14 }}>
          <input className="nc-search" value={blackQuery} onChange={(event) => setBlackQuery(event.target.value)} placeholder="Добавить канал в чёрный список" />
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.blackboxNeurocommentingChat(id, { query: blackQuery }).then((payload) => { applyPayload(payload); setBlackQuery(''); return payload; }), 'Канал в чёрном списке')}>+ В ЧС</button>
          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runSafe(() => customService.startChatInspect(id), 'Проверка комментариев запущена')}>Проверить комментарии</button>
        </div>
        {(data.blacklist || []).length === 0 ? <p className="nc-muted" style={{ marginTop: 10 }}>Чёрный список пуст. Закрытые комментарии и ошибки доступа попадают сюда сами.</p> : (
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
    </div>
  );
};

export default CustomAutomationNeurocommentingPage;
