import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';

const DMP_IMPORT_TYPES = [
  { value: 'website', label: 'Посетители сайта' },
  { value: 'competitors', label: 'Клиенты конкурентов' },
  { value: 'phones', label: 'По номерам телефонов' },
  { value: 'other', label: 'Другое' },
];

const STATUS_COLORS = {
  pending: 'bg-yellow-50 text-yellow-700',
  processing: 'bg-blue-50 text-blue-700',
  completed: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-700',
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
  const cpl = totals.purchased ? (totals.cost / totals.purchased).toFixed(2) : '-';

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">DMP.one</h1>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <div className="text-2xl font-semibold">{totals.requested}</div>
          <div className="text-xs text-gray-500">Заказано</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <div className="text-2xl font-semibold">{totals.received}</div>
          <div className="text-xs text-gray-500">Получено</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <div className="text-2xl font-semibold">{totals.purchased}</div>
          <div className="text-xs text-gray-500">Куплено</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <div className="text-2xl font-semibold">{totals.cost.toFixed(2)} ₽</div>
          <div className="text-xs text-gray-500">Стоимость</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <div className="text-2xl font-semibold">{cpl} ₽</div>
          <div className="text-xs text-gray-500">CPL</div>
        </div>
      </div>

      <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Тип импорта</label>
          <select
            value={form.importType}
            onChange={(e) => setForm((f) => ({ ...f, importType: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2 w-full text-sm"
          >
            {DMP_IMPORT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Источник (URL, сайт, номера)</label>
          <input
            type="text"
            placeholder="https://example.com"
            value={form.sourceUrl}
            onChange={(e) => setForm((f) => ({ ...f, sourceUrl: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2 w-full text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Количество</label>
          <input
            type="number"
            min={1}
            value={form.requestedCount}
            onChange={(e) => setForm((f) => ({ ...f, requestedCount: e.target.value }))}
            className="border border-gray-300 rounded px-3 py-2 w-full text-sm"
          />
        </div>
        <div className="md:col-span-4 flex gap-3">
          <button
            type="submit"
            disabled={isCreating}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {isCreating ? 'Создание...' : 'Создать заказ'}
          </button>
          <button
            type="button"
            onClick={handlePoll}
            disabled={isPolling}
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50 text-sm"
          >
            {isPolling ? '...' : 'Опросить результаты'}
          </button>
        </div>
      </form>

      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="font-medium mb-4">История импортов</h2>
        {isLoading ? (
          <div className="text-gray-500">Загрузка...</div>
        ) : imports.length === 0 ? (
          <div className="text-gray-500 text-center py-6">Импортов пока нет.</div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">ID</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Тип</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Источник</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Статус</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Заказано</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Получено</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Куплено</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Стоимость</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">CPL</th>
                <th className="px-4 py-3 text-sm font-medium text-gray-700">Создан</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((item) => (
                <tr key={item.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono">{item.id}</td>
                  <td className="px-4 py-3 text-sm">{item.import_type}</td>
                  <td className="px-4 py-3 text-sm truncate max-w-xs">{item.source_url || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex px-2 py-1 rounded text-xs ${STATUS_COLORS[item.status] || 'bg-gray-100 text-gray-700'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">{item.requested_count || 0}</td>
                  <td className="px-4 py-3 text-sm">{item.received_count || 0}</td>
                  <td className="px-4 py-3 text-sm">{item.purchased_count || 0}</td>
                  <td className="px-4 py-3 text-sm">{item.cost_rub ? `${item.cost_rub.toFixed(2)} ₽` : '-'}</td>
                  <td className="px-4 py-3 text-sm">{item.cpl_rub ? `${item.cpl_rub.toFixed(2)} ₽` : '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="font-medium mb-4">Лиды из DMP.one ({leads.length})</h2>
        {leads.length === 0 ? (
          <div className="text-gray-500 text-center py-6">Лиды пока не получены.</div>
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
                    <span className="inline-flex px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                      {lead.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm font-mono">{lead.assigned_account_id || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(lead.created_at).toLocaleString()}
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

export default CustomAutomationDmpPage;
