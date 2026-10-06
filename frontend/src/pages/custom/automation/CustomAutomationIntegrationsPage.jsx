import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import customService from '../../../services/customService';
import CustomAutomationIntegrationsBlock from './CustomAutomationIntegrationsBlock';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customIntegrations.css';

const CustomAutomationIntegrationsPage = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const loadSettings = useCallback(async () => {
    try {
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить интеграции');
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    const amocrm = searchParams.get('amocrm');
    if (!amocrm) {
      return;
    }
    if (amocrm === 'connected') {
      setMessage('AmoCRM подключено');
    } else if (amocrm === 'error') {
      setError('Не удалось подключить AmoCRM');
    }
    const next = new URLSearchParams(searchParams);
    next.delete('amocrm');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Интеграции</h1>
          <p>Готовые шаблоны Telegram и AmoCRM плюс конструктор для любых других сервисов.</p>
        </div>
      </div>
      {error ? <p className="form-hint">{error}</p> : null}
      {message ? <p className="form-hint">{message}</p> : null}
      {settings ? (
        <CustomAutomationIntegrationsBlock
          automationId={id}
          settings={settings}
          hideDmp
          onReloadSettings={loadSettings}
          onError={setError}
          onMessage={setMessage}
        />
      ) : (
        <p className="ubt-empty">Загрузка...</p>
      )}
    </div>
  );
};

export default CustomAutomationIntegrationsPage;
