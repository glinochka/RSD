/**
 * Project Integrations Page
 * Manage webhooks, external CRMs and business data connections.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import projectService from '../../services/projectService';
import { useNotification } from '../../context/useNotification';
import '../../styles/projectIntegrationsPage.css';

const INTEGRATION_TYPES = [
  { value: 'webhook', label: 'Входящий вебхук' },
  { value: 'crm_bitrix24', label: 'Битрикс24 (CRM)' },
  { value: 'crm_amocrm', label: 'amoCRM' },
  { value: 'external_api', label: 'Внешний API' },
];

const getTypeLabel = (type) => {
  const found = INTEGRATION_TYPES.find((t) => t.value === type);
  return found ? found.label : type;
};

const ProjectIntegrationsPage = () => {
  const { projectId } = useParams();
  const { showError, showSuccess } = useNotification();

  const [integrations, setIntegrations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    name: '',
    type: 'webhook',
    config: {},
    credentials: {},
    is_active: true,
  });

  const loadIntegrations = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectIntegrations(projectId);
      setIntegrations(data.items || []);
    } catch (error) {
      console.error('Failed to load integrations:', error);
      showError('Не удалось загрузить интеграции');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, showError]);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  const resetForm = () => {
    setForm({ name: '', type: 'webhook', config: {}, credentials: {}, is_active: true });
    setEditing(null);
    setIsFormOpen(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...form };
    if (editing && !payload.credentials?.token) {
      delete payload.credentials;
    }
    try {
      if (editing) {
        await projectService.updateProjectIntegration(projectId, editing.id, payload);
        showSuccess('Интеграция обновлена');
      } else {
        await projectService.createProjectIntegration(projectId, payload);
        showSuccess('Интеграция создана');
      }
      resetForm();
      loadIntegrations();
    } catch (error) {
      console.error('Failed to save integration:', error);
      showError(error.message || 'Не удалось сохранить интеграцию');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Удалить интеграцию?')) {
      return;
    }
    try {
      await projectService.deleteProjectIntegration(projectId, id);
      showSuccess('Интеграция удалена');
      loadIntegrations();
    } catch (error) {
      console.error('Failed to delete integration:', error);
      showError('Не удалось удалить интеграцию');
    }
  };

  const handleRotate = async (id) => {
    try {
      await projectService.rotateProjectIntegrationToken(projectId, id);
      showSuccess('Токен вебхука обновлен');
      loadIntegrations();
    } catch (error) {
      console.error('Failed to rotate token:', error);
      showError('Не удалось обновить токен');
    }
  };

  const startEdit = (integration) => {
    setEditing(integration);
    setForm({
      name: integration.name,
      type: integration.type,
      config: integration.config || {},
      credentials: {},
      is_active: integration.is_active,
    });
    setIsFormOpen(true);
  };

  if (isLoading) {
    return (
      <div className="project-integrations-page project-integrations-page--loading">
        <div className="spinner" />
        <p>Загрузка интеграций...</p>
      </div>
    );
  }

  return (
    <div className="project-integrations-page">
      <div className="integrations-header">
        <div>
          <h2 className="integrations-title">Интеграции</h2>
          <p className="integrations-subtitle">
            Вебхуки, внешние CRM и другие источники бизнес-данных
          </p>
        </div>
        <button
          type="button"
          className="btn btn-black"
          onClick={() => setIsFormOpen(true)}
        >
          Добавить интеграцию
        </button>
      </div>

      {isFormOpen && (
        <form className="integrations-form" onSubmit={handleSubmit}>
          <h3 className="integrations-form-title">
            {editing ? 'Редактировать интеграцию' : 'Новая интеграция'}
          </h3>
          <div className="integrations-form-row">
            <label className="integrations-field">
              <span>Название</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Например, Битрикс24"
                required
              />
            </label>
            <label className="integrations-field">
              <span>Тип</span>
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                {INTEGRATION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="integrations-field">
            <span>Дополнительные настройки (JSON)</span>
            <textarea
              rows={3}
              value={JSON.stringify(form.config, null, 2)}
              onChange={(e) => {
                try {
                  setForm({ ...form, config: JSON.parse(e.target.value) });
                } catch {
                  // ignore invalid JSON while typing
                }
              }}
            />
          </label>
          <label className="integrations-field">
            <span>Учетные данные / токен</span>
            <input
              type="text"
              value={form.credentials.token || ''}
              onChange={(e) =>
                setForm({ ...form, credentials: { token: e.target.value } })
              }
              placeholder="Введите токен или API-ключ"
            />
          </label>
          <label className="integrations-field integrations-field--checkbox">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <span>Активная</span>
          </label>
          <div className="integrations-form-actions">
            <button type="submit" className="btn btn-black">
              {editing ? 'Сохранить' : 'Создать'}
            </button>
            <button type="button" className="btn btn-outline" onClick={resetForm}>
              Отмена
            </button>
          </div>
        </form>
      )}

      <div className="integrations-list">
        {integrations.length === 0 && !isFormOpen && (
          <div className="integrations-empty">
            <p>Интеграций пока нет. Добавьте первую, чтобы собирать данные из внешних систем.</p>
          </div>
        )}

        {integrations.map((integration) => (
          <div key={integration.id} className="integration-card">
            <div className="integration-card-main">
              <div className="integration-card-icon">
                {integration.type === 'webhook' ? '⚡' : '🔗'}
              </div>
              <div className="integration-card-info">
                <h3 className="integration-card-name">{integration.name}</h3>
                <span className={`integration-card-type integration-card-type--${integration.type}`}>
                  {getTypeLabel(integration.type)}
                </span>
                <span className={`integration-card-status ${integration.is_active ? 'active' : 'inactive'}`}>
                  {integration.is_active ? 'Активна' : 'Выключена'}
                </span>
              </div>
            </div>

            {integration.type === 'webhook' && (
              <div className="integration-card-webhook">
                <span>Вебхук URL:</span>
                <code>{integration.webhook_url}</code>
                <button
                  type="button"
                  className="btn btn-sm btn-outline"
                  onClick={() => handleRotate(integration.id)}
                >
                  Обновить токен
                </button>
              </div>
            )}

            <div className="integration-card-actions">
              <button
                type="button"
                className="btn btn-sm btn-outline"
                onClick={() => startEdit(integration)}
              >
                Редактировать
              </button>
              <button
                type="button"
                className="btn btn-sm btn-danger"
                onClick={() => handleDelete(integration.id)}
              >
                Удалить
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProjectIntegrationsPage;
