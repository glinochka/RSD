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

const STATUS_FILTERS = [
  { value: '', label: 'Все статусы' },
  ...LEAD_STATUSES,
];

const STATUS_COLORS = {
  new: 'bg-blue-50 text-blue-700',
  warming: 'bg-yellow-50 text-yellow-700',
  qualified: 'bg-green-50 text-green-700',
  transferred: 'bg-purple-50 text-purple-700',
  processing: 'bg-orange-50 text-orange-700',
  converted: 'bg-emerald-50 text-emerald-700',
  lost: 'bg-gray-100 text-gray-600',
  spam: 'bg-red-50 text-red-700',
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

  const openChat = (leadId) => {
    navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(id, leadId));
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Лиды</h1>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-3 mb-4">
          <label className="text-sm font-medium text-gray-700">Статус:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="text-sm text-gray-500 mb-2">Всего: {total}</div>

        {isLoading ? (
          <div className="text-gray-500">Загрузка...</div>
        ) : leads.length === 0 ? (
          <div className="text-gray-500 text-center py-6">Лиды пока не появились.</div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">ID</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Контакт</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Имя</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Компания</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Аккаунт</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Создан</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Действия</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono">{lead.id}</td>
                  <td className="px-4 py-3 text-sm">{lead.contact_value}</td>
                  <td className="px-4 py-3 text-sm">{lead.full_name || '-'}</td>
                  <td className="px-4 py-3 text-sm">{lead.company || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex px-2 py-1 rounded text-xs ${STATUS_COLORS[lead.status] || 'bg-gray-100 text-gray-700'}`}>
                        {LEAD_STATUSES.find((s) => s.value === lead.status)?.label || lead.status}
                      </span>
                      <select
                        value={lead.status}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                        disabled={updating[lead.id]}
                        className="border border-gray-300 rounded px-2 py-1 text-xs"
                      >
                        {LEAD_STATUSES.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm font-mono">{lead.assigned_account_id || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(lead.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => openChat(lead.id)}
                        className="text-blue-600 hover:underline"
                      >
                        Переписка
                      </button>
                      {lead.status !== 'transferred' && (
                        <button
                          onClick={() => handleTransfer(lead.id)}
                          className="text-purple-600 hover:underline"
                        >
                          Передать
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationLeadsPage;
