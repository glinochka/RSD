import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectDashboard.css';
import '../../../styles/projectSettingsPage.css';

const DMP_IMPORT_TYPES = [
  { value: 'website', label: 'Посетители сайта' },
  { value: 'competitors', label: 'Клиенты конкурентов' },
  { value: 'phones', label: 'По номерам телефонов' },
  { value: 'other', label: 'Другое' },
];

const IMPORT_STATUS_CLASS = {
  pending: 'crm-status--pending',
  processing: 'crm-status--pending',
  completed: 'crm-status--confirmed',
  failed: 'crm-status--cancelled',
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

  const loadImports = useCallback(async () => {
    try {
      const data = await customService.getDmpImports(id, { limit: 50, offset: 0 });
      setImports(data.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load DMP imports');
    }
  }, [id]);

  const loadLeads = useCallback(async () => {
    try {
      const data = await customService.getLeads(id, { source: 'dmp_one', limit: 50, offset: 0 });
      setLeads(data.items || []);
    } catch (err) {
      setError(err.message || 'Failed to load DMP leads');
    }
  }, [id]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    await Promise.all([loadImports(), loadLeads()]);
    setIsLoading(false);
  }, [loadImports, loadLeads]);

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
      await loadImports();
    } catch (err) {
      setError(err.message || 'Failed to create DMP order');
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
      setError(err.message || 'Poll failed');
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
  const cpl = totals.purchased ? (totals.cost / totals.purchased).toFixed(2) : '—';

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">DMP.one</h1>
          <p className="crm-subtitle">Заказ контактов.</p>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="dashboard-stats-grid">
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{totals.requested}</span>
            <span className="dashboard-stat-label">Заказано</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{totals.received}</span>
            <span className="dashboard-stat-label">Получено</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{totals.purchased}</span>
            <span className="dashboard-stat-label">Куплено</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{totals.cost.toFixed(2)} ₽</span>
            <span className="dashboard-stat-label">Стоимость</span>
          </div>
        </div>
        <div className="dashboard-stat-card">
          <div className="dashboard-stat-content">
            <span className="dashboard-stat-value">{cpl} ₽</span>
            <span className="dashboard-stat-label">CPL</span>
          </div>
        </div>
      </div>

      <form onSubmit={handleCreate} className="settings-section">
        <h3 className="settings-section-title">Новый заказ</h3>
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

      <div className="settings-section">
        <h3 className="settings-section-title">История импортов</h3>
        {isLoading ? (
          <p className="form-hint">Загрузка...</p>
        ) : imports.length === 0 ? (
          <div className="crm-empty-list">
            <p>Импортов пока нет</p>
          </div>
        ) : (
          <div className="crm-list">
            {imports.map((item) => (
              <div key={item.id} className="crm-item">
                <div className="crm-item-header">
                  <h5 className="crm-item-title">#{item.id} · {item.import_type}</h5>
                  <span className={`crm-status ${IMPORT_STATUS_CLASS[item.status] || ''}`}>{item.status}</span>
                </div>
                <p className="crm-item-subtitle">{item.source_url || '-'}</p>
                <p className="crm-item-subtitle">
                  заказано {item.requested_count || 0} · получено {item.received_count || 0} · куплено {item.purchased_count || 0}
                  {item.cost_rub ? ` · ${item.cost_rub.toFixed(2)} ₽` : ''}
                  {item.cpl_rub ? ` · CPL ${item.cpl_rub.toFixed(2)} ₽` : ''}
                </p>
                <span className="crm-date">{item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Лиды из DMP.one ({leads.length})</h3>
        {leads.length === 0 ? (
          <div className="crm-empty-list">
            <p>Лиды пока не получены</p>
          </div>
        ) : (
          <div className="crm-list">
            {leads.map((lead) => (
              <div key={lead.id} className="crm-item">
                <div className="crm-item-header">
                  <h5 className="crm-item-title">{lead.full_name || lead.contact_value}</h5>
                  <span className="crm-status">{lead.status}</span>
                </div>
                <p className="crm-item-subtitle">
                  {lead.contact_value}
                  {lead.company ? ` · ${lead.company}` : ''}
                  {lead.assigned_account_id ? ` · аккаунт #${lead.assigned_account_id}` : ''}
                </p>
                <span className="crm-date">{lead.created_at ? new Date(lead.created_at).toLocaleString() : ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationDmpPage;
