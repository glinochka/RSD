import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import Stepper from '../../../components/custom/UbtStepper';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customStats.css';
import '../../../styles/customNeuro.css';

const PERIODS = [
  { id: 'all', label: 'За всё время' },
  { id: 'month', label: 'Месяц' },
  { id: 'week', label: 'Неделя' },
  { id: 'today', label: 'Сегодня' },
];

const TABS = [
  { id: 'dashboard', label: 'Дашборд' },
  { id: 'accounts', label: 'Аккаунты' },
  { id: 'history', label: 'История' },
];

const HISTORY_TABS = [
  { id: 'neurocommenting', label: 'История комментариев' },
  { id: 'discussion', label: 'История сообщений' },
  { id: 'shilling', label: 'История нейрошиллинга' },
  { id: 'intercept', label: 'История перехвата' },
  { id: 'dmp', label: 'История DMP' },
  { id: 'masslooking', label: 'История просмотров' },
  { id: 'chat_broadcast', label: 'История чат-рассылок' },
  { id: 'dm_broadcast', label: 'История ЛС-рассылок' },
  { id: 'warmup', label: 'История прогрева' },
  { id: 'masspriming', label: 'История масспрайминга' },
  { id: 'parser', label: 'История парсера юзеров' },
];

const MODULE_LABELS = {
  neurocommenting: 'Комментарии',
  shilling: 'Шиллинг',
  discussion: 'Сообщения',
  intercept: 'Перехват',
  dmp: 'DMP',
  masslooking: 'Просмотры',
  chat_broadcast: 'Чат-рассылки',
  dm_broadcast: 'ЛС-рассылки',
  warmup: 'Прогрев',
  masspriming: 'Прайминг',
  parser: 'Парсер юзеров',
};

const MODULE_COLORS = {
  neurocommenting: '#2f2f2f',
  shilling: '#525252',
  discussion: '#737373',
  intercept: '#ea580c',
  dmp: '#059669',
  masslooking: '#64748b',
  chat_broadcast: '#404040',
  dm_broadcast: '#1f2937',
  warmup: '#0f766e',
  masspriming: '#334155',
  parser: '#6b7280',
};

const DIST_LABELS = {
  valid: 'Валидные',
  frozen: 'Заморожены',
  spamblock: 'Спамблок',
  banned: 'Забанены',
  revoked: 'Разавторизованы',
  channel_banned: 'Бан в каналах',
  quarantine: 'Карантин',
};

const DIST_COLORS = {
  valid: '#22c55e',
  frozen: '#38bdf8',
  spamblock: '#f59e0b',
  banned: '#ef4444',
  revoked: '#94a3b8',
  channel_banned: '#64748b',
  quarantine: '#64748b',
};

const Ico = ({ children }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

const formatWhen = (value) => {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const formatDay = (value) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value).slice(5);
  }
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
};

const copyLines = async (items) => {
  const text = (items || []).map((item) => item.title).filter(Boolean).join('\n');
  if (!text) {
    return false;
  }
  await navigator.clipboard.writeText(text);
  return true;
};

const donutBackground = (parts) => {
  const total = parts.reduce((sum, item) => sum + item.value, 0);
  if (!total) {
    return '#f1f5f9';
  }
  let cursor = 0;
  const stops = parts
    .filter((item) => item.value > 0)
    .map((item) => {
      const start = cursor;
      cursor += (item.value / total) * 360;
      return `${item.color} ${start}deg ${cursor}deg`;
    });
  return `conic-gradient(${stops.join(', ')})`;
};

const EmptyState = ({ icon, text }) => (
  <div className="st-empty">
    {icon}
    <span>{text}</span>
  </div>
);

