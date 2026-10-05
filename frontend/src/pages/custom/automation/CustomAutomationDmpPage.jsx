import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectDashboard.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customAccountManager.css';

const DMP_IMPORT_TYPES = [
  { value: 'website', label: 'Посетители сайта' },
  { value: 'competitors', label: 'Клиенты конкурентов' },
  { value: 'phones', label: 'По номерам телефонов' },
  { value: 'other', label: 'Другое' },
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

const CustomAutomationDmpPage = () => {
  const { id } = useParams();
  const [imports, setImports] = useState([]);
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [form, setForm] = useState({
    importType: 'website',
    sourceUrl: '',
    requestedCount: 100,
  });

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [importsData, leadsData] = await Promise.all([
        customService.getDmpImports(id, { limit: 50, offset: 0 }),
        customService.getLeads(id, { source: 'dmp_one', limit: 100, offset: 0 }),
      ]);
      setImports(importsData.items || []);
      setLeads(leadsData.items || []);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить DMP');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setIsCreating(true);
    setMessage(null);
    setError(null);
    try {
      await customService.createDmpOrder(id, {
        importType: form.importType,
        sourceUrl: form.sourceUrl,
        requestedCount: Number(form.requestedCount) || 100,
      });
      setMessage('Заказ в DMP.one создан');
      setForm({ importType: 'website', sourceUrl: '', requestedCount: 100 });
      await loadAll();
    } catch (err) {
      setError(err.message || 'Не удалось создать заказ');
    } finally {
      setIsCreating(false);
    }
  };

  const handlePoll = async () => {
    setIsPolling(true);
    setMessage(null);
    try {
      await customService.runDmpPoll(id);
      setMessage('Опрос DMP.one запущен в фоне');
    } catch (err) {
      setError(err.message || 'Опрос не удался');
    } finally {
      setIsPolling(false);
    }
  };

  const totals = imports.reduce(
    (acc, item) => {
      acc.requested += item.requested_count || 0;
      acc.received += item.received_count || 0;
      acc.purchased += item.purchased_count || 0;
      acc.cost += item.cost_rub || 0;
      return acc;
    },
    { requested: 0, received: 0, purchased: 0, cost: 0 },
  );

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Дашборд DMP</h1>
          <p>Номера, которые пришли из DMP.one, и заказы импорта.</p>
        </div>
        <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_CONNECTION(id)} className="acc-btn acc-btn--ghost">
          Подключение
        </Link>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="ubt-kpi-grid">
        <div className="ubt-kpi">
          <strong>{leads.length}</strong>
          <span>Номеров в списке</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.purchased}</strong>
          <span>Куплено</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.received}</strong>
          <span>Получено</span>
        </div>
        <div className="ubt-kpi">
          <strong>{totals.cost.toFixed(0)} ₽</strong>
          <span>Расход</span>
        </div>
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Список номеров</h2>
        </div>
        {isLoading ? (
          <p className="ubt-empty">Загрузка...</p>
        ) : leads.length === 0 ? (
          <p className="ubt-empty">Номеров пока нет — создайте заказ или дождитесь вебхука.</p>
        ) : (
          <table className="ubt-table">
            <thead>
              <tr>
                <th>Номер</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td>{lead.contact_value || lead.full_name || `Лид #${lead.id}`}</td>
                  <td>{formatDate(lead.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Новый заказ</h2>
        </div>
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label htmlFor="dmp-type">Тип импорта</label>
            <CustomSelect
              id="dmp-type"
              value={form.importType}
              options={DMP_IMPORT_TYPES}
              onChange={(e) => setForm((f) => ({ ...f, importType: e.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="dmp-source">Источник (URL, сайт, номера)</label>
            <input
              id="dmp-source"
              type="text"
              placeholder="https://example.com"
              value={form.sourceUrl}
              onChange={(e) => setForm((f) => ({ ...f, sourceUrl: e.target.value }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="dmp-count">Количество</label>
            <input
              id="dmp-count"
              type="number"
              min={1}
              value={form.requestedCount}
              onChange={(e) => setForm((f) => ({ ...f, requestedCount: e.target.value }))}
            />
          </div>
          <div className="settings-actions">
            <button type="submit" disabled={isCreating} className="btn btn-black">
              {isCreating ? 'Создание...' : 'Создать заказ'}
            </button>
            <button type="button" onClick={handlePoll} disabled={isPolling} className="btn btn-outline">
              {isPolling ? '...' : 'Опросить результаты'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CustomAutomationDmpPage;
