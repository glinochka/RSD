import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

const CustomAutomationAmocrmPage = () => {
  const { id } = useParams();
  const [settings, setSettings] = useState(null);
  const [connection, setConnection] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    try {
      const [settingsData, connectionData] = await Promise.all([
        customService.getAutomationSettings(id),
        customService.getAmocrmConnection(id).catch(() => null),
      ]);
      setSettings(settingsData);
      setConnection(connectionData);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить AmoCRM');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSync = async () => {
    setIsSyncing(true);
    setMessage(null);
    try {
      await customService.runAmocrmSync(id);
      setMessage('Синхронизация запущена');
    } catch (err) {
      setError(err.message || 'Синхронизация не удалась');
    } finally {
      setIsSyncing(false);
    }
  };

  const enabled = settings?.is_amocrm_enabled;
  const connected = Boolean(connection?.connected);

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
          <p className="settings-subtitle">Подключение — в настройках.</p>
        </div>
        <span className={`crm-status ${connected ? 'crm-status--confirmed' : 'crm-status--completed'}`}>
          {connected ? 'Подключено' : 'Не подключено'}
        </span>
      </div>

      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}

      <div className="settings-section">
        {!enabled ? (
          <p className="form-hint">Включите модуль в настройках.</p>
        ) : (
          <>
            <p className="form-hint">Поддомен: {connection?.subdomain || '—'}</p>
            <p className="form-hint">Воронка: {connection?.pipeline_id || '—'}</p>
            <p className="form-hint">
              Последняя синхронизация:{' '}
              {connection?.last_sync_at ? new Date(connection.last_sync_at).toLocaleString() : '—'}
            </p>
          </>
        )}
        <div className="settings-actions">
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(id)} className="btn btn-black">
            Настройки
          </Link>
          <button type="button" onClick={handleSync} disabled={isSyncing || !connected} className="btn btn-outline">
            {isSyncing ? '...' : 'Синхронизировать статусы'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationAmocrmPage;
