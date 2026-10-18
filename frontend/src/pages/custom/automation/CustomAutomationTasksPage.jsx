import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import FeatureToggle from '../../../components/FeatureToggle';
import UbtJobControls from '../../../components/custom/UbtJobControls';
import UbtDistributeChats from '../../../components/custom/UbtDistributeChats';
import { paramLabel, resultLabel } from './jobParamLabels';
import { humanizeUbtLog } from './ubtLogText';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customAccountManager.css';
import '../../../styles/customTasks.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  paused: 'На паузе',
  awaiting_approval: 'На модерации',
  completed: 'Завершено',
  error: 'Ошибка',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
};

const SKIP_EDIT_KEYS = new Set(['presets', 'enabled', 'joins_complete', 'chat_assignments', 'reserve_chat_ids']);
const HIDE_PARAM_KEYS = new Set([
  'presets',
  'chat_assignments',
  'reserve_chat_ids',
  'account_ids',
  'chat_ids',
  'folder_ids',
  'channel_ids',
  'blacklisted_account_ids',
  'keywords',
  'messages',
  'recipients',
  'joins_complete',
  'enabled',
]);
const MINUTE_PARAM_KEYS = new Set([
  'join_delay_min',
  'join_delay_max',
  'comment_delay_min',
  'comment_delay_max',
  'delay_before_min',
  'delay_before_max',
]);
const PARAM_ORDER = [
  'max_per_account',
  'comment_delay_min',
  'comment_delay_max',
  'max_per_chat',
  'max_replies_per_run',
  'join_delay_min',
  'join_delay_max',
  'delay_before_min',
  'delay_before_max',
  'probability',
  'post_filter',
  'min_words',
  'respect_night_hours',
  'require_proxy',
  'hide_in_work',
];
const JOB_TASK_KEY = {
  neurocommenting: 'neurocommenting',
  discussion: 'neurochatting',
  shilling: 'neuroshilling',
  chat_monitoring: 'chat_monitoring',
  chat_broadcast: 'chat_broadcasts',
  parser: 'parser',
  masslooking: 'masslooking',
  warmup: 'warmup',
};
const EXTRA_EDIT_FIELDS = {
  neurocommenting: { delay_before_min: 180, delay_before_max: 240, join_delay_min: 1200, join_delay_max: 2400, comment_delay_min: 1200, comment_delay_max: 2400, probability: 100, max_per_chat: 10, max_per_account: 15 },
  chat_monitoring: { join_delay_min: 1200, join_delay_max: 2400, comment_delay_min: 1200, comment_delay_max: 2400, max_per_account: 15, respect_night_hours: true },
  discussion: { delay_before_min: 42, delay_before_max: 78, join_delay_min: 1200, join_delay_max: 2400, comment_delay_min: 1200, comment_delay_max: 2400, probability: 30, max_per_chat: 1, max_per_account: 15 },
  shilling: { delay_min: 8, delay_max: 25, join_delay_min: 1200, join_delay_max: 2400, comment_delay_min: 1200, comment_delay_max: 2400, max_per_account: 15 },
  chat_broadcast: { delay_group_min: 30, delay_group_max: 90, delay_msg_min: 3, delay_msg_max: 8, join_delay_min: 1200, join_delay_max: 2400, comment_delay_min: 1200, comment_delay_max: 2400, max_per_account: 15 },
  dm_broadcast: { delay_peer_min: 30, delay_peer_max: 90, delay_msg_min: 3, delay_msg_max: 8, comment_delay_min: 1200, comment_delay_max: 2400, max_per_account: 15 },
  masslooking: { delay_min: 2, delay_max: 6, join_delay_min: 1200, join_delay_max: 2400, max_per_account: 50 },
  masspriming: { delay_min: 8, delay_max: 25, max_per_account: 20 },
  parser: { delay_chat: 5, delay_user: 1, join_delay_min: 1200, join_delay_max: 2400, member_limit: 1000 },
  warmup: { join_delay_min: 1200, join_delay_max: 2400 },
};

