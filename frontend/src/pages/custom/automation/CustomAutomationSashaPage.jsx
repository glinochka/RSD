import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSasha.css';

const OUTCOME_FILTERS = [
  { value: '', label: 'Все звонки' },
  { value: 'committed', label: 'Лиды' },
  { value: 'talked', label: 'Состоялся разговор' },
  { value: 'rejected', label: 'Отказ' },
  { value: 'no_answer', label: 'Недозвон' },
];

const formatDate = (value) => {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('ru-RU');
  } catch {
    return String(value);
  }
};

const formatDuration = (ms) => {
  if (!ms && ms !== 0) {
    return '—';
  }
  const total = Math.max(0, Math.round(Number(ms) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
};

const outcomeClass = (outcome) => {
  if (outcome === 'лид') {
    return 'sasha-chip sasha-chip--lead';
  }
  if (outcome === 'отказ') {
    return 'sasha-chip sasha-chip--reject';
  }
  if (outcome === 'недозвон') {
    return 'sasha-chip sasha-chip--miss';
  }
  return 'sasha-chip';
};

const qualityClass = (value) => {
  if (value >= 7) {
    return 'sasha-quality sasha-quality--hot';
  }
  if (value >= 4) {
    return 'sasha-quality sasha-quality--warm';
  }
  return 'sasha-quality';
};

const CustomAutomationSashaPage = () => {
  const { id } = useParams();
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState({});
  const [settings, setSettings] = useState(null);
  const [filter, setFilter] = useState('');
  const [openId, setOpenId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPushing, setIsPushing] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    try {
      const [callsData, settingsData] = await Promise.all([
        customService.getSashaCalls(id, { outcome: filter || undefined, limit: 80, offset: 0 }),
        customService.getAutomationSettings(id),
      ]);
      setCalls(callsData.items || []);
      setStats(callsData.stats || {});
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить прозвон Sasha AI');
    } finally {
      setIsLoading(false);
    }
  }, [id, filter]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handlePush = async () => {
    setIsPushing(true);
    setMessage(null);
    try {
      await customService.pushSashaPending(id);
      setMessage('Ожидающие номера отправлены в Sasha AI');
      await loadAll();
    } catch (err) {
      setError(err.message || 'Не удалось отправить номера');
    } finally {
      setIsPushing(false);
    }
  };

  const connected = Boolean(settings?.sasha_connected);

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Прозвон Sasha AI</h1>
          <p>Номера из DMP.one уходят на прозвон. Договорённость возвращается сюда и в тот же Telegram-бот, что лиды из чатов и DMP.</p>
        </div>
        <div className="settings-actions">
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id)} className="acc-btn acc-btn--ghost">
            Подключение
          </Link>
          <button type="button" className="acc-btn acc-btn--ghost" onClick={handlePush} disabled={isPushing || !connected}>
            {isPushing ? '...' : 'Отправить очередь'}
          </button>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <p className={`sasha-status${connected ? '' : ' is-off'}`}>
        {connected ? 'Sasha AI подключена' : 'Сначала вставьте webhook загрузки контактов на странице подключения'}
      </p>

      <div className="ubt-kpi-grid">
        <div className="ubt-kpi">
          <strong>{stats.queued ?? 0}</strong>
          <span>В очереди</span>
        </div>
        <div className="ubt-kpi">
          <strong>{stats.uploaded ?? 0}</strong>
          <span>Ушло в Сашу</span>
        </div>
        <div className="ubt-kpi">
          <strong>{stats.completed ?? 0}</strong>
          <span>Дозвоны</span>
        </div>
        <div className="ubt-kpi">
          <strong>{stats.committed_leads ?? 0}</strong>
          <span>Лиды</span>
        </div>
        <div className="ubt-kpi">
          <strong>{stats.avg_quality == null ? '—' : stats.avg_quality}</strong>
          <span>Средний прогрев</span>
        </div>
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Результаты звонков</h2>
          <div className="form-group" style={{ minWidth: 220, margin: 0 }}>
            <CustomSelect
              id="sasha-filter"
              value={filter}
              options={OUTCOME_FILTERS}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
        </div>
        {isLoading ? (
          <p className="ubt-empty">Загрузка...</p>
        ) : calls.length === 0 ? (
          <p className="ubt-empty">Звонков пока нет. Номер из DMP уходит в колл-лист сам, а договорённость вернётся в эту таблицу и в Telegram-бот.</p>
        ) : (
          <table className="ubt-table">
            <thead>
              <tr>
                <th>Контакт</th>
                <th>Исход</th>
                <th>Прогрев</th>
                <th>О чём разговор</th>
                <th>Длительность</th>
                <th>Когда</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((item) => (
                <React.Fragment key={item.id}>
                  <tr className={openId === item.id ? 'is-open' : ''}>
                    <td>
                      <strong>{item.client_name || item.phone || '—'}</strong>
                      {item.client_name && item.phone ? <div className="form-hint">{item.phone}</div> : null}
                    </td>
                    <td><span className={outcomeClass(item.outcome)}>{item.outcome}</span></td>
                    <td>
                      {item.lead_quality == null ? '—' : (
                        <span className={qualityClass(item.lead_quality)}>
                          <span className="sasha-quality-bar"><span style={{ width: `${item.lead_quality * 10}%` }} /></span>
                          {item.lead_quality}/10 · {item.warmth}
                        </span>
                      )}
                    </td>
                    <td>{item.client_facts || item.agreements || '—'}</td>
                    <td>{formatDuration(item.duration_ms)}</td>
                    <td>
                      {formatDate(item.ended_at || item.created_at)}
                      <div>
                        <button
                          type="button"
                          className="acc-btn acc-btn--ghost"
                          onClick={() => setOpenId((prev) => (prev === item.id ? null : item.id))}
                        >
                          {openId === item.id ? 'Скрыть диалог' : 'Диалог'}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {openId === item.id ? (
                    <tr className="sasha-expand">
                      <td colSpan={6}>
                        {item.agreements ? <p className="form-hint">Договорённость: {item.agreements}</p> : null}
                        {item.lead_destination ? <p className="form-hint">Следующий шаг: {item.lead_destination}</p> : null}
                        {item.record_url ? (
                          <p className="form-hint">
                            <a href={item.record_url} target="_blank" rel="noreferrer">Запись разговора</a>
                          </p>
                        ) : null}
                        {item.custom_lead_id ? (
                          <p className="form-hint">
                            <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, item.custom_lead_id)}>Карточка лида</Link>
                          </p>
                        ) : null}
                        <div className="sasha-transcript">{item.transcript_text || 'Транскрипт пока пуст'}</div>
                      </td>
                    </tr>
                  ) : null}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationSashaPage;
