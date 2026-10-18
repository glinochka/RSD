import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customSasha.css';

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
  const [sashaCalls, setSashaCalls] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isPushingSasha, setIsPushingSasha] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const loadLead = useCallback(async () => {
    try {
      const data = await customService.getLead(id, leadId);
      setLead(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить лид');
    }
  }, [id, leadId]);

  const loadMessages = useCallback(async () => {
    try {
      const data = await customService.getLeadMessages(id, leadId, { limit: 100, offset: 0 });
      setMessages(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить сообщения');
    }
  }, [id, leadId]);

  const loadSasha = useCallback(async () => {
    try {
      const data = await customService.getLeadSashaCalls(id, leadId);
      setSashaCalls(data.items || []);
    } catch {
      setSashaCalls([]);
    }
  }, [id, leadId]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([loadLead(), loadMessages(), loadSasha()]);
    setIsLoading(false);
  }, [loadLead, loadMessages, loadSasha]);

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
      setError(err.message || 'Не удалось обновить статус');
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
      setError(err.message || 'Не удалось передать лид');
    }
  };

  const handlePushSasha = async () => {
    setIsPushingSasha(true);
    setMessage(null);
    try {
      await customService.pushLeadToSasha(id, leadId);
      setMessage('Номер отправлен в Sasha AI');
      await loadLead();
    } catch (err) {
      setError(err.message || 'Не удалось отправить в Sasha AI');
    } finally {
      setIsPushingSasha(false);
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
          {lead && lead.contact_type === 'phone' ? (
            <button type="button" onClick={handlePushSasha} className="btn btn-outline" disabled={isPushingSasha}>
              {isPushingSasha ? '...' : 'Отправить в Sasha AI'}
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
          {lead.sasha_status ? <p className="form-hint">Sasha AI: {lead.sasha_status}{lead.sasha_lead_quality != null ? ` · прогрев ${lead.sasha_lead_quality}/10` : ''}</p> : null}
          {lead.sasha_summary ? <p className="form-hint">О разговоре: {lead.sasha_summary}</p> : null}
          <div className="form-group">
            <label htmlFor="lead-chat-status">Статус</label>
            <CustomSelect
              id="lead-chat-status"
              value={lead.status}
              options={LEAD_STATUSES}
              onChange={handleStatusChange}
              disabled={updatingStatus}
            />
          </div>
        </div>
      ) : null}

      {sashaCalls.length > 0 ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Звонки Sasha AI</h3>
          {sashaCalls.map((item) => (
            <div key={item.id} className="ubt-panel" style={{ marginBottom: 12 }}>
              <p className="form-hint">
                {item.outcome}
                {item.lead_quality != null ? ` · прогрев ${item.lead_quality}/10 (${item.warmth})` : ''}
                {item.duration_ms ? ` · ${Math.round(item.duration_ms / 1000)} с` : ''}
              </p>
              {item.client_name ? <p className="form-hint">ФИО: {item.client_name}</p> : null}
              {item.client_facts ? <p className="form-hint">О клиенте: {item.client_facts}</p> : null}
              {item.agreements ? <p className="form-hint">Договорённость: {item.agreements}</p> : null}
              {item.record_url ? (
                <p className="form-hint">
                  <a href={item.record_url} target="_blank" rel="noreferrer">Запись</a>
                </p>
              ) : null}
              <div className="sasha-transcript">{item.transcript_text || 'Транскрипт пуст'}</div>
            </div>
          ))}
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
