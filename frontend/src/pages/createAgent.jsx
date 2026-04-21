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
  const [useWhatsAppUserbotChannel, setUseWhatsAppUserbotChannel] = useState(false);
  const [useWhatsAppBusinessApiChannel, setUseWhatsAppBusinessApiChannel] = useState(false);
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [isUserbotVerified, setIsUserbotVerified] = useState(false);
  const [verifiedUserbotLabel, setVerifiedUserbotLabel] = useState('');
  const [whatsappUserbotMode, setWhatsappUserbotMode] = useState('simple');
  const [whatsappUserbotAuthToken, setWhatsappUserbotAuthToken] = useState('');
  const [whatsappUserbotAuthMethod, setWhatsappUserbotAuthMethod] = useState('qr');
  const [whatsappUserbotVerifyCode, setWhatsappUserbotVerifyCode] = useState('');
  const [whatsappUserbotQrDataUrl, setWhatsappUserbotQrDataUrl] = useState('');
  const [isSendingWhatsappUserbotCode, setIsSendingWhatsappUserbotCode] = useState(false);
  const [isVerifyingWhatsappUserbotCode, setIsVerifyingWhatsappUserbotCode] = useState(false);
  const [isWhatsappUserbotVerified, setIsWhatsappUserbotVerified] = useState(false);
  const [verifiedWhatsappUserbotLabel, setVerifiedWhatsappUserbotLabel] = useState('');
  const [whatsappUserbotPairingCode, setWhatsappUserbotPairingCode] = useState('');

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
      whatsapp_userbot_phone_number: '',
      whatsapp_userbot_session_string: '',
      whatsapp_userbot_client_label: '',
      whatsapp_phone_number_id: '',
      whatsapp_access_token: '',
      whatsapp_business_account_id: '',
      whatsapp_verify_token: '',
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
        const isWhatsAppUserbotMode = useWhatsAppUserbotChannel;
        const isWhatsAppBusinessApiMode = useWhatsAppBusinessApiChannel;

        if (!isBotMode && !isUserbotMode && !isWhatsAppUserbotMode && !isWhatsAppBusinessApiMode) {
          showError('Выберите хотя бы один способ подключения');
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
        if (isWhatsAppUserbotMode && !values.whatsapp_userbot_phone_number?.trim()) {
          form.setFieldError('whatsapp_userbot_phone_number', 'Номер WhatsApp обязателен');
          return;
        }
        if (isWhatsAppUserbotMode) {
          if (whatsappUserbotMode === 'simple') {
            if (!values.whatsapp_userbot_session_string?.trim() || !isWhatsappUserbotVerified) {
              form.setFieldError(
                'whatsapp_userbot_session_string',
                'Сначала подтвердите код и инициализируйте WhatsApp userbot-сессию'
              );
              return;
            }
          } else if (!values.whatsapp_userbot_session_string?.trim()) {
            form.setFieldError('whatsapp_userbot_session_string', 'Session string WhatsApp userbot обязателен');
            return;
          }
        }
        if (isWhatsAppBusinessApiMode && !values.whatsapp_phone_number_id?.trim()) {
          form.setFieldError('whatsapp_phone_number_id', 'Phone Number ID обязателен');
          return;
        }
        if (isWhatsAppBusinessApiMode && !values.whatsapp_access_token?.trim()) {
          form.setFieldError('whatsapp_access_token', 'Access Token обязателен');
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

        const primaryProvider = isBotMode
          ? 'telegram_bot'
          : isUserbotMode
            ? 'telegram_userbot'
            : isWhatsAppUserbotMode
              ? 'whatsapp_userbot'
              : 'whatsapp_business_api';

        if (isBotMode) {
          await agentService.addBotChannel({
            agent_id: agentId,
            bot_token: values.bot_token.trim(),
            make_primary: primaryProvider === 'telegram_bot',
          });
        }
        if (isUserbotMode) {
          await agentService.addUserbotChannel({
            agent_id: agentId,
            api_id: Number(values.api_id),
            api_hash: values.api_hash.trim(),
            session_string: values.session_string.trim(),
            make_primary: primaryProvider === 'telegram_userbot',
          });
        }
        if (isWhatsAppUserbotMode) {
          await agentService.addWhatsAppUserbotChannel({
            agent_id: agentId,
            phone_number: values.whatsapp_userbot_phone_number.trim(),
            session_string: values.whatsapp_userbot_session_string.trim(),
            client_label: values.whatsapp_userbot_client_label?.trim() || undefined,
            make_primary: primaryProvider === 'whatsapp_userbot',
          });
        }
        if (isWhatsAppBusinessApiMode) {
          await agentService.addWhatsAppBusinessApiChannel({
            agent_id: agentId,
            phone_number_id: values.whatsapp_phone_number_id.trim(),
            access_token: values.whatsapp_access_token.trim(),
            business_account_id: values.whatsapp_business_account_id?.trim() || undefined,
            verify_token: values.whatsapp_verify_token?.trim() || undefined,
            make_primary: primaryProvider === 'whatsapp_business_api',
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

  const toggleWhatsAppBusinessApiChannel = () => {
    setUseWhatsAppBusinessApiChannel((prev) => {
      const next = !prev;
      if (!next) {
        form.setFieldValue('whatsapp_phone_number_id', '');
        form.setFieldValue('whatsapp_access_token', '');
        form.setFieldValue('whatsapp_business_account_id', '');
        form.setFieldValue('whatsapp_verify_token', '');
        form.setFieldError('whatsapp_phone_number_id', undefined);
        form.setFieldError('whatsapp_access_token', undefined);
      }
      return next;
    });
  };

  const toggleWhatsAppUserbotChannel = () => {
    setUseWhatsAppUserbotChannel((prev) => {
      const next = !prev;
      if (!next) {
        setWhatsappUserbotMode('simple');
        setWhatsappUserbotAuthToken('');
        setWhatsappUserbotAuthMethod('qr');
        setWhatsappUserbotVerifyCode('');
        setWhatsappUserbotPairingCode('');
        setWhatsappUserbotQrDataUrl('');
        setIsSendingWhatsappUserbotCode(false);
        setIsVerifyingWhatsappUserbotCode(false);
        setIsWhatsappUserbotVerified(false);
        setVerifiedWhatsappUserbotLabel('');
        form.setFieldValue('whatsapp_userbot_phone_number', '');
        form.setFieldValue('whatsapp_userbot_session_string', '');
        form.setFieldValue('whatsapp_userbot_client_label', '');
        form.setFieldError('whatsapp_userbot_phone_number', undefined);
        form.setFieldError('whatsapp_userbot_session_string', undefined);
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

  const switchWhatsappUserbotMode = (mode) => {
    setWhatsappUserbotMode(mode);
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotAuthMethod('qr');
    setWhatsappUserbotVerifyCode('');
    setWhatsappUserbotPairingCode('');
    setWhatsappUserbotQrDataUrl('');
    setIsWhatsappUserbotVerified(false);
    setVerifiedWhatsappUserbotLabel('');
    form.setFieldValue('whatsapp_userbot_session_string', '');
    form.setFieldError('whatsapp_userbot_session_string', undefined);
  };

  const handleWhatsappUserbotRequestCode = async () => {
    if (!form.values.whatsapp_userbot_phone_number?.trim()) {
      form.setFieldError('whatsapp_userbot_phone_number', 'Номер WhatsApp обязателен');
      return;
    }
    setIsSendingWhatsappUserbotCode(true);
    try {
      const response = await agentService.requestWhatsAppUserbotCode({
        phone_number: form.values.whatsapp_userbot_phone_number.trim(),
        auth_method: whatsappUserbotAuthMethod,
      });
      setWhatsappUserbotAuthToken(response.auth_token);
      setWhatsappUserbotAuthMethod(response.auth_method || whatsappUserbotAuthMethod);
      setWhatsappUserbotPairingCode(response.pairing_code || '');
      setWhatsappUserbotQrDataUrl(response.qr_data_url || '');
      setWhatsappUserbotVerifyCode((response.auth_method || whatsappUserbotAuthMethod) === 'pairing_code' ? (response.pairing_code || '') : '');
      setIsWhatsappUserbotVerified(false);
      setVerifiedWhatsappUserbotLabel('');
      form.setFieldValue('whatsapp_userbot_session_string', '');
      showSuccess(
        response.hint ||
          ((response.auth_method || whatsappUserbotAuthMethod) === 'qr'
            ? 'QR готов. Отсканируйте его в WhatsApp и затем нажмите «Проверить подключение».'
            : 'Pairing-код получен. Введите его в WhatsApp на телефоне, затем нажмите «Подтвердить код».')
      );
    } catch (error) {
      showError(error.message || 'Не удалось запросить код WhatsApp');
    } finally {
      setIsSendingWhatsappUserbotCode(false);
    }
  };

  const handleWhatsappUserbotVerifyCode = async () => {
    if (!whatsappUserbotAuthToken) {
      showError('Сначала запросите код подтверждения WhatsApp');
      return;
    }
    if (whatsappUserbotAuthMethod === 'pairing_code' && !whatsappUserbotVerifyCode.trim()) {
      showError('Введите код подтверждения WhatsApp');
      return;
    }
    setIsVerifyingWhatsappUserbotCode(true);
    try {
      const response = await agentService.verifyWhatsAppUserbotCode({
        auth_token: whatsappUserbotAuthToken,
        code: whatsappUserbotAuthMethod === 'pairing_code' ? whatsappUserbotVerifyCode.trim() : undefined,
      });
      form.setFieldValue('whatsapp_userbot_session_string', response.session_string || '');
      if (response.phone_number) {
        form.setFieldValue('whatsapp_userbot_phone_number', response.phone_number);
      }
      setIsWhatsappUserbotVerified(true);
      setVerifiedWhatsappUserbotLabel(response.display_name || response.phone_number || 'успешно');
      showSuccess('WhatsApp userbot успешно инициализирован');
    } catch (error) {
      setIsWhatsappUserbotVerified(false);
      showError(error.message || 'Не удалось подтвердить код WhatsApp');
    } finally {
      setIsVerifyingWhatsappUserbotCode(false);
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
              <label>Тип подключения:</label>
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
                <button
                  type="button"
                  className={`connection-type-card ${useWhatsAppUserbotChannel ? 'active' : ''}`}
                  onClick={toggleWhatsAppUserbotChannel}
                  disabled={form.isSubmitting}
                >
                  WhatsApp userbot
                </button>
                <button
                  type="button"
                  className={`connection-type-card ${useWhatsAppBusinessApiChannel ? 'active' : ''}`}
                  onClick={toggleWhatsAppBusinessApiChannel}
                  disabled={form.isSubmitting}
                >
                  WhatsApp Business API
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

            {useWhatsAppBusinessApiChannel && (
              <div className="form-group">
                <label htmlFor="whatsapp_phone_number_id">WhatsApp Phone Number ID:</label>
                <input
                  id="whatsapp_phone_number_id"
                  type="text"
                  name="whatsapp_phone_number_id"
                  placeholder="Например: 123456789012345"
                  className={`input-main ${form.errors.whatsapp_phone_number_id ? 'error' : ''}`}
                  value={form.values.whatsapp_phone_number_id}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.whatsapp_phone_number_id && (
                  <span className="error-message">{form.errors.whatsapp_phone_number_id}</span>
                )}

                <label htmlFor="whatsapp_access_token" className="mt-input">WhatsApp Access Token:</label>
                <input
                  id="whatsapp_access_token"
                  type="password"
                  name="whatsapp_access_token"
                  placeholder="Введите постоянный токен Meta"
                  className={`input-main ${form.errors.whatsapp_access_token ? 'error' : ''}`}
                  value={form.values.whatsapp_access_token}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.whatsapp_access_token && (
                  <span className="error-message">{form.errors.whatsapp_access_token}</span>
                )}

                <label htmlFor="whatsapp_business_account_id" className="mt-input">
                  WhatsApp Business Account ID (опционально):
                </label>
                <input
                  id="whatsapp_business_account_id"
                  type="text"
                  name="whatsapp_business_account_id"
                  placeholder="Например: 987654321098765"
                  className="input-main"
                  value={form.values.whatsapp_business_account_id}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />

                <label htmlFor="whatsapp_verify_token" className="mt-input">
                  Webhook Verify Token (опционально):
                </label>
                <input
                  id="whatsapp_verify_token"
                  type="text"
                  name="whatsapp_verify_token"
                  placeholder="Токен для проверки webhook"
                  className="input-main"
                  value={form.values.whatsapp_verify_token}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />

                <p className="help-text">
                  Данные сохраняются как канал агента и используются для интеграции WhatsApp Business API.
                </p>
              </div>
            )}

            {useWhatsAppUserbotChannel && (
              <div className="form-group">
                <label>Режим подключения WhatsApp userbot:</label>
                <div className="connection-type-grid">
                  <button
                    type="button"
                    className={`connection-type-card ${whatsappUserbotMode === 'simple' ? 'active' : ''}`}
                    onClick={() => switchWhatsappUserbotMode('simple')}
                    disabled={form.isSubmitting}
                  >
                    Простое подключение
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${whatsappUserbotMode === 'expert' ? 'active' : ''}`}
                    onClick={() => switchWhatsappUserbotMode('expert')}
                    disabled={form.isSubmitting}
                  >
                    Режим эксперта
                  </button>
                </div>

                <label htmlFor="whatsapp_userbot_phone_number">Номер WhatsApp userbot:</label>
                <input
                  id="whatsapp_userbot_phone_number"
                  type="text"
                  name="whatsapp_userbot_phone_number"
                  placeholder="+79990001122"
                  className={`input-main ${form.errors.whatsapp_userbot_phone_number ? 'error' : ''}`}
                  value={form.values.whatsapp_userbot_phone_number}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.whatsapp_userbot_phone_number && (
                  <span className="error-message">{form.errors.whatsapp_userbot_phone_number}</span>
                )}

                {whatsappUserbotMode === 'simple' ? (
                  <>
                    <div className="connection-type-grid channels-tabs">
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotAuthMethod === 'qr' ? 'active' : ''}`}
                        onClick={() => setWhatsappUserbotAuthMethod('qr')}
                        disabled={form.isSubmitting || isSendingWhatsappUserbotCode}
                      >
                        QR-код
                      </button>
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotAuthMethod === 'pairing_code' ? 'active' : ''}`}
                        onClick={() => setWhatsappUserbotAuthMethod('pairing_code')}
                        disabled={form.isSubmitting || isSendingWhatsappUserbotCode}
                      >
                        Pairing-код
                      </button>
                    </div>

                    <div className="channel-actions-row">
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleWhatsappUserbotRequestCode}
                        disabled={form.isSubmitting || isSendingWhatsappUserbotCode}
                      >
                        {isSendingWhatsappUserbotCode ? 'Отправка...' : 'Запросить код'}
                      </button>
                    </div>

                    {whatsappUserbotQrDataUrl ? (
                      <div className="help-text" style={{ marginTop: 'var(--spacing-base)' }}>
                        <p><strong>QR для подключения:</strong></p>
                        <img
                          src={whatsappUserbotQrDataUrl}
                          alt="WhatsApp QR"
                          style={{ width: '220px', maxWidth: '100%', background: '#fff', padding: '8px', borderRadius: '8px' }}
                        />
                        <p style={{ marginTop: 'var(--spacing-sm)' }}>
                          Откройте WhatsApp → Настройки → Связанные устройства → Привязать устройство и отсканируйте QR.
                        </p>
                      </div>
                    ) : null}

                    {whatsappUserbotPairingCode ? (
                      <div className="help-text" style={{ marginTop: 'var(--spacing-base)' }}>
                        <p>
                          <strong>Pairing-код:</strong>{' '}
                          <code style={{ fontSize: '1.1em', letterSpacing: '0.05em' }}>{whatsappUserbotPairingCode}</code>
                        </p>
                        <p>
                          На телефоне откройте WhatsApp → Настройки → Связанные устройства → Привязать устройство и введите
                          этот код. После подтверждения в WhatsApp нажмите «Подтвердить код» ниже (тот же код).
                        </p>
                      </div>
                    ) : null}

                    {whatsappUserbotAuthMethod === 'pairing_code' ? (
                      <>
                        <label htmlFor="whatsapp_userbot_verify_code" className="mt-input">
                          Тот же pairing-код для подтверждения на сайте:
                        </label>
                        <input
                          id="whatsapp_userbot_verify_code"
                          type="text"
                          name="whatsapp_userbot_verify_code"
                          placeholder="Введите код/подтверждение"
                          className="input-main"
                          value={whatsappUserbotVerifyCode}
                          onChange={(e) => setWhatsappUserbotVerifyCode(e.target.value)}
                          disabled={form.isSubmitting}
                        />
                      </>
                    ) : null}

                    <div className="channel-actions-row">
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleWhatsappUserbotVerifyCode}
                        disabled={form.isSubmitting || isVerifyingWhatsappUserbotCode}
                      >
                        {isVerifyingWhatsappUserbotCode
                          ? 'Проверка...'
                          : whatsappUserbotAuthMethod === 'qr'
                            ? 'Проверить подключение'
                            : 'Подтвердить код'}
                      </button>
                    </div>

                    {isWhatsappUserbotVerified && (
                      <p className="help-text userbot-success">
                        WhatsApp userbot подтвержден: {verifiedWhatsappUserbotLabel || 'успешно'}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <label htmlFor="whatsapp_userbot_session_string" className="mt-input">
                      Session string WhatsApp userbot:
                    </label>
                    <textarea
                      id="whatsapp_userbot_session_string"
                      name="whatsapp_userbot_session_string"
                      placeholder="Вставьте сериализованную сессию userbot"
                      className={`input-main textarea ${form.errors.whatsapp_userbot_session_string ? 'error' : ''}`}
                      value={form.values.whatsapp_userbot_session_string}
                      onChange={form.handleChange}
                      disabled={form.isSubmitting}
                      rows="4"
                    ></textarea>
                    {form.errors.whatsapp_userbot_session_string && (
                      <span className="error-message">{form.errors.whatsapp_userbot_session_string}</span>
                    )}
                  </>
                )}

                <label htmlFor="whatsapp_userbot_client_label" className="mt-input">
                  Название клиента (опционально):
                </label>
                <input
                  id="whatsapp_userbot_client_label"
                  type="text"
                  name="whatsapp_userbot_client_label"
                  placeholder="Например: WA MultiDevice Session #1"
                  className="input-main"
                  value={form.values.whatsapp_userbot_client_label}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />

                <p className="help-text">
                  Используйте только свою userbot-сессию. Это не официальный канал Meta.
                </p>
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