const CustomAutomationStatsPage = () => {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const requestedHistory = searchParams.get('history');
  const [tab, setTab] = useState(requestedHistory ? 'history' : 'dashboard');
  const [period, setPeriod] = useState('all');
  const [historyType, setHistoryType] = useState(
    HISTORY_TABS.some((item) => item.id === requestedHistory) ? requestedHistory : 'neurocommenting'
  );
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [visibility, setVisibility] = useState('');
  const [thresholdInput, setThresholdInput] = useState(50);
  const [threshold, setThreshold] = useState(50);
  const [minAttempts, setMinAttempts] = useState(3);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [blackQuery, setBlackQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const limit = 25;

  const load = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    try {
      const payload = await customService.getUbtStats(id, {
        period,
        historyType,
        search: search || undefined,
        status: status || undefined,
        visibility: visibility || undefined,
        threshold,
        minAttempts,
        limit,
        offset,
      });
      setData(payload);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить статистику');
    } finally {
      setIsLoading(false);
    }
  }, [id, period, historyType, search, status, visibility, threshold, minAttempts, offset]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput), 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const timer = window.setTimeout(() => setThreshold(thresholdInput), 250);
    return () => window.clearTimeout(timer);
  }, [thresholdInput]);

  useEffect(() => {
    setOffset(0);
  }, [period, historyType, search, status, visibility]);

  const dashboard = data?.dashboard || {};
  const accounts = data?.accounts || {};
  const history = data?.history || {};
  const summary = history.summary?.[historyType] || { attempts: 0, success: 0, failed: 0, deleted: 0, success_pct: 0 };
  const series = dashboard.series || [];
  const byModule = dashboard.by_module || {};
  const moduleParts = Object.entries(MODULE_LABELS).map(([key, label]) => ({
    key,
    label,
    value: Number(byModule[key] || 0),
    color: MODULE_COLORS[key],
  }));
  const moduleTotal = moduleParts.reduce((sum, item) => sum + item.value, 0);
  const distParts = Object.entries(DIST_LABELS).map(([key, label]) => ({
    key,
    label,
    value: Number(accounts.distribution?.[key] || 0),
    color: DIST_COLORS[key],
  }));
  const distTotal = distParts.reduce((sum, item) => sum + item.value, 0);
  const incidents = accounts.incidents || [];
  const statusChanges = accounts.status_changes || [];
  const historyItems = history.items || [];
  const historyTotal = history.total || 0;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(historyTotal / limit));

  const seriesMax = useMemo(() => {
    return series.reduce((max, item) => {
      const dayTotal = Object.entries(item)
        .filter(([key]) => key !== 'date')
        .reduce((sum, [, value]) => sum + Number(value || 0), 0);
      return Math.max(max, dayTotal);
    }, 0);
  }, [series]);

  const incidentMax = incidents.reduce((max, item) => {
    const total = Number(item.banned || 0) + Number(item.frozen || 0) + Number(item.spamblock || 0);
    return Math.max(max, total);
  }, 0);

  const exportCsv = () => {
    const rows = [['Аккаунт', 'Канал', 'Текст', 'Статус', 'Дата']];
    historyItems.forEach((item) => {
      rows.push([item.account, item.channel, String(item.text || '').replace(/\n/g, ' '), item.status, item.created_at || '']);
    });
    const blob = new Blob([rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(';')).join('\n')], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ubt-stats-${period}-${historyType}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const addBlack = async (event) => {
    event.preventDefault();
    if (!blackQuery.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await customService.addStatsBlacklist(id, { query: blackQuery.trim() });
      setBlackQuery('');
      setMessage('Канал добавлен в чёрный список');
      await load();
    } catch (err) {
      setError(err.message || 'Не удалось добавить канал');
    } finally {
      setBusy(false);
    }
  };

  if (!data && isLoading) {
    return (
      <div className="st-page">
        <div className="st-hero">
          <div>
            <h1>Моя статистика</h1>
          </div>
        </div>
        <EmptyState icon={<Ico><circle cx="12" cy="12" r="9" /></Ico>} text="Загрузка статистики..." />
      </div>
    );
  }

  return (
    <div className="st-page">
      <div className="st-hero">
        <div>
          <h1>Моя статистика</h1>
          <div className="st-periods">
            {PERIODS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`st-chip ${period === item.id ? 'is-active' : ''}`}
                onClick={() => setPeriod(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="st-hero-actions">
          <button type="button" className="acc-btn acc-btn--primary" onClick={exportCsv}>
            Экспорт
          </button>
          <button type="button" className="acc-btn acc-btn--ghost" onClick={load} disabled={isLoading}>
            Обновить
          </button>
        </div>
      </div>

      {error ? <p className="acc-flash acc-flash--error">{error}</p> : null}
      {message ? <p className="acc-flash">{message}</p> : null}

      <div className="st-tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`st-tab ${tab === item.id ? 'is-active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'dashboard' ? (
        <>
          <div className="st-kpis st-kpis--3">
            <div className="st-kpi">
              <div className="st-kpi-icon" style={{ background: '#f3f3f3', color: '#2f2f2f' }}>
                <Ico><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></Ico>
              </div>
              <strong>{dashboard.accounts || 0}</strong>
              <span>Аккаунты</span>
            </div>
            <div className="st-kpi">
              <div className="st-kpi-icon" style={{ background: '#f3f3f3', color: '#2f2f2f' }}>
                <Ico><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></Ico>
              </div>
              <strong>{dashboard.chats || 0}</strong>
              <span>Каналов</span>
            </div>
            <div className="st-kpi">
              <div className="st-kpi-icon" style={{ background: '#fff7ed', color: '#ea580c' }}>
                <Ico><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></Ico>
              </div>
              <strong>{dashboard.jobs || 0}</strong>
              <span>Всего задач</span>
            </div>
          </div>

          <div className="st-split">
            <div className="st-card">
              <h2>Сравнение</h2>
              {moduleTotal === 0 ? (
                <EmptyState
                  icon={<Ico><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Ico>}
                  text="Данные отсутствуют"
                />
              ) : (
                <div className="st-donut-wrap">
                  <div className="st-donut" style={{ background: donutBackground(moduleParts) }} />
                  <div className="st-legend">
                    {moduleParts.filter((item) => item.value).map((item) => (
                      <div key={item.key}>
                        <i style={{ background: item.color }} />
                        {item.label}: {item.value}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="st-card">
              <h2>Активность</h2>
              {series.length === 0 ? (
                <EmptyState
                  icon={<Ico><path d="M3 17l6-6 4 4 8-8" /><path d="M14 7h7v7" /></Ico>}
                  text="Данные отсутствуют"
                />
              ) : (
                <div className="st-cols">
                  {series.map((item) => {
                    const values = Object.entries(item).filter(([key]) => key !== 'date');
                    return (
                      <div key={item.date} className="st-col">
                        <div className="st-col-stack">
                          {values.map(([key, value]) => (
                            <div
                              key={key}
                              className="st-col-fill"
                              style={{
                                height: `${Math.max(4, Math.round((Number(value) / (seriesMax || 1)) * 120))}px`,
                                background: MODULE_COLORS[key] || '#2f2f2f',
                              }}
                              title={`${MODULE_LABELS[key] || key}: ${value}`}
                            />
                          ))}
                        </div>
                        <span>{formatDay(item.date)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="st-kpis st-kpis--4">
            <div className="st-kpi st-kpi--center">
              <strong>{dashboard.messages || 0}</strong>
              <span>Сообщений</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{dashboard.comments || 0}</strong>
              <span>Комментариев</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{dashboard.intercept || 0}</strong>
              <span>Перехватов</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{dashboard.success_pct || 0}%</strong>
              <span>Средний успех</span>
            </div>
          </div>
        </>
      ) : null}

      {tab === 'accounts' ? (
        <>
          <div className="st-kpis st-kpis--8">
            {[
              { label: 'Всего аккаунтов', value: accounts.total, color: '#f3f3f3', ink: '#2f2f2f' },
              { label: 'Валидный', value: accounts.active, color: '#ecfdf3', ink: '#16a34a' },
              { label: 'Заморожен', value: accounts.frozen, color: '#f1f5f9', ink: '#475569' },
              { label: 'Не авторизован', value: accounts.empty, color: '#f1f5f9', ink: '#64748b' },
              { label: 'Спамблок', value: accounts.spamblocked, color: '#fff7ed', ink: '#ea580c' },
              { label: 'Забанен', value: accounts.banned, color: '#fef2f2', ink: '#dc2626' },
              { label: 'Разавторизован', value: accounts.revoked, color: '#fef2f2', ink: '#b91c1c' },
              { label: 'С прокси', value: accounts.with_proxy, color: '#f3f3f3', ink: '#2f2f2f' },
            ].map((item) => (
              <div key={item.label} className="st-kpi st-kpi--center">
                <div className="st-kpi-icon" style={{ background: item.color, color: item.ink }}>
                  <Ico><circle cx="12" cy="12" r="9" /></Ico>
                </div>
                <strong>{item.value || 0}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div className="st-kpis st-kpis--4">
            <div className="st-kpi st-kpi--center">
              <strong>{accounts.channel_banned || 0}</strong>
              <span>Бан в каналах</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{accounts.in_work || 0}</strong>
              <span>В работе</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{accounts.quarantine || 0}</strong>
              <span>На карантине</span>
            </div>
            <div className="st-kpi st-kpi--center">
              <strong>{accounts.invalid || 0}</strong>
              <span>Невалидные</span>
            </div>
          </div>

          <div className="st-card">
            <h2>Живучесть аккаунтов</h2>
            <div className="st-kpis st-kpis--4">
              <div className="st-kpi st-kpi--center">
                <strong>{accounts.avg_age_days || 0} дн.</strong>
                <span>Средний возраст</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{accounts.median_age_days || 0} дн.</strong>
                <span>Медиана возраста</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{accounts.valid_age_days || 0} дн.</strong>
                <span>Возраст валидных</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{accounts.lifespan_days || 0} дн.</strong>
                <span>Прожили до смерти</span>
              </div>
            </div>
          </div>

          <div className="st-card">
            <h2>Динамика инцидентов</h2>
            {incidents.length === 0 ? (
              <EmptyState
                icon={<Ico><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></Ico>}
                text="За выбранный период инцидентов не было"
              />
            ) : (
              <div className="st-cols">
                {incidents.map((item) => (
                  <div key={item.date} className="st-col">
                    <div className="st-col-stack">
                      {['banned', 'frozen', 'spamblock'].map((key) => (
                        Number(item[key] || 0) ? (
                          <div
                            key={key}
                            className="st-col-fill"
                            style={{
                              height: `${Math.max(4, Math.round((Number(item[key]) / (incidentMax || 1)) * 120))}px`,
                              background: DIST_COLORS[key],
                            }}
                          />
                        ) : null
                      ))}
                    </div>
                    <span>{formatDay(item.date)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="st-card">
            <h2>Смены статусов</h2>
            {statusChanges.length === 0 ? (
              <EmptyState
                icon={<Ico><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /></Ico>}
                text="За период статусы аккаунтов не менялись"
              />
            ) : (
              <div className="st-changes">
                {statusChanges.map((item, index) => (
                  <div key={`${item.account_id}-${index}`} className="st-change">
                    <strong>{item.account}</strong>
                    <span>{item.from} → {item.to} · {formatWhen(item.at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="st-card">
            <h2>Распределение по статусам</h2>
            {distTotal === 0 ? (
              <EmptyState
                icon={<Ico><path d="M4 19V5M10 19V9M16 19V13M22 19H2" /></Ico>}
                text="Данные отсутствуют"
              />
            ) : (
              <div className="st-bars">
                {distParts.filter((item) => item.value).map((item) => (
                  <div key={item.key} className="st-bar-row">
                    <span>{item.label}</span>
                    <div className="st-bar-track">
                      <div
                        className="st-bar-fill"
                        style={{ width: `${Math.round((item.value / distTotal) * 100)}%`, background: item.color }}
                      />
                    </div>
                    <span>{item.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}

      {tab === 'history' ? (
        <>
          <div className="st-subtabs">
            {HISTORY_TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`st-subtab ${historyType === item.id ? 'is-active' : ''}`}
                onClick={() => setHistoryType(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="st-card">
            <h2>{HISTORY_TABS.find((item) => item.id === historyType)?.label}</h2>
            <div className="st-kpis st-kpis--5">
              <div className="st-kpi st-kpi--center">
                <strong>{summary.attempts || 0}</strong>
                <span>Всего попыток</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{summary.success || 0}</strong>
                <span>Успешных</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{summary.failed || 0}</strong>
                <span>Неуспешных</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{summary.success_pct || 0}%</strong>
                <span>Процент успешных</span>
              </div>
              <div className="st-kpi st-kpi--center">
                <strong>{summary.deleted || 0}</strong>
                <span>Удалено после отправки</span>
              </div>
            </div>
          </div>

          <div className="st-card">
            <h2>Генератор списков</h2>
            <p className="ubt-empty" style={{ marginBottom: 12 }}>
              Белый список — каналы, где действия проходят порог. Чёрный — где чаще не проходят.
            </p>
            <div className="st-gen">
              <label className="st-gen-slider">
                Порог {thresholdInput}%
                <input type="range" min="0" max="100" value={thresholdInput} onChange={(event) => setThresholdInput(Number(event.target.value))} />
              </label>
              <div className="st-stepper">
                Минимум попыток
                <Stepper value={minAttempts} min={1} max={100} onChange={setMinAttempts} />
              </div>
            </div>
            <div className="st-lists">
              <div className="st-list-box">
                <div className="st-list-head">
                  <span>Белый список · {history.whitelist?.length || 0}</span>
                  <button type="button" onClick={() => copyLines(history.whitelist).then((ok) => setMessage(ok ? 'Белый список скопирован' : 'Список пуст'))}>
                    Скопировать
                  </button>
                </div>
                {(history.whitelist || []).slice(0, 8).map((item) => (
                  <div key={item.id} className="st-black-item">
                    <span>{item.title}</span>
                    <span>{item.success_pct}%</span>
                  </div>
                ))}
              </div>
              <div className="st-list-box">
                <div className="st-list-head">
                  <span>Чёрный список · {history.generated_blacklist?.length || 0}</span>
                  <button type="button" onClick={() => copyLines(history.generated_blacklist).then((ok) => setMessage(ok ? 'Чёрный список скопирован' : 'Список пуст'))}>
                    Скопировать
                  </button>
                </div>
                {(history.generated_blacklist || []).slice(0, 8).map((item) => (
                  <div key={item.id} className="st-black-item">
                    <span>{item.title}</span>
                    <span>{item.success_pct}%</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="st-filters">
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Поиск комментария, канала..."
              />
              <CustomSelect
                value={status}
                options={[
                  { value: '', label: 'Статус' },
                  { value: 'success', label: 'Успех' },
                  { value: 'error', label: 'Ошибка' },
                ]}
                onChange={(event) => setStatus(event.target.value)}
              />
              <CustomSelect
                value={visibility}
                options={[
                  { value: '', label: 'Видимость' },
                  { value: 'open', label: 'Комментарии открыты' },
                  { value: 'closed', label: 'Комментарии закрыты' },
                ]}
                onChange={(event) => setVisibility(event.target.value)}
              />
              <button
                type="button"
                className="acc-btn acc-btn--ghost"
                onClick={() => { setSearchInput(''); setSearch(''); setStatus(''); setVisibility(''); }}
              >
                Очистить фильтры
              </button>
            </div>

            <div className="st-table-wrap">
              <table className="st-table">
                <thead>
                  <tr>
                    <th>Аккаунт</th>
                    <th>Канал</th>
                    <th>Комментарий</th>
                    <th>Промпт</th>
                    <th>Статус</th>
                    <th>Видимость</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.length === 0 ? (
                    <tr>
                      <td colSpan={7}>
                        <EmptyState
                          icon={<Ico><path d="M21 8V7a2 2 0 0 0-2-2h-4l-2-2H9L7 5H3a2 2 0 0 0-2 2v1" /><path d="M3 8h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></Ico>}
                          text={`${HISTORY_TABS.find((item) => item.id === historyType)?.label} не найдена`}
                        />
                      </td>
                    </tr>
                  ) : historyItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.account}</td>
                      <td>
                        {item.chat_id ? (
                          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(id)}>{item.channel}</Link>
                        ) : item.channel}
                      </td>
                      <td className="muted">{item.text || '—'}</td>
                      <td className="muted">{item.prompt || '—'}</td>
                      <td>
                        <span className={`st-status st-status--${item.status}`}>{item.status === 'success' ? 'Успех' : 'Ошибка'}</span>
                      </td>
                      <td>{item.visibility === 'open' ? 'Открыта' : item.visibility === 'closed' ? 'Закрыта' : '—'}</td>
                      <td>{formatWhen(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="st-pager">
              <button type="button" disabled={offset <= 0} onClick={() => setOffset(0)}>&laquo;</button>
              <button type="button" disabled={offset <= 0} onClick={() => setOffset(Math.max(0, offset - limit))}>&lsaquo;</button>
              <span style={{ alignSelf: 'center', fontSize: '0.8rem', color: '#6b7280' }}>{page} / {pages}</span>
              <button type="button" disabled={page >= pages} onClick={() => setOffset(offset + limit)}>&rsaquo;</button>
              <button type="button" disabled={page >= pages} onClick={() => setOffset((pages - 1) * limit)}>&raquo;</button>
            </div>
          </div>

          <div className="st-card">
            <h2>Чёрный список каналов</h2>
            <p className="ubt-empty">Каналы, добавленные сюда, пропускаются при работе модулей. Записи появляются автоматически при ошибках доступа.</p>
            <form className="st-black-add" onSubmit={addBlack}>
              <input
                value={blackQuery}
                onChange={(event) => setBlackQuery(event.target.value)}
                placeholder="Название или ссылка канала из списка чатов"
              />
              <button type="submit" disabled={busy}>+ Добавить в ЧС</button>
            </form>
            {(history.blacklist || []).length === 0 ? (
              <EmptyState
                icon={<Ico><path d="M20 6 9 17l-5-5" /></Ico>}
                text="Чёрный список пуст. Каналы и группы с ошибками доступа попадают сюда сами."
              />
            ) : (history.blacklist || []).map((item) => (
              <div key={item.id} className="st-black-item">
                <div>
                  <strong>{item.title}</strong>
                  <div className="ubt-empty">{item.reason || item.username || 'Добавлен вручную'}</div>
                </div>
                <span>{formatWhen(item.black_boxed_at)}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
};

export default CustomAutomationStatsPage;