const formatParamValue = (value) => {
  if (typeof value === 'boolean') {
    return value ? 'Да' : 'Нет';
  }
  if (Array.isArray(value) || (value && typeof value === 'object')) {
    return JSON.stringify(value);
  }
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
};

const formatShownParam = (key, value) => {
  if (typeof value === 'boolean') {
    return value ? 'Да' : 'Нет';
  }
  if (MINUTE_PARAM_KEYS.has(key) && Number.isFinite(Number(value))) {
    const mins = Math.max(1, Math.round(Number(value) / 60));
    return `${mins} мин`;
  }
  if (Array.isArray(value) || (value && typeof value === 'object')) {
    return JSON.stringify(value);
  }
  return String(value);
};

const shownParams = (job) => ({
  ...(EXTRA_EDIT_FIELDS[job?.job_type] || {}),
  ...(job?.params || {}),
});

const parseParamValue = (raw, original) => {
  if (typeof original === 'boolean') {
    return raw === true || raw === 'true' || raw === '1' || raw === 'Да';
  }
  if (typeof original === 'number') {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : original;
  }
  if (Array.isArray(original) || (original && typeof original === 'object')) {
    try {
      return JSON.parse(raw);
    } catch {
      return original;
    }
  }
  const trimmed = String(raw ?? '').trim();
  if (trimmed === '') {
    return '';
  }
  const asNumber = Number(trimmed);
  if (Number.isFinite(asNumber) && String(asNumber) === trimmed) {
    return asNumber;
  }
  if (trimmed === 'true' || trimmed === 'false') {
    return trimmed === 'true';
  }
  return raw;
};

const buildEditForm = (job) => {
  const extras = EXTRA_EDIT_FIELDS[job?.job_type] || {};
  const params = { ...extras, ...(job?.params || {}) };
  const form = {};
  Object.entries(params).forEach(([key, value]) => {
    if (SKIP_EDIT_KEYS.has(key)) {
      return;
    }
    form[key] = formatParamValue(value);
  });
  return form;
};

const BUCKETS = [
  { id: 'active', label: 'Активные' },
  { id: 'history', label: 'История' },
  { id: 'all', label: 'Все' },
];

const CATEGORIES = [
  { id: '', label: 'Все типы' },
  { id: 'module', label: 'Модули' },
  { id: 'account', label: 'Аккаунты' },
];

