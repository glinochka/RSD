import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const LEAD_STATUSES = [
  { value: 'new', label: 'Новый' },
  { value: 'warming', label: 'Согрев' },
  { value: 'qualified', label: 'Квалифицирован' },
  { value: 'transferred', label: 'Передан' },
  { value: 'processing', label: 'В обработке' },
  { value: 'converted', label: 'Конвертирован' },
  { value: 'lost', label: 'Потерян' },
  { value: 'spam', label: 'Спам' },
];

const STATUS_FILTERS = [
  { value: '', label: 'Все статусы' },
  ...LEAD_STATUSES,
];

const STATUS_CLASS = {
  new: '',
  warming: 'crm-status--pending',
  qualified: 'crm-status--confirmed',
  transferred: 'crm-status--completed',
  processing: 'crm-status--pending',
  converted: 'crm-status--confirmed',
  lost: 'crm-status--completed',
  spam: 'crm-status--cancelled',
};

const CustomAutomationLeadsPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [filter, setFilter] = useState('');
  const [updating, setUpdating] = useState({});

  const loadLeads = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getLeads(id, { status: filter || undefined, limit: 50, offset: 0 });
      setLeads(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load leads');
    } finally {
      setIsLoading(false);
    }
  }, [id, filter]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const handleStatusChange = async (leadId, newStatus) => {
    setUpdating((prev) => ({ ...prev, [leadId]: true }));
    setMessage(null);
    try {
      await customService.updateLeadStatus(id, leadId, newStatus);
      setMessage('Статус обновлён');
      await loadLeads();
    } catch (err) {
      setError(err.message || 'Failed to update status');
    } finally {
      setUpdating((prev) => ({ ...prev, [leadId]: false }));
    }
  };

  const handleTransfer = async (leadId) => {
    if (!window.confirm('Передать лид в обработку?')) {
      return;
    }
    setMessage(null);
    try {
      await customService.transferLead(id, leadId);
      setMessage('Лид передан');
      await loadLeads();
    } catch (err) {
      setError(err.message || 'Failed to transfer lead');
    }
  };

  const handleDelete = async (leadId) => {
    if (!window.confirm('Удалить лида безвозвратно? Можно снова запустить DMP/перехват для демо.')) {
      return;
    }
    setMessage(null);
    try {
      await customService.deleteLead(id, leadId);
      setMessage('Лид удалён');
      await loadLeads();
    } catch (err) {
      setError(err.message || 'Не удалось удалить лида');
    }
  };

  const openChat = (leadId) => {
    navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, leadId));
  };

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Лиды</h1>
          <p className="crm-subtitle">Перехват, согрев и передача менеджеру.</p>
        </div>
        <div className="crm-stats">
          <div className="crm-stat">
            <span className="crm-stat-value">{total}</span>
            <span className="crm-stat-label">Всего</span>
          </div>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="settings-section">
        <div className="form-group">
          <label htmlFor="lead-filter">Статус</label>
          <CustomSelect
            id="lead-filter"
            value={filter}
            options={STATUS_FILTERS}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : leads.length === 0 ? (
        <div className="crm-empty-list">
          <p>Лиды пока не появились</p>
          <span>Они появятся после перехвата в чатах или импорта DMP.</span>
        </div>
      ) : (
        <div className="crm-list">
          {leads.map((lead) => (
            <div key={lead.id} className="crm-item">
              <div className="crm-item-header">
                <h5 className="crm-item-title">{lead.full_name || lead.contact_value || `Лид #${lead.id}`}</h5>
                <span className={`crm-status ${STATUS_CLASS[lead.status] || ''}`}>
                  {LEAD_STATUSES.find((s) => s.value === lead.status)?.label || lead.status}
                </span>
              </div>
              <p className="crm-item-subtitle">
                {lead.contact_value}
                {lead.company ? ` · ${lead.company}` : ''}
                {lead.assigned_account_id ? ` · аккаунт #${lead.assigned_account_id}` : ''}
              </p>
              <span className="crm-date">{lead.created_at ? new Date(lead.created_at).toLocaleString() : ''}</span>
              <div className="form-group">
                <label htmlFor={`lead-status-${lead.id}`}>Статус</label>
                <CustomSelect
                  id={`lead-status-${lead.id}`}
                  value={lead.status}
                  options={LEAD_STATUSES}
                  onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                  disabled={updating[lead.id]}
                />
              </div>
              <div className="crm-item-actions">
                <button type="button" onClick={() => openChat(lead.id)} className="btn btn-black">
                  Переписка
                </button>
                {lead.status !== 'transferred' ? (
                  <button type="button" onClick={() => handleTransfer(lead.id)} className="btn btn-outline">
                    Передать
                  </button>
                ) : null}
                <button type="button" onClick={() => handleDelete(lead.id)} className="btn btn-outline">
                  Удалить
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CustomAutomationLeadsPage;
