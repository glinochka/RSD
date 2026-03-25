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
import { NAVIGATION_ROUTES } from '../config/constants';
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
    bot_token: {
      required: true,
      label: 'API ключ Telegram бота',
    },
    system_prompt: {
      required: true,
      label: 'Системный промпт',
      minLength: 1,
      maxLength: 5000,
    },
  };

  const form = useForm(
    {
      bot_token: '',
      system_prompt: '',
    },
    async (values) => {
      if (!isAuthenticated) {
        setShowAuthModal(true);
        return;
      }

      try {
        if (isEditMode) {
          showError('Редактирование агента сейчас недоступно на этой странице');
          return;
        }

        const createdAgent = await agentService.create({
          bot_token: values.bot_token.trim(),
          system_prompt: values.system_prompt.trim(),
        });

        const fallbackBotId = Number(values.bot_token.split(':', 1)[0]);
        const botId = createdAgent?.bot_id ?? fallbackBotId;

        if (!Number.isFinite(botId)) {
          showError('Не удалось определить bot_id после создания агента');
          return;
        }

        for (const file of uploadedFiles) {
          await agentService.uploadDocumentByBotId(botId, file);
        }

        showSuccess('Агент успешно создан!');

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
            {/* Bot Token */}
            <div className="form-group">
              <label htmlFor="bot_token">API ключ Telegram бота:</label>
              <input
                id="bot_token"
                type="text"
                name="bot_token"
                placeholder="Например, 8523614461:AAH8tzlk5jvC8aj-t2-fjuWYxfjVsrs2bUM"
                className={`input-main ${form.errors.bot_token ? 'error' : ''}`}
                value={form.values.bot_token}
                onChange={form.handleChange}
                onBlur={form.handleBlur}
                disabled={form.isSubmitting}
              />
              {form.touched.bot_token && form.errors.bot_token && (
                <span className="error-message">{form.errors.bot_token}</span>
              )}
            </div>

            {/* System prompt */}
            <div className="form-group">
              <label htmlFor="system_prompt">Системный промпт:</label>
              <textarea
                id="system_prompt"
                name="system_prompt"
                placeholder="Введите системный промпт для агента..."
                className="input-main textarea"
                value={form.values.system_prompt}
                onChange={form.handleChange}
                onBlur={form.handleBlur}
                disabled={form.isSubmitting}
                rows="5"
              ></textarea>
              {form.touched.system_prompt && form.errors.system_prompt && (
                <span className="error-message">{form.errors.system_prompt}</span>
              )}
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
                  Вы еще не авторизованы, войдите в аккаунт чтобы создать агента
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