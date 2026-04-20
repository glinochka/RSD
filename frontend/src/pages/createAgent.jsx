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

const fileIdentity = (file) => `${file.name}::${file.size}::${file.lastModified}`;
const linkIdentity = (link) => link.trim().toLowerCase();

const CreateAgentContent = () => {
  const navigate = useNavigate();
  const { id: agentId } = useParams();
  const { showError, showSuccess } = useNotification();
  const { isAuthenticated } = useAuth();
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [pendingLink, setPendingLink] = useState('');
  const [uploadedLinks, setUploadedLinks] = useState([]);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [useBotChannel, setUseBotChannel] = useState(true);
  const [useUserbotChannel, setUseUserbotChannel] = useState(false);
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [isUserbotVerified, setIsUserbotVerified] = useState(false);
  const [verifiedUserbotLabel, setVerifiedUserbotLabel] = useState('');

  const isEditMode = !!agentId;

  const validationRules = {
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
      api_id: '',
      api_hash: '',
      phone_number: '',
      verify_code: '',
      password_2fa: '',
      session_string: '',
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

        const isBotMode = useBotChannel;
        const isUserbotMode = useUserbotChannel;

        if (!isBotMode && !isUserbotMode) {
          showError('Выберите хотя бы один способ подключения Telegram');
          return;
        }

        if (isBotMode && !values.bot_token?.trim()) {
          form.setFieldError('bot_token', 'API ключ Telegram бота обязателен');
          return;
        }
        if (isUserbotMode && !values.api_id?.toString().trim()) {
          form.setFieldError('api_id', 'API ID обязателен');
          return;
        }
        if (isUserbotMode && !values.api_hash?.trim()) {
          form.setFieldError('api_hash', 'API hash обязателен');
          return;
        }
        if (isUserbotMode && !values.phone_number?.trim()) {
          form.setFieldError('phone_number', 'Номер телефона обязателен');
          return;
        }
        if (isUserbotMode && (!values.session_string?.trim() || !isUserbotVerified)) {
          form.setFieldError('verify_code', 'Сначала подтвердите код и сохраните userbot-сессию');
          return;
        }

        const createdAgent = await agentService.createEmpty({
          system_prompt: values.system_prompt.trim(),
        });
        const agentId = createdAgent?.id;
        if (!Number.isFinite(agentId)) {
          showError('Не удалось определить id агента после создания');
          return;
        }

        if (isBotMode) {
          await agentService.addBotChannel({
            agent_id: agentId,
            bot_token: values.bot_token.trim(),
            make_primary: true,
          });
        }
        if (isUserbotMode) {
          await agentService.addUserbotChannel({
            agent_id: agentId,
            api_id: Number(values.api_id),
            api_hash: values.api_hash.trim(),
            session_string: values.session_string.trim(),
            make_primary: !isBotMode,
          });
        }

        for (const file of uploadedFiles) {
          await agentService.uploadDocumentByBotId(agentId, file);
        }

        for (const link of uploadedLinks) {
          await agentService.uploadPublicLinkByBotId(agentId, link);
        }

        showSuccess('Агент успешно создан!');

        navigate(NAVIGATION_ROUTES.AGENTS);
      } catch (error) {
        showError(error.message || 'Ошибка при сохранении агента');
      }
    },
    validationRules
  );

  const clearUserbotLocalState = () => {
    setUserbotAuthToken('');
    setIsUserbotVerified(false);
    setVerifiedUserbotLabel('');
    form.setFieldValue('api_id', '');
    form.setFieldValue('api_hash', '');
    form.setFieldValue('phone_number', '');
    form.setFieldValue('verify_code', '');
    form.setFieldValue('password_2fa', '');
    form.setFieldValue('session_string', '');
    form.setFieldError('verify_code', undefined);
  };

  const toggleBotChannel = () => {
    setUseBotChannel((prev) => {
      const next = !prev;
      if (!next) {
        form.setFieldValue('bot_token', '');
        form.setFieldError('bot_token', undefined);
      }
      return next;
    });
  };

  const toggleUserbotChannel = () => {
    setUseUserbotChannel((prev) => {
      const next = !prev;
      if (!next) {
        clearUserbotLocalState();
      }
      return next;
    });
  };

  const handleUserbotRequestCode = async () => {
    if (!form.values.api_id?.toString().trim()) {
      form.setFieldError('api_id', 'API ID обязателен');
      return;
    }
    if (!form.values.api_hash?.trim()) {
      form.setFieldError('api_hash', 'API hash обязателен');
      return;
    }
    if (!form.values.phone_number?.trim()) {
      form.setFieldError('phone_number', 'Номер телефона обязателен');
      return;
    }

    setIsSendingCode(true);
    try {
      const response = await agentService.requestUserbotCode({
        api_id: Number(form.values.api_id),
        api_hash: form.values.api_hash.trim(),
        phone_number: form.values.phone_number.trim(),
      });
      setUserbotAuthToken(response.auth_token);
      setIsUserbotVerified(false);
      setVerifiedUserbotLabel('');
      form.setFieldValue('session_string', '');
      showSuccess('Код подтверждения отправлен в Telegram');
    } catch (error) {
      showError(error.message || 'Не удалось отправить код Telegram');
    } finally {
      setIsSendingCode(false);
    }
  };

  const handleUserbotVerifyCode = async () => {
    if (!userbotAuthToken) {
      showError('Сначала запросите код подтверждения');
      return;
    }
    if (!form.values.verify_code?.trim()) {
      form.setFieldError('verify_code', 'Введите код подтверждения');
      return;
    }

    setIsVerifyingCode(true);
    try {
      const response = await agentService.verifyUserbotCode({
        auth_token: userbotAuthToken,
        code: form.values.verify_code.trim(),
        password: form.values.password_2fa?.trim() || undefined,
      });
      form.setFieldValue('session_string', response.session_string || '');
      setIsUserbotVerified(true);
      const label = response.username
        ? `@${response.username}`
        : [response.first_name, response.last_name].filter(Boolean).join(' ') || `id: ${response.telegram_id}`;
      setVerifiedUserbotLabel(label);
      showSuccess('Userbot успешно подтвержден');
    } catch (error) {
      setIsUserbotVerified(false);
      showError(error.message || 'Не удалось подтвердить код');
    } finally {
      setIsVerifyingCode(false);
    }
  };

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

    setUploadedFiles((prev) => {
      const merged = [...prev, ...validFiles];
      return Array.from(new Map(merged.map((f) => [fileIdentity(f), f])).values());
    });
  };

  const handleRemoveFile = (index) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const isValidPublicUrl = (value) => {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const handleAddLink = () => {
    const normalized = pendingLink.trim();
    if (!normalized) {
      return;
    }
    if (!isValidPublicUrl(normalized)) {
      showError('Некорректная ссылка. Разрешены только публичные http/https URL');
      return;
    }
    setUploadedLinks((prev) => {
      const merged = [...prev, normalized];
      return Array.from(new Map(merged.map((link) => [linkIdentity(link), link])).values());
    });
    setPendingLink('');
  };

  const handleRemoveLink = (index) => {
    setUploadedLinks((prev) => prev.filter((_, i) => i !== index));
  };

  const handleLinkKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAddLink();
    }
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
            <div className="form-group">
              <label>Тип подключения Telegram:</label>
              <div className="connection-type-grid">
                <button
                  type="button"
                  className={`connection-type-card ${useBotChannel ? 'active' : ''}`}
                  onClick={toggleBotChannel}
                  disabled={form.isSubmitting}
                >
                  Telegram бот
                </button>
                <button
                  type="button"
                  className={`connection-type-card ${useUserbotChannel ? 'active' : ''}`}
                  onClick={toggleUserbotChannel}
                  disabled={form.isSubmitting}
                >
                  Telegram юзербот
                </button>
              </div>
            </div>

            {useBotChannel && (
              <div className="form-group">
                <label htmlFor="bot_token">API ключ Telegram бота:</label>
                <input
                  id="bot_token"
                  type="text"
                  name="bot_token"
                  placeholder="Введите API ключ Telegram бота, его можно получить в BotFather"
                  className={`input-main ${form.errors.bot_token ? 'error' : ''}`}
                  value={form.values.bot_token}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                />
                {form.errors.bot_token && (
                  <span className="error-message">{form.errors.bot_token}</span>
                )}
              </div>
            )}

            {useUserbotChannel && (
              <div className="form-group">
                <label htmlFor="api_id">Telegram API ID:</label>
                <input
                  id="api_id"
                  type="number"
                  name="api_id"
                  placeholder="Введите API ID из my.telegram.org"
                  className={`input-main ${form.errors.api_id ? 'error' : ''}`}
                  value={form.values.api_id}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.api_id && (
                  <span className="error-message">{form.errors.api_id}</span>
                )}

                <label htmlFor="api_hash" className="mt-input">Telegram API hash:</label>
                <input
                  id="api_hash"
                  type="text"
                  name="api_hash"
                  placeholder="Введите API hash из my.telegram.org"
                  className={`input-main ${form.errors.api_hash ? 'error' : ''}`}
                  value={form.values.api_hash}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.api_hash && (
                  <span className="error-message">{form.errors.api_hash}</span>
                )}

                <label htmlFor="phone_number" className="mt-input">Номер телефона:</label>
                <input
                  id="phone_number"
                  type="text"
                  name="phone_number"
                  placeholder="+79990001122"
                  className={`input-main ${form.errors.phone_number ? 'error' : ''}`}
                  value={form.values.phone_number}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.phone_number && (
                  <span className="error-message">{form.errors.phone_number}</span>
                )}

                <div className="channel-actions-row">
                  <button
                    type="button"
                    className="btn btn-black"
                    onClick={handleUserbotRequestCode}
                    disabled={form.isSubmitting || isSendingCode}
                  >
                    {isSendingCode ? 'Отправка...' : 'Отправить код'}
                  </button>
                </div>

                <label htmlFor="verify_code" className="mt-input">Код из Telegram:</label>
                <input
                  id="verify_code"
                  type="text"
                  name="verify_code"
                  placeholder="12345"
                  className={`input-main ${form.errors.verify_code ? 'error' : ''}`}
                  value={form.values.verify_code}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.verify_code && (
                  <span className="error-message">{form.errors.verify_code}</span>
                )}

                <label htmlFor="password_2fa" className="mt-input">Пароль 2FA (если включен):</label>
                <input
                  id="password_2fa"
                  type="password"
                  name="password_2fa"
                  placeholder="Введите пароль 2FA при необходимости"
                  className="input-main"
                  value={form.values.password_2fa}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />

                <div className="channel-actions-row">
                  <button
                    type="button"
                    className="btn btn-black"
                    onClick={handleUserbotVerifyCode}
                    disabled={form.isSubmitting || isVerifyingCode}
                  >
                    {isVerifyingCode ? 'Проверка...' : 'Подтвердить код'}
                  </button>
                </div>

                {isUserbotVerified && (
                  <p className="help-text userbot-success">
                    Userbot подтвержден: {verifiedUserbotLabel || 'успешно'}
                  </p>
                )}
              </div>
            )}

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

            <div className="form-group">
              <label htmlFor="public-link">Публичные ссылки:</label>
              <div className="docs-container">
                {uploadedLinks.length > 0 && (
                  <ul className="docs-list">
                    {uploadedLinks.map((link, index) => (
                      <li key={linkIdentity(link)} className="doc-item">
                        <span>{link}</span>
                        <button
                          type="button"
                          className="remove-file-btn"
                          onClick={() => handleRemoveLink(index)}
                          aria-label="Remove link"
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="link-source-row">
                  <input
                    id="public-link"
                    type="url"
                    name="public-link"
                    placeholder="https://example.com/article"
                    className="input-main"
                    value={pendingLink}
                    onChange={(e) => setPendingLink(e.target.value)}
                    onKeyDown={handleLinkKeyDown}
                    disabled={form.isSubmitting}
                  />
                  <button
                    type="button"
                    className="btn btn-black link-add-btn"
                    onClick={handleAddLink}
                    disabled={form.isSubmitting}
                  >
                    Добавить ссылку
                  </button>
                </div>
              </div>
              <p className="help-text">Ссылка обрабатывается один раз и не обновляется автоматически</p>
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