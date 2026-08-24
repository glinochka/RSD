import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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

const CustomAutomationLeadChatPage = () => {
  const { id, leadId } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const loadLead = useCallback(async () => {
    try {
      const data = await customService.getLead(id, leadId);
      setLead(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load lead');
    }
  }, [id, leadId]);

  const loadMessages = useCallback(async () => {
    try {
      const data = await customService.getLeadMessages(id, leadId, { limit: 100, offset: 0 });
      setMessages(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load messages');
    }
  }, [id, leadId]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([loadLead(), loadMessages()]);
    setIsLoading(false);
  }, [loadLead, loadMessages]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleStatusChange = async (e) => {
    setUpdatingStatus(true);
    setMessage(null);
    try {
      await customService.updateLeadStatus(id, leadId, e.target.value);
      setMessage('Статус обновлён');
      await loadLead();
    } catch (err) {
      setError(err.message || 'Failed to update status');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleTransfer = async () => {
    if (!window.confirm('Передать лид в обработку?')) {
      return;
    }
    setMessage(null);
    try {
      await customService.transferLead(id, leadId);
      setMessage('Лид передан');
      await loadLead();
    } catch (err) {
      setError(err.message || 'Failed to transfer lead');
    }
  };

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Переписка с лидом #{leadId}</h1>
          <p className="crm-subtitle">{lead?.contact_value || lead?.full_name || ''}</p>
        </div>
        <div className="settings-actions">
          <button type="button" className="btn btn-outline" onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id))}>
            К лидам
          </button>
          {lead && lead.status !== 'transferred' ? (
            <button type="button" onClick={handleTransfer} className="btn btn-black">
              Передать
            </button>
          ) : null}
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      {lead ? (
        <div className="settings-section">
          <p className="form-hint">Контакт: {lead.contact_value}</p>
          <p className="form-hint">Имя: {lead.full_name || '-'}</p>
          <p className="form-hint">Компания: {lead.company || '-'}</p>
          <p className="form-hint">Аккаунт пула: {lead.assigned_account_id || '-'}</p>
          <p className="form-hint">Источник: {lead.source}</p>
          <div className="form-group">
            <label htmlFor="lead-chat-status">Статус</label>
            <select id="lead-chat-status" value={lead.status} onChange={handleStatusChange} disabled={updatingStatus}>
              {LEAD_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>
      ) : null}

      <div className="settings-section">
        {isLoading ? (
          <p className="form-hint">Загрузка...</p>
        ) : messages.length === 0 ? (
          <div className="crm-empty-list">
            <p>Сообщений пока нет</p>
          </div>
        ) : (
          <div className="crm-chat">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`crm-chat-row ${msg.direction === 'outgoing' ? 'crm-chat-row--out' : ''}`}
              >
                <div className="crm-chat-bubble">
                  <div className="crm-chat-meta">
                    {msg.direction === 'outgoing' ? 'От аккаунта пула' : 'Входящее'}
                    {msg.social_account_id ? ` #${msg.social_account_id}` : ''}
                    {msg.sent_at ? ` · ${new Date(msg.sent_at).toLocaleString()}` : ''}
                  </div>
                  <div>{msg.text}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationLeadChatPage;
