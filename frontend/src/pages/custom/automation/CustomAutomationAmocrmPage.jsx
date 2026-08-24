import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';

const CustomAutomationAmocrmPage = () => {
  const { id } = useParams();
  const [settings, setSettings] = useState(null);
  const [connection, setConnection] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [form, setForm] = useState({
    subdomain: '',
    access_token: '',
    refresh_token: '',
    pipeline_id: '',
    responsible_user_id: '',
    lead_status_id: '',
  });

  const loadSettings = useCallback(async () => {
    try {
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
    } catch (err) {
      setError(err.message || 'Failed to load settings');
    }
  }, [id]);

  const loadConnection = useCallback(async () => {
    try {
      const data = await customService.getAmocrmConnection(id);
      setConnection(data);
      setForm({
        subdomain: data.subdomain || '',
        access_token: '',
        refresh_token: '',
        pipeline_id: data.pipeline_id || '',
        responsible_user_id: data.responsible_user_id || '',
        lead_status_id: data.lead_status_id || '',
      });
      setError(null);
    } catch (err) {
      if (err.message && err.message.includes('404')) {
        setConnection(null);
      } else {
        setError(err.message || 'Failed to load connection');
      }
    }
  }, [id]);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.all([loadSettings(), loadConnection()]);
    setIsLoading(false);
  }, [loadSettings, loadConnection]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        subdomain: form.subdomain,
        access_token: form.access_token,
        refresh_token: form.refresh_token,
        pipeline_id: form.pipeline_id,
        responsible_user_id: form.responsible_user_id,
        lead_status_id: form.lead_status_id,
      };
      await customService.saveAmocrmConnection(id, payload);
      setMessage('Подключение к AmoCRM сохранено');
      await loadAll();
    } catch (err) {
      setError(err.message || 'Failed to save connection');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisable = async () => {
    if (!window.confirm('Отключить AmoCRM?')) {
      return;
    }
    setMessage(null);
    try {
      await customService.deleteAmocrmConnection(id);
      setMessage('Подключение отключено');
      await loadAll();
    } catch (err) {
      setError(err.message || 'Failed to disable connection');
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    setMessage(null);
    try {
      await customService.runAmocrmSync(id);
      setMessage('Синхронизация статусов запущена в фоне');
    } catch (err) {
      setError(err.message || 'Sync failed');
    } finally {
      setIsSyncing(false);
    }
  };

  const enabled = settings?.is_amocrm_enabled;

  if (isLoading) {
    return <div className="text-gray-500">Загрузка...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">AmoCRM</h1>
        {enabled ? (
          <span className="inline-flex px-2 py-1 rounded text-xs bg-green-50 text-green-700">Включено</span>
        ) : (
          <span className="inline-flex px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">Отключено</span>
        )}
      </div>

      {message && <div className="text-green-600">{message}</div>}
      {error && <div className="text-red-600">{error}</div>}

      {!enabled && (
        <div className="bg-yellow-50 text-yellow-800 rounded-lg p-4 text-sm">
          AmoCRM отключено. Включите в разделе «Настройки» → «AmoCRM».
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Поддомен AmoCRM</label>
            <input
              type="text"
              name="subdomain"
              value={form.subdomain}
              onChange={handleChange}
              placeholder="company"
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
            <p className="text-xs text-gray-500 mt-1">Например, company в company.amocrm.ru</p>
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Access token</label>
            <input
              type="password"
              name="access_token"
              value={form.access_token}
              onChange={handleChange}
              placeholder={connection ? 'Оставьте пустым, чтобы не менять' : ''}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Refresh token (опционально)</label>
            <input
              type="password"
              name="refresh_token"
              value={form.refresh_token}
              onChange={handleChange}
              placeholder={connection ? 'Оставьте пустым, чтобы не менять' : ''}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID воронки</label>
            <input
              type="text"
              name="pipeline_id"
              value={form.pipeline_id}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID ответственного пользователя</label>
            <input
              type="text"
              name="responsible_user_id"
              value={form.responsible_user_id}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">ID статуса сделки</label>
            <input
              type="text"
              name="lead_status_id"
              value={form.lead_status_id}
              onChange={handleChange}
              className="w-full border border-gray-300 rounded px-3 py-2"
            />
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={isSaving || !enabled}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? 'Сохранение...' : 'Сохранить подключение'}
          </button>
          {connection && (
            <button
              type="button"
              onClick={handleDisable}
              className="border border-red-300 text-red-600 px-4 py-2 rounded hover:bg-red-50"
            >
              Отключить
            </button>
          )}
          <button
            type="button"
            onClick={handleSync}
            disabled={isSyncing || !enabled}
            className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
          >
            {isSyncing ? '...' : 'Синхронизировать статусы'}
          </button>
        </div>
      </form>

      {connection && (
        <div className="bg-white rounded-lg shadow p-4 text-sm space-y-1">
          <div><strong>Поддомен:</strong> {connection.subdomain}</div>
          <div><strong>Воронка:</strong> {connection.pipeline_id || '-'}</div>
          <div><strong>Ответственный:</strong> {connection.responsible_user_id || '-'}</div>
          <div><strong>Статус сделки:</strong> {connection.lead_status_id || '-'}</div>
          <div><strong>Последняя синхронизация:</strong> {connection.last_sync_at ? new Date(connection.last_sync_at).toLocaleString() : '—'}</div>
        </div>
      )}
    </div>
  );
};

export default CustomAutomationAmocrmPage;
