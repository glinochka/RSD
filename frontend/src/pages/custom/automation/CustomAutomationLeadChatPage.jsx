import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';

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

  const goBack = () => {
    navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(id));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button onClick={goBack} className="text-sm text-gray-600 hover:text-gray-900">
            ← Назад к лидам
          </button>
          <h1 className="text-2xl font-semibold">Переписка с лидом #{leadId}</h1>
        </div>
        {lead && (
          <div className="flex items-center gap-3">
            <select
              value={lead.status}
              onChange={handleStatusChange}
              disabled={updatingStatus}
              className="border border-gray-300 rounded px-3 py-2 text-sm"
            >
              {LEAD_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            {lead.status !== 'transferred' && (
              <button
                onClick={handleTransfer}
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 text-sm"
              >
                Передать
              </button>
            )}
          </div>
        )}
      </div>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      {lead && (
        <div className="bg-white rounded-lg shadow p-4 text-sm space-y-1">
          <div><strong>Контакт:</strong> {lead.contact_value}</div>
          <div><strong>Имя:</strong> {lead.full_name || '-'}</div>
          <div><strong>Компания:</strong> {lead.company || '-'}</div>
          <div><strong>Аккаунт пула:</strong> {lead.assigned_account_id || '-'}</div>
          <div><strong>Источник:</strong> {lead.source}</div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-4">
        {isLoading ? (
          <div className="text-gray-500">Загрузка...</div>
        ) : messages.length === 0 ? (
          <div className="text-gray-500 text-center py-6">Сообщений пока нет.</div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.direction === 'outgoing'
                      ? 'bg-blue-600 text-white rounded-br-none'
                      : 'bg-gray-100 text-gray-800 rounded-bl-none'
                  }`}
                >
                  <div className="text-xs opacity-75 mb-1">
                    {msg.direction === 'outgoing' ? 'От аккаунта пула' : 'Входящее'}
                    {msg.social_account_id ? ` #${msg.social_account_id}` : ''}
                  </div>
                  <div className="text-sm whitespace-pre-wrap">{msg.text}</div>
                  <div className={`text-xs mt-2 ${msg.direction === 'outgoing' ? 'text-blue-100' : 'text-gray-500'}`}>
                    {new Date(msg.sent_at).toLocaleString()}
                  </div>
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
