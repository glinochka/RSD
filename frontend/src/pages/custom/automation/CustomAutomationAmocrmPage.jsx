import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

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
    return (
      <div className="project-settings-page project-settings-page--loading">
        <div className="settings-loading">
          <div className="spinner" />
          <p>Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">AmoCRM</h1>
          <p className="settings-subtitle">Подключение воронки.</p>
        </div>
        <span className={`crm-status ${enabled ? 'crm-status--confirmed' : 'crm-status--completed'}`}>
          {enabled ? 'Включено' : 'Отключено'}
        </span>
      </div>

      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}

      {!enabled ? (
        <div className="settings-section">
          <p className="form-hint">AmoCRM отключено. Включите в разделе «Настройки».</p>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="settings-form">
        <div className="settings-section">
          <h3 className="settings-section-title">Подключение</h3>
          <div className="form-group">
            <label htmlFor="subdomain">Поддомен AmoCRM</label>
            <input
              id="subdomain"
              type="text"
              name="subdomain"
              value={form.subdomain}
              onChange={handleChange}
              placeholder="company"
            />
            <span className="form-hint">Например, company в company.amocrm.ru</span>
          </div>
          <div className="form-group">
            <label htmlFor="access_token">Access token</label>
            <input
              id="access_token"
              type="password"
              name="access_token"
              value={form.access_token}
              onChange={handleChange}
              placeholder={connection ? 'Оставьте пустым, чтобы не менять' : ''}
            />
          </div>
          <div className="form-group">
            <label htmlFor="refresh_token">Refresh token (опционально)</label>
            <input
              id="refresh_token"
              type="password"
              name="refresh_token"
              value={form.refresh_token}
              onChange={handleChange}
              placeholder={connection ? 'Оставьте пустым, чтобы не менять' : ''}
            />
          </div>
          <div className="form-group">
            <label htmlFor="pipeline_id">ID воронки</label>
            <input id="pipeline_id" type="text" name="pipeline_id" value={form.pipeline_id} onChange={handleChange} />
          </div>
          <div className="form-group">
            <label htmlFor="responsible_user_id">ID ответственного пользователя</label>
            <input
              id="responsible_user_id"
              type="text"
              name="responsible_user_id"
              value={form.responsible_user_id}
              onChange={handleChange}
            />
          </div>
          <div className="form-group">
            <label htmlFor="lead_status_id">ID статуса сделки</label>
            <input
              id="lead_status_id"
              type="text"
              name="lead_status_id"
              value={form.lead_status_id}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="settings-actions">
          <button type="submit" disabled={isSaving || !enabled} className="btn btn-black">
            {isSaving ? 'Сохранение...' : 'Сохранить подключение'}
          </button>
          {connection ? (
            <button type="button" onClick={handleDisable} className="btn-danger">
              Отключить
            </button>
          ) : null}
          <button type="button" onClick={handleSync} disabled={isSyncing || !enabled} className="btn btn-outline">
            {isSyncing ? '...' : 'Синхронизировать статусы'}
          </button>
        </div>
      </form>

      {connection ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Текущее подключение</h3>
          <p className="form-hint">Поддомен: {connection.subdomain}</p>
          <p className="form-hint">Воронка: {connection.pipeline_id || '-'}</p>
          <p className="form-hint">Ответственный: {connection.responsible_user_id || '-'}</p>
          <p className="form-hint">Статус сделки: {connection.lead_status_id || '-'}</p>
          <p className="form-hint">
            Последняя синхронизация: {connection.last_sync_at ? new Date(connection.last_sync_at).toLocaleString() : '—'}
          </p>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationAmocrmPage;
