import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';

const CopyField = ({ id, label, value, hint }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    if (!value) {
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" value={value || ''} readOnly />
      {hint ? <span className="form-hint">{hint}</span> : null}
      <div className="settings-actions">
        <button type="button" className="btn btn-outline" onClick={handleCopy} disabled={!value}>
          {copied ? 'Скопировано' : 'Копировать'}
        </button>
      </div>
    </div>
  );
};

const CustomAutomationDmpConnectionPage = () => {
  const { id } = useParams();
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isRotating, setIsRotating] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить подключение');
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleRotate = async () => {
    if (!window.confirm('Выпустить новый секрет? Старый URL перестанет работать.')) {
      return;
    }
    setIsRotating(true);
    setMessage(null);
    try {
      await customService.rotateDmpWebhookSecret(id);
      setMessage('Секрет обновлён');
      await loadSettings();
    } catch (err) {
      setError(err.message || 'Не удалось обновить секрет');
    } finally {
      setIsRotating(false);
    }
  };

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Подключение DMP</h1>
          <p>Ключ и вебхук для приёма номеров из DMP.one по API.</p>
        </div>
      </div>
      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}
      <div className="ubt-panel">
        <CopyField
          id="dmp-webhook-url"
          label="Webhook URL"
          value={settings?.dmp_webhook_url || ''}
          hint="Вставьте в DMP One → Интеграция, формат JSON."
        />
        <CopyField
          id="dmp-webhook-secret"
          label="API / webhook-секрет"
          value={settings?.dmp_webhook_secret || ''}
          hint="Этот секрет подписывает входящие номера. Исходящий API-ключ DMP живёт в окружении сервера."
        />
        <div className="settings-actions">
          <button type="button" className="btn btn-outline" onClick={handleRotate} disabled={isRotating}>
            {isRotating ? '...' : 'Новый секрет'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationDmpConnectionPage;
