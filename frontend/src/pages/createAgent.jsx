/**
 * Create/Edit Agent Page
 * Form for creating or editing agents
 */

import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import MainLayout from '../components/Layout';
import { useForm } from '../hooks/useForm';
import { useNotification } from '../context/useNotification';
import { useAuth } from '../context/useAuth';
import agentService from '../services/agentService';
import { validateFile } from '../utils/validation';
import { AGENT_ROLES, AGENT_TASKS, NAVIGATION_ROUTES } from '../config/constants';
import '../styles/createAgent.css';

const CreateAgentContent = () => {
  const navigate = useNavigate();
  const { id: agentId } = useParams();
  const { showError, showSuccess } = useNotification();
  const { isAuthenticated } = useAuth();
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const isEditMode = !!agentId;

  const validationRules = {
    name: {
      required: true,
      label: 'Имя агента',
      minLength: 2,
      maxLength: 50,
    },
    role: {
      required: true,
      label: 'Роль агента',
    },
    task: {
      required: true,
      label: 'Задача',
    },
  };

  const form = useForm(
    {
      name: '',
      role: '',
      task: '',
      prompt: '',
    },
    async (values) => {
      if (!isAuthenticated) {
        setShowAuthModal(true);
        return;
      }

      try {
        const agentData = {
          ...values,
          files: uploadedFiles,
        };

        if (isEditMode) {
          await agentService.update(agentId, agentData);
          showSuccess('Агент успешно обновлен!');
        } else {
          await agentService.create(agentData);
          showSuccess('Агент успешно создан!');
        }

        navigate(NAVIGATION_ROUTES.AGENTS);
      } catch (error) {
        showError(error.message || 'Ошибка при сохранении агента');
      }
    },
    validationRules
  );

  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files || []);

    const validFiles = [];
    const errors = [];

    files.forEach((file) => {
      const validation = validateFile(file);
      if (validation.isValid) {
        validFiles.push(file);
      } else {
        errors.push(`${file.name}: ${validation.errors.join(', ')}`);
      }
    });

    if (errors.length > 0) {
      showError(`Ошибки при загрузке файлов:\n${errors.join('\n')}`);
    }

    setUploadedFiles((prev) => [...prev, ...validFiles]);
  };

  const handleRemoveFile = (index) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAuthRedirect = () => {
    setShowAuthModal(false);
    navigate(NAVIGATION_ROUTES.AUTH);
  };

  return (
    <MainLayout>
      <div className="create-agent-page">
          <section className="create-agent-header">
            <h2>{isEditMode ? 'Редактировать агента' : 'Создать нового агента'}</h2>
            <button
              type="submit"
              form="agent-form"
              className="btn btn-black btn-save"
              disabled={form.isSubmitting}
            >
              {form.isSubmitting ? 'Сохранение...' : 'Сохранить'}
            </button>
          </section>

          <form id="agent-form" className="agent-form" onSubmit={form.handleSubmit}>
            {/* Agent Name */}
            <div className="form-group">
              <label htmlFor="name">Имя агента:</label>
              <input
                id="name"
                type="text"
                name="name"
                placeholder="МОП"
                className={`input-main ${form.errors.name ? 'error' : ''}`}
                value={form.values.name}
                onChange={form.handleChange}
                onBlur={form.handleBlur}
                disabled={form.isSubmitting}
              />
              {form.touched.name && form.errors.name && (
                <span className="error-message">{form.errors.name}</span>
              )}
            </div>

            {/* Agent Role */}
            <div className="form-group">
              <label htmlFor="role">Роль агента:</label>
              <div className="select-wrapper">
                <select
                  id="role"
                  name="role"
                  value={form.values.role}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  className={form.errors.role ? 'error' : ''}
                >
                  <option value="">Выберите роль</option>
                  <option value={AGENT_ROLES.SALES_MANAGER}>
                    Менеджер отдела продаж
                  </option>
                  <option value={AGENT_ROLES.SUPPORT}>Техническая поддержка</option>
                  <option value={AGENT_ROLES.ASSISTANT}>Ассистент</option>
                </select>
              </div>
              {form.touched.role && form.errors.role && (
                <span className="error-message">{form.errors.role}</span>
              )}
            </div>

            {/* Agent Task */}
            <div className="form-group">
              <label htmlFor="task">Задача:</label>
              <div className="select-wrapper">
                <select
                  id="task"
                  name="task"
                  value={form.values.task}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  className={form.errors.task ? 'error' : ''}
                >
                  <option value="">Выберите задачу</option>
                  <option value={AGENT_TASKS.SALES}>Заставь клиента купить</option>
                  <option value={AGENT_TASKS.FAQ}>Ответь на вопросы по документам</option>
                  <option value={AGENT_TASKS.CONTACTS}>Собери контактные данные</option>
                </select>
              </div>
              {form.touched.task && form.errors.task && (
                <span className="error-message">{form.errors.task}</span>
              )}
            </div>

            {/* Prompt */}
            <div className="form-group">
              <label htmlFor="prompt">Промпт (опционально):</label>
              <textarea
                id="prompt"
                name="prompt"
                placeholder="Введите дополнительные инструкции для агента..."
                className="input-main textarea"
                value={form.values.prompt}
                onChange={form.handleChange}
                disabled={form.isSubmitting}
                rows="5"
              ></textarea>
            </div>

            {/* Files Upload */}
            <div className="form-group">
              <label htmlFor="files">Документация:</label>
              <div className="docs-container">
                {uploadedFiles.length > 0 && (
                  <ul className="docs-list">
                    {uploadedFiles.map((file, index) => (
                      <li key={index} className="doc-item">
                        <span>{file.name}</span>
                        <button
                          type="button"
                          className="remove-file-btn"
                          onClick={() => handleRemoveFile(index)}
                          aria-label="Remove file"
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                <label className="add-files-zone">
                  <input
                    type="file"
                    id="files"
                    multiple
                    accept=".pdf,.doc,.docx,.txt"
                    onChange={handleFileUpload}
                    disabled={form.isSubmitting}
                    style={{ display: 'none' }}
                  />
                  + Добавить файлы
                </label>
              </div>
              <p className="help-text">Максимальный размер файла: 10MB</p>
            </div>
          </form>

          {showAuthModal && (
            <div className="auth-modal-backdrop">
              <div className="auth-modal">
                <h3 className="auth-modal-title">
                  вы еще не авторизованы, войдите в аккаунт чтобы создать агента
                </h3>
                <div className="auth-modal-actions">
                  <button className="btn btn-black" onClick={handleAuthRedirect}>
                    Авторизоваться
                  </button>
                </div>
              </div>
            </div>
          )}
      </div>
    </MainLayout>
  );
};

const CreateAgent = CreateAgentContent;

export default CreateAgent;