const formatWhen = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${day}.${month}, ${hours}:${minutes}`;
};

const formatDuration = (seconds) => {
  const total = Math.max(0, Number(seconds) || 0);
  if (total < 60) {
    return `${total} с`;
  }
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins < 60) {
    return secs ? `${mins} мин ${secs} с` : `${mins} мин`;
  }
  const hours = Math.floor(mins / 60);
  return `${hours} ч ${mins % 60} мин`;
};

const paramEntries = (params) => {
  const entries = Object.entries(params || {}).filter(([key, value]) => {
    if (HIDE_PARAM_KEYS.has(key) || value === undefined || value === null || value === '') {
      return false;
    }
    if (Array.isArray(value) && value.length === 0) {
      return false;
    }
    return true;
  });
  entries.sort((a, b) => {
    const ia = PARAM_ORDER.indexOf(a[0]);
    const ib = PARAM_ORDER.indexOf(b[0]);
    if (ia === -1 && ib === -1) {
      return 0;
    }
    if (ia === -1) {
      return 1;
    }
    if (ib === -1) {
      return -1;
    }
    return ia - ib;
  });
  return entries;
};
const resultEntries = (result) => paramEntries(result).filter(([key]) => key !== 'items');

const CustomAutomationTasksPage = () => {
  const { id } = useParams();
  const [bucket, setBucket] = useState('active');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedChats, setSelectedChats] = useState([]);
  const [panel, setPanel] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [form, setForm] = useState({ query: '', max_chats: 30, require_approval: true, relevance_threshold: 0.6 });

  const loadJobs = useCallback(async ({ silent } = {}) => {
    try {
      if (!silent) {
        setIsLoading(true);
      }
      const data = await customService.getAutomationJobs(id, {
        bucket,
        category: category || undefined,
        search: search || undefined,
        limit: 80,
      });
      setItems(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить задачи');
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  }, [id, bucket, category, search]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId],
  );

  useEffect(() => {
    if (selectedId && !items.some((item) => item.id === selectedId)) {
      setSelectedId(null);
    }
  }, [items, selectedId]);

  const hasActiveRef = useRef(false);
  hasActiveRef.current = items.some((item) => ['pending', 'running', 'awaiting_approval'].includes(item.status));

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (hasActiveRef.current) {
        loadJobs({ silent: true });
      }
    }, 8000);
    return () => window.clearInterval(timer);
  }, [loadJobs]);

  const runAction = async (fn, okText) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
      if (okText) {
        setMessage(okText);
      }
      setPanel(null);
      await loadJobs();
    } catch (err) {
      setError(err.message || 'Не удалось выполнить действие');
    } finally {
      setBusy(false);
    }
  };

  const handleStartDiscovery = (event) => {
    event.preventDefault();
    runAction(
      () => customService.createDiscoveryTask(id, {
        query: form.query,
        mode: 'monitoring',
        max_chats: Number(form.max_chats),
        require_approval: form.require_approval,
        relevance_threshold: Number(form.relevance_threshold),
      }),
      'Поиск чатов запущен',
    );
  };

  const chats = selected?.result?.items || [];

  return (
    <div className="tsk-page">
      <div className="tsk-intro">
        <h1>Задачи</h1>
        <p>
          Фоновые запуски модулей и операции над аккаунтами. Они выполняются на сервере — окно можно закрыть, задачи не прервутся.
          Активную задачу можно поставить на паузу и позже продолжить, изменить параметры или остановить совсем.
        </p>
      </div>

      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="tsk-filters">
        {BUCKETS.map((item) => (
          <button key={item.id} type="button" className={`tsk-chip ${bucket === item.id ? 'is-active' : ''}`} onClick={() => setBucket(item.id)}>
            {item.label}
          </button>
        ))}
        {CATEGORIES.map((item) => (
          <button
            key={item.id || 'all-types'}
            type="button"
            className={`tsk-chip tsk-chip--ghost ${category === item.id ? 'is-active' : ''}`}
            onClick={() => setCategory(item.id)}
          >
            {item.label}
          </button>
        ))}
        <input className="tsk-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию..." />
        <button type="button" className="acc-btn acc-btn--ghost" onClick={() => setPanel('launch')}>Запустить</button>
      </div>

      <div className="tsk-split">
        <div className="tsk-list">
          {isLoading ? <div className="tsk-empty-list">Загрузка...</div> : null}
          {!isLoading && items.length === 0 ? (
            <div className="tsk-empty-list">
              <span>Нет {bucket === 'active' ? 'активных ' : ''}задач</span>
            </div>
          ) : null}
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`tsk-card ${selectedId === item.id ? 'is-active' : ''}`}
              onClick={() => { setSelectedId(item.id); setSelectedChats([]); setEditing(false); }}
            >
              <div className="tsk-card-top">
                <div className="tsk-card-title">
                  <span className="tsk-badge">{item.badge || 'ЗД'}</span>
                  {item.title}
                </div>
                <span className="tsk-date">{formatWhen(item.created_at).slice(0, 5)}</span>
              </div>
              {item.subtitle ? <div className="tsk-card-sub">{item.subtitle}</div> : <div className="tsk-card-sub" />}
              <div className="tsk-card-meta">
                <span className={`tsk-status tsk-status--${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                <span className="tsk-dur">{formatDuration(item.duration_seconds)}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="tsk-detail">
          {!selected ? (
            <div className="tsk-detail-empty">
              <div className="tsk-stack"><span /><span /><span /></div>
              <span>Выберите задачу слева</span>
            </div>
          ) : (
            <>
              <div className="tsk-detail-head">
                <div>
                  <h2>{selected.title}</h2>
                  <p>{selected.subtitle || formatWhen(selected.created_at)}</p>
                </div>
                <button type="button" className="tsk-close" onClick={() => { setSelectedId(null); setEditing(false); }}>×</button>
              </div>

              <div>
                <div className="tsk-section-label">Логи</div>
                <div className="tsk-logs">
                  {(selected.logs || []).length === 0
                    ? 'Логи не сохранились — они хранятся 3 суток'
                    : (selected.logs || []).map((row, index) => (
                      <div key={`${row.ts}-${index}`} className={row.level === 'error' ? 'tsk-log-err' : ''}>
                        {formatWhen(row.ts)} {humanizeUbtLog(row.message)}
                      </div>
                    ))}
                </div>
              </div>

              <div className="tsk-kpi-row">
                <div className="tsk-kpi">
                  <strong>{STATUS_LABELS[selected.status] || selected.status}</strong>
                  <span>Статус</span>
                </div>
                <div className="tsk-kpi">
                  <strong>{formatDuration(selected.duration_seconds)}</strong>
                  <span>Длительность</span>
                </div>
              </div>

              <div>
                <div className="tsk-section-label">Время</div>
                <dl className="tsk-kv">
                  <div><dt>Создана</dt><dd>{formatWhen(selected.created_at)}</dd></div>
                  <div><dt>Завершена</dt><dd>{formatWhen(selected.completed_at) || '—'}</dd></div>
                </dl>
              </div>

              {editing && selected.can_edit ? (
                <div>
                  <div className="tsk-section-label">Параметры</div>
                  <div className="tsk-edit">
                    {Object.keys(editForm).length === 0 ? <p>Нет редактируемых полей</p> : null}
                    {Object.entries(editForm).map(([key, value]) => (
                      <div key={key} className="tsk-edit-row">
                        <label htmlFor={`tsk-edit-${key}`}>{paramLabel(key)}</label>
                        {String(value).length > 80 ? (
                          <textarea id={`tsk-edit-${key}`} rows={3} value={value} onChange={(event) => setEditForm((prev) => ({ ...prev, [key]: event.target.value }))} />
                        ) : (
                          <input id={`tsk-edit-${key}`} value={value} onChange={(event) => setEditForm((prev) => ({ ...prev, [key]: event.target.value }))} />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : paramEntries(shownParams(selected)).length ? (
                <div>
                  <div className="tsk-section-label">Параметры запуска</div>
                  <dl className="tsk-kv">
                    {paramEntries(shownParams(selected)).map(([key, value]) => (
                      <div key={key}><dt>{paramLabel(key)}</dt><dd>{formatShownParam(key, value)}</dd></div>
                    ))}
                  </dl>
                </div>
              ) : null}

              {JOB_TASK_KEY[selected.job_type] ? (
                <UbtDistributeChats
                  key={`${selected.id}-${JOB_TASK_KEY[selected.job_type]}`}
                  automationId={id}
                  taskKey={JOB_TASK_KEY[selected.job_type]}
                  settings={selected.params}
                  onApplied={() => loadJobs()}
                />
              ) : null}

              {resultEntries(selected.result).length || selected.error ? (
                <div>
                  <div className="tsk-section-label">Результат</div>
                  <dl className="tsk-kv">
                    {resultEntries(selected.result).map(([key, value]) => (
                      <div key={key}><dt>{resultLabel(key)}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>
                    ))}
                    {selected.error ? <div><dt>Ошибка</dt><dd>{selected.error}</dd></div> : null}
                  </dl>
                </div>
              ) : null}

              {chats.length ? (
                <div>
                  <div className="tsk-section-label">Каналы {chats.length}</div>
                  <div className="tsk-channels">
                    {chats.map((chat, index) => (
                      <label key={chat.id || index} className="tsk-channel">
                        {selected.can_approve ? (
                          <input
                            type="checkbox"
                            checked={selectedChats.includes(index)}
                            onChange={() => setSelectedChats((prev) => (prev.includes(index) ? prev.filter((item) => item !== index) : [...prev, index]))}
                          />
                        ) : <span />}
                        <b>{chat.username || chat.title || chat.id}</b>
                        <span>{chat.title || chat.reason || ''}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="tsk-actions">
                {editing && selected.can_edit ? (
                  <>
                    <button
                      type="button"
                      className="acc-btn acc-btn--primary"
                      disabled={busy}
                      onClick={() => {
                        const original = { ...(EXTRA_EDIT_FIELDS[selected.job_type] || {}), ...(selected.params || {}) };
                        const params = {};
                        Object.entries(editForm).forEach(([key, value]) => {
                          params[key] = parseParamValue(value, original[key]);
                        });
                        runAction(async () => {
                          await customService.patchAutomationJob(id, selected.id, { params });
                          setEditing(false);
                        }, 'Параметры сохранены');
                      }}
                    >
                      Сохранить параметры
                    </button>
                    <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => setEditing(false)}>Отмена</button>
                  </>
                ) : (
                  <UbtJobControls
                    job={selected}
                    busy={busy}
                    onPause={() => runAction(() => customService.pauseAutomationJob(id, selected.id), 'Задача на паузе')}
                    onResume={() => runAction(() => customService.resumeAutomationJob(id, selected.id), 'Задача продолжена')}
                    onCancel={() => runAction(() => customService.cancelAutomationJob(id, selected.id), 'Задача остановлена')}
                    onEdit={() => { setEditForm(buildEditForm(selected)); setEditing(true); }}
                  />
                )}
                {selected.can_approve ? (
                  <>
                    <button type="button" className="acc-btn acc-btn--primary" disabled={busy || !selectedChats.length} onClick={() => runAction(() => customService.approveDiscoveryTask(id, selected.source_id, selectedChats), 'Чаты одобрены')}>
                      Одобрить выбранные
                    </button>
                    <button type="button" className="acc-btn acc-btn--ghost" disabled={busy || !selectedChats.length} onClick={() => runAction(() => customService.rejectDiscoveryTask(id, selected.source_id, selectedChats), 'Чаты отклонены')}>
                      Отклонить
                    </button>
                  </>
                ) : null}
                {selected.job_type === 'discovery' ? (
                  <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>К чатам</Link>
                ) : null}
              </div>
            </>
          )}
        </div>
      </div>

      {panel === 'launch' ? (
        <div className="tsk-drawer-backdrop" onClick={() => setPanel(null)}>
          <aside className="tsk-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="tsk-detail-head">
              <div>
                <h2>Запустить задачу</h2>
                <p>Модуль, аккаунты или поиск чатов — прогресс появится в списке слева.</p>
              </div>
              <button type="button" className="tsk-close" onClick={() => setPanel(null)}>×</button>
            </div>
            <div className="tsk-actions" style={{ margin: '12px 0 18px' }}>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.runNeurocommenting(id), 'Нейрокомментинг запущен')}>Нейрокомментинг</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.runDiscussion(id), 'Активность запущена')}>Активность в чатах</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.runShilling(id), 'Шиллинг запущен')}>Нейрошиллинг</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.startAccountPrepare(id), 'Подготовка запущена')}>Подготовить аккаунты</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.runAutomationAccountHealthCheck(id), 'Проверка сессий запущена')}>Проверить сессии</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.startChatInspect(id), 'Проверка комментариев запущена')}>Проверить комментарии</button>
              <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.runJoinChats(id), 'Вступление запущено')}>Вступить в чаты</button>
            </div>
            <form onSubmit={handleStartDiscovery}>
              <h3 className="settings-section-title">Поиск чатов</h3>
              <div className="form-group">
                <label htmlFor="tsk-query">Тема / запрос</label>
                <input id="tsk-query" required value={form.query} onChange={(event) => setForm((prev) => ({ ...prev, query: event.target.value }))} />
              </div>
              <div className="form-group">
                <label htmlFor="tsk-max">Макс. чатов</label>
                <input id="tsk-max" type="number" min={1} max={200} value={form.max_chats} onChange={(event) => setForm((prev) => ({ ...prev, max_chats: event.target.value }))} />
              </div>
              <div className="form-group">
                <FeatureToggle title="Ручное одобрение" checked={form.require_approval} onChange={(checked) => setForm((prev) => ({ ...prev, require_approval: checked }))} />
              </div>
              <button type="submit" className="acc-btn acc-btn--primary" disabled={busy}>{busy ? 'Запуск...' : 'Найти чаты'}</button>
            </form>
          </aside>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationTasksPage;
