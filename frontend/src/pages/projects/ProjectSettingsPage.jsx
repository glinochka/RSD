/**
 * Project Settings Page
 * Project configuration and management
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { useForm } from '../../hooks/useForm';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import '../../styles/projectSettingsPage.css';

// Icons
const SettingsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const ArchiveIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="21 8 21 21 3 21 3 8" />
    <rect x="1" y="3" width="22" height="5" />
    <line x1="10" y1="12" x2="14" y2="12" />
  </svg>
);

const TrashIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
);

const SaveIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
);

const INDUSTRIES = [
  { value: 'retail', label: 'Розничная торговля' },
  { value: 'food', label: 'Рестораны и кафе' },
  { value: 'beauty', label: 'Салоны красоты' },
  { value: 'healthcare', label: 'Медицина и здоровье' },
  { value: 'education', label: 'Образование' },
  { value: 'services', label: 'Услуги' },
  { value: 'tech', label: 'IT и технологии' },
  { value: 'consulting', label: 'Консалтинг' },
  { value: 'finance', label: 'Финансы' },
  { value: 'entertainment', label: 'Развлечения' },
  { value: 'auto', label: 'Автомобили' },
  { value: 'real_estate', label: 'Недвижимость' },
  { value: 'other', label: 'Другое' },
];

const ProjectSettingsPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();

  const [project, setProject] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);

  const form = useForm({
    initialValues: {
      name: '',
      description: '',
      industry: 'other',
    },
    onSubmit: async (values) => {
      await handleSave(values);
    },
  });

  useEffect(() => {
    loadProject();
  }, [projectId]);

  const loadProject = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProject(projectId);
      setProject(data);
      form.setValues({
        name: data.name || '',
        description: data.description || '',
        industry: data.industry || 'other',
      });
    } catch (error) {
      console.error('Failed to load project:', error);
      showError('Не удалось загрузить проект');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (values) => {
    try {
      setIsSaving(true);
      await projectService.updateProject(projectId, {
        name: values.name,
        description: values.description,
        industry: values.industry,
      });
      showSuccess('Настройки сохранены');
    } catch (error) {
      console.error('Failed to save project:', error);
      showError(error.message || 'Не удалось сохранить настройки');
    } finally {
      setIsSaving(false);
    }
  };

  const handleArchive = async () => {
    try {
      await projectService.archiveProject(projectId);
      showSuccess('Проект архивирован');
      navigate(NAVIGATION_ROUTES.PROJECTS_LIST);
    } catch (error) {
      console.error('Failed to archive project:', error);
      showError(error.message || 'Не удалось архивировать проект');
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

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div className="settings-header-icon">
          <SettingsIcon />
        </div>
        <div>
          <h2 className="settings-title">Настройки проекта</h2>
          <p className="settings-subtitle">Управление параметрами и данными проекта</p>
        </div>
      </div>

      <form onSubmit={form.handleSubmit} className="settings-form">
        <div className="settings-section">
          <h3 className="settings-section-title">Основная информация</h3>

          <div className="form-group">
            <label htmlFor="name">Название проекта *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={form.values.name}
              onChange={form.handleChange}
              onBlur={form.handleBlur}
              placeholder="Мой бизнес"
              required
              maxLength={200}
            />
            <span className="form-hint">Отображается в заголовке и списке проектов</span>
          </div>

          <div className="form-group">
            <label htmlFor="industry">Отрасль</label>
            <select
              id="industry"
              name="industry"
              value={form.values.industry}
              onChange={form.handleChange}
              onBlur={form.handleBlur}
            >
              {INDUSTRIES.map((ind) => (
                <option key={ind.value} value={ind.value}>
                  {ind.label}
                </option>
              ))}
            </select>
            <span className="form-hint">Используется для генерации AI-рекомендаций</span>
          </div>

          <div className="form-group">
            <label htmlFor="description">Описание</label>
            <textarea
              id="description"
              name="description"
              value={form.values.description}
              onChange={form.handleChange}
              onBlur={form.handleBlur}
              placeholder="Краткое описание бизнеса..."
              rows={4}
              maxLength={1000}
            />
            <span className="form-hint">
              {form.values.description?.length || 0} / 1000
            </span>
          </div>
        </div>

        <div className="settings-actions">
          <button
            type="submit"
            className="btn btn-black"
            disabled={isSaving || !form.values.name.trim()}
          >
            {isSaving ? (
              <>
                <span className="spinner-small" />
                Сохранение...
              </>
            ) : (
              <>
                <SaveIcon />
                Сохранить изменения
              </>
            )}
          </button>
        </div>
      </form>

      <div className="settings-section settings-section--danger">
        <h3 className="settings-section-title settings-section-title--danger">
          Опасная зона
        </h3>

        <div className="danger-action">
          <div className="danger-action-info">
            <h4>Архивировать проект</h4>
            <p>
              Проект будет скрыт из списка. Все агенты и сайты останутся активными.
              Отменить действие можно только через поддержку.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setShowArchiveConfirm(true)}
          >
            <ArchiveIcon />
            Архивировать
          </button>
        </div>
      </div>

      {/* Archive Confirmation Modal */}
      {showArchiveConfirm && (
        <div className="modal-overlay">
          <div className="modal modal--small">
            <div className="modal-header">
              <h3 className="modal-title">
                <TrashIcon />
                Архивировать проект?
              </h3>
            </div>
            <div className="modal-body">
              <p>
                Вы уверены, что хотите архивировать проект <strong>{project?.name}</strong>?
              </p>
              <ul className="modal-list">
                <li>Проект будет скрыт из списка</li>
                <li>Агенты продолжат работу</li>
                <li>Сайт останется доступен</li>
                <li>Восстановление — через поддержку</li>
              </ul>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setShowArchiveConfirm(false)}
              >
                Отмена
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleArchive}
              >
                Архивировать
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectSettingsPage;
