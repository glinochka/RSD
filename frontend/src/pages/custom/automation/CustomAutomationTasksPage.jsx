import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import FeatureToggle from '../../../components/FeatureToggle';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customAccountManager.css';
import '../../../styles/customTasks.css';

const STATUS_LABELS = {
  pending: 'Ожидает',
  running: 'В работе',
  awaiting_approval: 'На модерации',
  completed: 'Завершено',
  error: 'Ошибка',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
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
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
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

const paramEntries = (params) => Object.entries(params || {}).filter(([, value]) => value !== undefined && value !== null && value !== '');
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
  const [form, setForm] = useState({ query: '', max_chats: 30, require_approval: true, relevance_threshold: 0.6 });

  const loadJobs = useCallback(async () => {
    try {
      setIsLoading(true);
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
      setIsLoading(false);
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

  useEffect(() => {
    const hasActive = items.some((item) => ['pending', 'running', 'awaiting_approval'].includes(item.status));
    if (!hasActive) {
      return undefined;
    }
    const timer = window.setInterval(loadJobs, 5000);
    return () => window.clearInterval(timer);
  }, [items, loadJobs]);

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
          «Активные» — текущий прогресс с логами и отменой, «История» — завершённые с параметрами и результатом.
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
              onClick={() => { setSelectedId(item.id); setSelectedChats([]); }}
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
                <button type="button" className="tsk-close" onClick={() => setSelectedId(null)}>×</button>
              </div>

              <div>
                <div className="tsk-section-label">Логи</div>
                <div className="tsk-logs">
                  {(selected.logs || []).length === 0 ? 'Логи не сохранились — они хранятся 24 часа' : null}
                  {(selected.logs || []).map((row, index) => (
                    <div key={`${row.ts}-${index}`} className={`tsk-log-row ${row.level === 'error' ? 'tsk-log-row--error' : ''}`}>
                      <span>{formatWhen(row.ts)}</span>
                      <span>{row.message}</span>
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

              {paramEntries(selected.params).length ? (
                <div>
                  <div className="tsk-section-label">Параметры запуска</div>
                  <dl className="tsk-kv">
                    {paramEntries(selected.params).map(([key, value]) => (
                      <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>
                    ))}
                  </dl>
                </div>
              ) : null}

              {resultEntries(selected.result).length || selected.error ? (
                <div>
                  <div className="tsk-section-label">Результат</div>
                  <dl className="tsk-kv">
                    {resultEntries(selected.result).map(([key, value]) => (
                      <div key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>
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
                {selected.can_cancel ? (
                  <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => runAction(() => customService.cancelAutomationJob(id, selected.id), 'Задача отменена')}>
                    Отменить
                  </button>
                ) : null}
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
