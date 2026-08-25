import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

const ROTATION_STRATEGIES = [
  { value: 'round_robin', label: 'По кругу' },
  { value: 'least_used', label: 'Меньше использовался' },
  { value: 'risk_weighted', label: 'По риску бана' },
];

const CustomAutomationSettingsPage = () => {
  const { id } = useParams();
  const { isAdmin } = useCustomAuth();
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [credentials, setCredentials] = useState([]);
  const [newCredential, setNewCredential] = useState({ username: '', password: '' });
  const [isCreatingAccess, setIsCreatingAccess] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setForm(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить настройки');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  const loadCredentials = useCallback(async () => {
    if (!isAdmin) {
      return;
    }
    try {
      const data = await customService.listCredentials(id);
      setCredentials(data.items || []);
    } catch (err) {
      setCredentials([]);
    }
  }, [id, isAdmin]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    loadCredentials();
  }, [loadCredentials]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleNumberChange = (e) => {
    const { name, value } = e.target;
    const parsed = parseInt(value, 10);
    setForm((prev) => ({ ...prev, [name]: Number.isNaN(parsed) ? 0 : parsed }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSuccess(null);
    setError(null);
    setIsSaving(true);
    try {
      const payload = {
        rotation_strategy: form.rotation_strategy,
        max_daily_messages_per_account: form.max_daily_messages_per_account,
        is_chat_monitoring_enabled: form.is_chat_monitoring_enabled,
        is_neurocommenting_enabled: form.is_neurocommenting_enabled,
        is_shilling_enabled: form.is_shilling_enabled,
        is_digital_footprint_enabled: form.is_digital_footprint_enabled,
        is_dmp_one_enabled: form.is_dmp_one_enabled,
        is_amocrm_enabled: form.is_amocrm_enabled,
        lead_manager_contact: form.lead_manager_contact,
        status: form.status,
      };
      const data = await customService.updateAutomationSettings(id, payload);
      setSettings(data);
      setForm(data);
      setSuccess('Настройки сохранены');
    } catch (err) {
      setError(err.message || 'Не удалось сохранить');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateAccess = async (e) => {
    e.preventDefault();
    setIsCreatingAccess(true);
    setError(null);
    try {
      await customService.createCredential(id, newCredential);
      setNewCredential({ username: '', password: '' });
      await loadCredentials();
    } catch (err) {
      setError(err.message || 'Не удалось создать доступ');
    } finally {
      setIsCreatingAccess(false);
    }
  };

  if (isLoading) {
    return (
      <div className="project-settings-page project-settings-page--loading">
        <div className="settings-loading">
          <div className="spinner" />
          <p>Загрузка настроек...</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="project-settings-page">
        <p>{error || 'Не удалось загрузить настройки'}</p>
      </div>
    );
  }

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">Настройки</h1>
          <p className="settings-subtitle">
            Модули, ротация и доступ клиента. После включения система работает сама — подливайте аккаунты и чаты.
          </p>
        </div>
      </div>

      {error ? <p className="form-hint">{error}</p> : null}
      {success ? <p className="form-hint">{success}</p> : null}
      {settings?.warnings?.length > 0 ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Внимание</h3>
          {settings.warnings.map((warning) => (
            <p key={warning} className="form-hint">{warning}</p>
          ))}
        </div>
      ) : null}

      <form className="settings-form" onSubmit={handleSubmit}>
        <div className="settings-section">
          <h3 className="settings-section-title">Статус</h3>
          <div className="form-group">
            <label htmlFor="status">Воркеры</label>
            <select id="status" name="status" value={form.status || 'draft'} onChange={handleChange}>
              <option value="draft">Черновик</option>
              <option value="active">Активна</option>
              <option value="paused">Пауза</option>
              <option value="archived">Архив</option>
            </select>
          </div>
        </div>

        <div className="settings-section">
          <h3 className="settings-section-title">Модули</h3>
          {[
            { name: 'is_chat_monitoring_enabled', label: 'Мониторинг чатов и перехват заявок' },
            { name: 'is_neurocommenting_enabled', label: 'Нейрокомментинг' },
            { name: 'is_shilling_enabled', label: 'Шиллинг (парный нативный диалог)' },
            { name: 'is_digital_footprint_enabled', label: 'Цифровой след в дискуссиях' },
            { name: 'is_dmp_one_enabled', label: 'DMP.one' },
            { name: 'is_amocrm_enabled', label: 'AmoCRM (только фулфилмент)' },
          ].map((field) => (
            <div key={field.name} className="form-group">
              <label htmlFor={field.name}>
                <input
                  id={field.name}
                  type="checkbox"
                  name={field.name}
                  checked={Boolean(form[field.name])}
                  onChange={handleChange}
                />{' '}
                {field.label}
              </label>
            </div>
          ))}
          <span className="form-hint">
            Шиллинг: два аккаунта класса «шиллинг» общаются как живые люди. В чатах — случайно с 8:00 до 20:00 МСК с вероятностью 40% (не каждый день). Под постами — общее действие с нейрокомментингом на ~20% постов, никогда оба сразу.
          </span>
        </div>

        <div className="settings-section">
          <h3 className="settings-section-title">Ротация однодневок</h3>
          <div className="form-group">
            <label htmlFor="rotation_strategy">Стратегия</label>
            <select
              id="rotation_strategy"
              name="rotation_strategy"
              value={form.rotation_strategy || 'round_robin'}
              onChange={handleChange}
            >
              {ROTATION_STRATEGIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <span className="form-hint">
              Только для нейрокомментинга и массовых публичных действий. Диалог с лидом всегда ведёт один аккаунт.
              Шиллинг использует отдельный класс аккаунтов (минимум два) и не пересекается с нейрокомментингом под одним постом.
            </span>
          </div>
          <div className="form-group">
            <label htmlFor="max_daily_messages_per_account">Лимит сообщений на аккаунт в сутки</label>
            <input
              id="max_daily_messages_per_account"
              type="number"
              name="max_daily_messages_per_account"
              value={form.max_daily_messages_per_account || 0}
              onChange={handleNumberChange}
              min={0}
            />
          </div>
        </div>

        <div className="settings-section">
          <h3 className="settings-section-title">Передача лидов</h3>
          <div className="form-group">
            <label htmlFor="lead_manager_contact">Контакт менеджера</label>
            <input
              id="lead_manager_contact"
              type="text"
              name="lead_manager_contact"
              value={form.lead_manager_contact || ''}
              onChange={handleChange}
              placeholder="Telegram / email / webhook"
            />
            <span className="form-hint">Нужен, если AmoCRM выключена.</span>
          </div>
        </div>

        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={isSaving}>
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>

      {isAdmin ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Доступ клиента</h3>
          <form onSubmit={handleCreateAccess}>
            <div className="form-group">
              <label htmlFor="access-login">Логин</label>
              <input
                id="access-login"
                type="text"
                value={newCredential.username}
                onChange={(e) => setNewCredential((prev) => ({ ...prev, username: e.target.value }))}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="access-password">Пароль</label>
              <input
                id="access-password"
                type="text"
                value={newCredential.password}
                onChange={(e) => setNewCredential((prev) => ({ ...prev, password: e.target.value }))}
                required
              />
            </div>
            <div className="settings-actions">
              <button type="submit" className="btn btn-black" disabled={isCreatingAccess}>
                {isCreatingAccess ? 'Создание...' : 'Выдать доступ'}
              </button>
            </div>
          </form>
          {credentials.length === 0 ? (
            <p className="form-hint">Пока нет логинов клиента.</p>
          ) : (
            <div className="crm-list" style={{ marginTop: 16 }}>
              {credentials.map((item) => (
                <div key={item.id} className="crm-item">
                  <div className="crm-item-header">
                    <strong>{item.username}</strong>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={async () => {
                        if (!window.confirm('Удалить доступ?')) {
                          return;
                        }
                        await customService.deleteCredential(id, item.id);
                        await loadCredentials();
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationSettingsPage;
