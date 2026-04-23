/**
 * Create/Edit Agent Page
 * Form for creating or editing agents
 */

import React, { useEffect, useRef, useState } from 'react';
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
const CRM_TOOL_OPTIONS = [
  { value: 'find_contact', label: 'Поиск контактов' },
  { value: 'create_contact', label: 'Создание контакта' },
  { value: 'find_lead', label: 'Поиск сделок' },
  { value: 'create_lead', label: 'Создание сделки' },
  { value: 'update_lead', label: 'Изменение сделки' },
  { value: 'add_note', label: 'Добавление заметки' },
  { value: 'create_task', label: 'Создание задачи' },
  { value: 'assign_owner', label: 'Назначение ответственного' },
];

const parseAllowedTools = (raw) =>
  Array.from(
    new Set(
      String(raw || '')
        .split(',')
        .map((tool) => tool.trim())
        .filter(Boolean)
    )
  );

const buildCrmValidationSignature = (provider, baseUrl, token) =>
  `${String(provider || '').trim().toLowerCase()}|${String(baseUrl || '').trim()}|${String(token || '').trim()}`;

const SALES_DEFAULT_TEMPLATE_CONFIG = {
  mode: 'draft_only',
  qualification_model: 'deepseek-chat',
  generation_model: 'deepseek-chat',
  min_confidence: 0.75,
  scan_scope: {
    include_chat_ids: [],
    exclude_chat_ids: [],
  },
  dm_limits: {
    per_minute: 3,
    per_hour: 25,
    per_day: 120,
    per_source_chat_per_day: 40,
  },
  cooldown_days: 14,
  dedup_window_days: 30,
  allowed_languages: ['ru', 'en'],
  quiet_hours_local: '22:00-09:00',
  offer_profile_id: null,
  confirmation_policy: 'confirm_risky',
  allowed_tools: ['schedule_dm', 'skip_lead', 'record_lead_signal', 'create_crm_lead', 'mark_contacted'],
};

const TEMPLATE_TYPE_HELP = {
  qa: 'Агент отвечает на вопросы по подключённой базе знаний (RAG): поиск по документам и выдержки в ответах. Подходит для поддержки и консультаций.',
  crm_admin:
    'Агент работает по шаблону администратора CRM: поиск и создание контактов, сделок, задач и другое в соответствии с настройками ниже. Перед сохранением проверьте подключение к CRM. Функция в статусе BETA.',
  sales_manager:
    'Агент работает в режиме менеджера продаж: отслеживает целевые сообщения в чатах через Telegram userbot и готовит outreach в личные сообщения. На этом этапе включается безопасный профиль draft_only с лимитами и дедупликацией.',
  ai_logist: 'Шаблон находится в разработке.',
  content_factory: 'Шаблон находится в разработке.',
};

const TEMPLATE_TYPE_SELECT_OPTIONS = [
  { value: 'qa', label: 'Консультант (Вопрос-Ответ)' },
  {
    value: 'crm_admin',
    label: (
      <span className="select-option-label-with-badge">
        Администратор (Интеграция с CRM)
        <span className="beta-badge">BETA</span>
      </span>
    ),
  },
  {
    value: 'sales_manager',
    label: (
      <span className="select-option-label-with-badge">
        Менеджер продаж (Telegram userbot)
        <span className="beta-badge">BETA</span>
      </span>
    ),
  },
  {
    value: 'ai_logist',
    disabled: true,
    label: (
      <span className="select-option-label-with-badge">
        ИИ Логист
        <span className="beta-badge">В разработке</span>
      </span>
    ),
  },
  {
    value: 'content_factory',
    disabled: true,
    label: (
      <span className="select-option-label-with-badge">
        Контент-завод
        <span className="beta-badge">В разработке</span>
      </span>
    ),
  },
];

const CustomSelect = ({
  id,
  name,
  value,
  options,
  onChange,
  disabled = false,
  className = '',
  error = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleOutsideClick = (event) => {
      if (!selectRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const selectedOption = options.find((option) => option.value === value) || options[0];
  const buttonClassName = [
    'custom-select-trigger',
    className,
    error ? 'error' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const handleSelectOption = (nextValue) => {
    const optionToSelect = options.find((option) => option.value === nextValue);
    if (optionToSelect?.disabled) {
      return;
    }
    onChange({
      target: {
        name,
        value: nextValue,
      },
    });
    setIsOpen(false);
  };

  return (
    <div className={`custom-select ${disabled ? 'disabled' : ''}`} ref={selectRef}>
      <button
        id={id}
        type="button"
        className={buttonClassName}
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="custom-select-value">{selectedOption?.label || ''}</span>
        <span className={`custom-select-arrow ${isOpen ? 'open' : ''}`} aria-hidden="true" />
      </button>
      {isOpen && !disabled && (
        <div className="custom-select-dropdown" role="listbox" aria-labelledby={id}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`custom-select-option ${option.value === value ? 'selected' : ''} ${
                option.disabled ? 'disabled' : ''
              }`}
              onClick={() => handleSelectOption(option.value)}
              disabled={option.disabled}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

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
  const [whatsappUserbotQrDataUrl, setWhatsappUserbotQrDataUrl] = useState('');
  const [isSendingWhatsappUserbotCode, setIsSendingWhatsappUserbotCode] = useState(false);
  const [isVerifyingWhatsappUserbotCode, setIsVerifyingWhatsappUserbotCode] = useState(false);
  const [isWhatsappUserbotVerified, setIsWhatsappUserbotVerified] = useState(false);
  const [verifiedWhatsappUserbotLabel, setVerifiedWhatsappUserbotLabel] = useState('');
  const [isValidatingCrm, setIsValidatingCrm] = useState(false);
  const [crmValidationResult, setCrmValidationResult] = useState(null);
  const [crmValidationSignature, setCrmValidationSignature] = useState('');
  const whatsappUserbotLastAuthStatusRef = useRef('');

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
      template_type: 'qa',
      crm_provider: 'amocrm',
      crm_account_base_url: '',
      crm_access_token: '',
      crm_allowed_tools: 'find_contact, create_contact, find_lead, create_lead, update_lead, add_note, create_task, assign_owner',
      crm_confirmation_policy: 'confirm_risky',
      crm_fallback_mode: 'ask_clarifying_question',
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

        const selectedTemplate = values.template_type?.trim() || 'qa';
        if (
          selectedTemplate === 'sales_manager' &&
          (!isUserbotMode || isBotMode || isWhatsAppUserbotMode || isWhatsAppBusinessApiMode)
        ) {
          showError(
            'Для шаблона "Менеджер продаж" на этом этапе доступно только подключение Telegram userbot.'
          );
          return;
        }
        if (selectedTemplate === 'crm_admin' && !values.crm_account_base_url?.trim()) {
          form.setFieldError('crm_account_base_url', 'Base URL CRM обязателен');
          return;
        }
        if (selectedTemplate === 'crm_admin' && !values.crm_access_token?.trim()) {
          form.setFieldError('crm_access_token', 'Access token CRM обязателен');
          return;
        }
        if (selectedTemplate === 'crm_admin') {
          const currentSignature = buildCrmValidationSignature(
            values.crm_provider,
            values.crm_account_base_url,
            values.crm_access_token
          );
          if (!crmValidationResult?.ok || crmValidationSignature !== currentSignature) {
            showError('Перед сохранением выполните и пройдите проверку подключения CRM.');
            return;
          }
        }
        const templateConfig = selectedTemplate === 'crm_admin'
          ? {
              crm_provider: values.crm_provider?.trim() || 'amocrm',
              allowed_tools: parseAllowedTools(values.crm_allowed_tools),
              confirmation_policy: values.crm_confirmation_policy?.trim() || 'confirm_risky',
              fallback_mode: values.crm_fallback_mode?.trim() || 'ask_clarifying_question',
            }
          : selectedTemplate === 'sales_manager'
            ? SALES_DEFAULT_TEMPLATE_CONFIG
            : undefined;

        const createdAgent = await agentService.createEmpty({
          system_prompt: values.system_prompt.trim(),
          template_type: selectedTemplate,
          template_config: templateConfig,
        });
        const agentId = createdAgent?.id;
        if (!Number.isFinite(agentId)) {
          showError('Не удалось определить id агента после создания');
          return;
        }

        if (selectedTemplate === 'crm_admin') {
          await agentService.connectCrm({
            agent_id: agentId,
            provider: values.crm_provider?.trim() || 'amocrm',
            account_base_url: values.crm_account_base_url.trim(),
            access_token: values.crm_access_token.trim(),
          });
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
  const isSalesManagerTemplate = form.values.template_type === 'sales_manager';

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
    if (isSalesManagerTemplate) return;
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
    if (isSalesManagerTemplate) return;
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
    if (isSalesManagerTemplate) return;
    setUseWhatsAppUserbotChannel((prev) => {
      const next = !prev;
      if (!next) {
        setWhatsappUserbotMode('simple');
        setWhatsappUserbotAuthToken('');
        setWhatsappUserbotQrDataUrl('');
        setIsSendingWhatsappUserbotCode(false);
        setIsVerifyingWhatsappUserbotCode(false);
        setIsWhatsappUserbotVerified(false);
        setVerifiedWhatsappUserbotLabel('');
        whatsappUserbotLastAuthStatusRef.current = '';
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
      form.setFieldValue('verify_code', '');
      form.setFieldValue('password_2fa', '');
      form.setFieldError('verify_code', undefined);
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
    setWhatsappUserbotQrDataUrl('');
    setIsWhatsappUserbotVerified(false);
    setVerifiedWhatsappUserbotLabel('');
    whatsappUserbotLastAuthStatusRef.current = '';
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
      });
      setWhatsappUserbotAuthToken(response.auth_token);
      setWhatsappUserbotQrDataUrl(response.qr_data_url || '');
      setIsWhatsappUserbotVerified(false);
      setVerifiedWhatsappUserbotLabel('');
      whatsappUserbotLastAuthStatusRef.current = '';
      form.setFieldValue('whatsapp_userbot_session_string', '');
      showSuccess(
        response.hint || 'QR готов. Отсканируйте его в WhatsApp и затем нажмите «Проверить подключение».'
      );
    } catch (error) {
      showError(error.message || 'Не удалось запросить QR-код WhatsApp');
    } finally {
      setIsSendingWhatsappUserbotCode(false);
    }
  };

  const handleWhatsappUserbotVerifyCode = async () => {
    if (!whatsappUserbotAuthToken) {
      showError('Сначала запросите код подтверждения WhatsApp');
      return;
    }
    setIsVerifyingWhatsappUserbotCode(true);
    try {
      const response = await agentService.verifyWhatsAppUserbotCode({
        auth_token: whatsappUserbotAuthToken,
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

  useEffect(() => {
    if (whatsappUserbotMode !== 'simple') return undefined;
    if (!whatsappUserbotAuthToken) return undefined;
    if (isWhatsappUserbotVerified) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await agentService.whatsappUserbotAuthStatus({
          auth_token: whatsappUserbotAuthToken,
        });
        if (cancelled) return;
        if (response?.qr_data_url) {
          setWhatsappUserbotQrDataUrl(response.qr_data_url);
        }
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = whatsappUserbotLastAuthStatusRef.current;
        if (nextStatus && nextStatus !== prevStatus) {
          if (nextStatus === 'paired') {
            showSuccess('QR подтвержден в WhatsApp. Нажмите «Проверить подключение».');
          } else if (nextStatus === 'failed') {
            showError(response?.last_error || 'Сессия WhatsApp завершилась с ошибкой. Запросите новый QR.');
          }
        }
        whatsappUserbotLastAuthStatusRef.current = nextStatus;
      } catch {
        // Ignore intermittent polling failures; user can still verify manually.
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [
    whatsappUserbotMode,
    whatsappUserbotAuthToken,
    isWhatsappUserbotVerified,
    showError,
    showSuccess,
  ]);

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

  const toggleCrmTool = (toolName) => {
    const selected = parseAllowedTools(form.values.crm_allowed_tools);
    const hasTool = selected.includes(toolName);
    const next = hasTool ? selected.filter((item) => item !== toolName) : [...selected, toolName];
    form.setFieldValue('crm_allowed_tools', next.join(', '));
  };

  const handleValidateCrm = async () => {
    if (!form.values.crm_account_base_url?.trim()) {
      form.setFieldError('crm_account_base_url', 'Base URL CRM обязателен');
      return;
    }
    if (!form.values.crm_access_token?.trim()) {
      form.setFieldError('crm_access_token', 'Access token CRM обязателен');
      return;
    }
    setIsValidatingCrm(true);
    try {
      const response = await agentService.validateCrm({
        provider: form.values.crm_provider?.trim() || 'amocrm',
        account_base_url: form.values.crm_account_base_url.trim(),
        access_token: form.values.crm_access_token.trim(),
      });
      const signature = buildCrmValidationSignature(
        form.values.crm_provider,
        form.values.crm_account_base_url,
        form.values.crm_access_token
      );
      setCrmValidationSignature(signature);
      setCrmValidationResult(response);
      showSuccess('Подключение CRM успешно проверено');
    } catch (error) {
      setCrmValidationResult({ ok: false, error: error.message || 'Ошибка валидации CRM' });
      showError(error.message || 'Не удалось проверить подключение CRM');
    } finally {
      setIsValidatingCrm(false);
    }
  };

  useEffect(() => {
    if (form.values.template_type !== 'crm_admin') {
      setCrmValidationResult(null);
      setCrmValidationSignature('');
      return;
    }
    const currentSignature = buildCrmValidationSignature(
      form.values.crm_provider,
      form.values.crm_account_base_url,
      form.values.crm_access_token
    );
    if (crmValidationSignature && crmValidationSignature !== currentSignature) {
      setCrmValidationResult(null);
    }
  }, [
    form.values.template_type,
    form.values.crm_provider,
    form.values.crm_account_base_url,
    form.values.crm_access_token,
    crmValidationSignature,
  ]);

  useEffect(() => {
    if (!isSalesManagerTemplate) return;
    setUseUserbotChannel(true);
    if (useBotChannel) {
      setUseBotChannel(false);
      form.setFieldValue('bot_token', '');
      form.setFieldError('bot_token', undefined);
    }
    if (useWhatsAppUserbotChannel) {
      setUseWhatsAppUserbotChannel(false);
      setWhatsappUserbotMode('simple');
      setWhatsappUserbotAuthToken('');
      setWhatsappUserbotQrDataUrl('');
      setIsSendingWhatsappUserbotCode(false);
      setIsVerifyingWhatsappUserbotCode(false);
      setIsWhatsappUserbotVerified(false);
      setVerifiedWhatsappUserbotLabel('');
      whatsappUserbotLastAuthStatusRef.current = '';
      form.setFieldValue('whatsapp_userbot_phone_number', '');
      form.setFieldValue('whatsapp_userbot_session_string', '');
      form.setFieldValue('whatsapp_userbot_client_label', '');
      form.setFieldError('whatsapp_userbot_phone_number', undefined);
      form.setFieldError('whatsapp_userbot_session_string', undefined);
    }
    if (useWhatsAppBusinessApiChannel) {
      setUseWhatsAppBusinessApiChannel(false);
      form.setFieldValue('whatsapp_phone_number_id', '');
      form.setFieldValue('whatsapp_access_token', '');
      form.setFieldValue('whatsapp_business_account_id', '');
      form.setFieldValue('whatsapp_verify_token', '');
      form.setFieldError('whatsapp_phone_number_id', undefined);
      form.setFieldError('whatsapp_access_token', undefined);
    }
  }, [
    form,
    isSalesManagerTemplate,
    useBotChannel,
    useWhatsAppBusinessApiChannel,
    useWhatsAppUserbotChannel,
  ]);

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
            <h3 className="agent-form-section-title">Подключение</h3>
            <div className="form-group">
              <label htmlFor="template_type">Шаблон агента:</label>
              <CustomSelect
                id="template_type"
                name="template_type"
                className="input-main"
                value={form.values.template_type}
                onChange={form.handleChange}
                options={TEMPLATE_TYPE_SELECT_OPTIONS}
                disabled={form.isSubmitting}
              />
              <p className="help-text">
                {TEMPLATE_TYPE_HELP[form.values.template_type] || TEMPLATE_TYPE_HELP.qa}
              </p>
            </div>

            {form.values.template_type === 'crm_admin' && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Конфигурация CRM шаблона</h3>
                <label htmlFor="crm_provider">CRM провайдер:</label>
                <CustomSelect
                  id="crm_provider"
                  name="crm_provider"
                  className="input-main"
                  value={form.values.crm_provider}
                  onChange={form.handleChange}
                  options={[
                    { value: 'amocrm', label: 'amoCRM' },
                    { value: 'bitrix24', label: 'Bitrix24' },
                  ]}
                  disabled={form.isSubmitting}
                />

                <label htmlFor="crm_account_base_url" className="mt-input">
                  Base URL аккаунта CRM:
                </label>
                <input
                  id="crm_account_base_url"
                  type="text"
                  name="crm_account_base_url"
                  className={`input-main ${form.errors.crm_account_base_url ? 'error' : ''}`}
                  value={form.values.crm_account_base_url}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                  placeholder={
                    form.values.crm_provider === 'bitrix24'
                      ? 'https://your-portal.bitrix24.ru/rest'
                      : 'https://example.amocrm.ru'
                  }
                />
                {form.errors.crm_account_base_url && (
                  <span className="error-message">{form.errors.crm_account_base_url}</span>
                )}

                <label htmlFor="crm_access_token" className="mt-input">
                  Access token CRM:
                </label>
                <input
                  id="crm_access_token"
                  type="password"
                  name="crm_access_token"
                  className={`input-main ${form.errors.crm_access_token ? 'error' : ''}`}
                  value={form.values.crm_access_token}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                  placeholder="Вставьте OAuth access token"
                />
                {form.errors.crm_access_token && (
                  <span className="error-message">{form.errors.crm_access_token}</span>
                )}

                <div className="channel-actions-row">
                  <button
                    type="button"
                    className="btn btn-black"
                    onClick={handleValidateCrm}
                    disabled={form.isSubmitting || isValidatingCrm}
                  >
                    {isValidatingCrm ? 'Проверка...' : 'Проверить подключение CRM'}
                  </button>
                </div>

                {crmValidationResult?.ok ? (
                  <p className="help-text userbot-success">
                    CRM проверена: {crmValidationResult.provider} ({crmValidationResult.external_id || 'ok'})
                  </p>
                ) : null}
                {crmValidationResult && crmValidationResult.ok === false ? (
                  <p className="error-message">
                    {crmValidationResult.error || 'Проверка CRM завершилась с ошибкой'}
                  </p>
                ) : null}

                <label htmlFor="crm_allowed_tools" className="mt-input">
                  Разрешенные действия CRM:
                </label>
                <div className="connection-type-grid connection-type-grid--channels">
                  {CRM_TOOL_OPTIONS.map((tool) => {
                    const selectedTools = parseAllowedTools(form.values.crm_allowed_tools);
                    const active = selectedTools.includes(tool.value);
                    return (
                      <button
                        key={tool.value}
                        type="button"
                        className={`connection-type-card ${active ? 'active' : ''}`}
                        onClick={() => toggleCrmTool(tool.value)}
                        disabled={form.isSubmitting}
                      >
                        {tool.label}
                      </button>
                    );
                  })}
                </div>
                <p className="help-text">
                  Выбрано: {parseAllowedTools(form.values.crm_allowed_tools).join(', ') || 'ничего'}
                </p>

                <label htmlFor="crm_confirmation_policy" className="mt-input">
                  Политика подтверждения:
                </label>
                <CustomSelect
                  id="crm_confirmation_policy"
                  name="crm_confirmation_policy"
                  className="input-main"
                  value={form.values.crm_confirmation_policy}
                  onChange={form.handleChange}
                  options={[
                    { value: 'confirm_risky', label: 'Подтверждать рискованные действия' },
                    { value: 'always_confirm', label: 'Подтверждать каждое действие' },
                    { value: 'never_confirm', label: 'Без подтверждений' },
                  ]}
                  disabled={form.isSubmitting}
                />

                <label htmlFor="crm_fallback_mode" className="mt-input">
                  Режим fallback:
                </label>
                <CustomSelect
                  id="crm_fallback_mode"
                  name="crm_fallback_mode"
                  className="input-main"
                  value={form.values.crm_fallback_mode}
                  onChange={form.handleChange}
                  options={[
                    { value: 'ask_clarifying_question', label: 'Задавать уточняющие вопросы' },
                    { value: 'text_only', label: 'Только текстовый ответ' },
                  ]}
                  disabled={form.isSubmitting}
                />
              </div>
            )}

            {form.values.template_type === 'sales_manager' && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Конфигурация Sales Manager</h3>
                <div className="help-text">
                  <strong>⚠️ Важно:</strong> На этом этапе sales_manager настроен с безопасным профилем:
                  <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
                    <li>Режим: <strong>draft_only</strong> (все сообщения требуют подтверждения)</li>
                    <li>Модель классификации: <strong>DeepSeek-chat</strong></li>
                    <li>Минимальная уверенность: <strong>0.75</strong></li>
                    <li>Лимиты: <strong>3/минуту, 25/час, 120/день</strong></li>
                    <li>Cooldown между контактами: <strong>14 дней</strong></li>
                  </ul>
                </div>
                <p className="help-text">
                  Агент будет сканировать сообщения в доступных ему Telegram чатах и готовить 
                  персонализированные предложения в личные сообщения. Дополнительная конфигурация 
                  лимитов и правил доступна после создания агента.
                </p>
              </div>
            )}

            <div className="form-group">
              <label>Тип подключения:</label>
              <div className="connection-type-grid connection-type-grid--channels">
                <button
                  type="button"
                  className={`connection-type-card ${useBotChannel ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                  onClick={toggleBotChannel}
                  disabled={form.isSubmitting || isSalesManagerTemplate}
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
                  className={`connection-type-card ${useWhatsAppUserbotChannel ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                  onClick={toggleWhatsAppUserbotChannel}
                  disabled={form.isSubmitting || isSalesManagerTemplate}
                >
                  WhatsApp юзербот
                </button>
                <button
                  type="button"
                  className={`connection-type-card connection-type-card--with-beta ${useWhatsAppBusinessApiChannel ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                  onClick={toggleWhatsAppBusinessApiChannel}
                  disabled={form.isSubmitting || isSalesManagerTemplate}
                >
                  <span className="connection-type-card-label connection-type-card-label--stacked-wa-api">
                    <span className="connection-type-card-label__row">WhatsApp Business</span>
                    <span className="connection-type-card-label__row connection-type-card-label__row--api-beta">
                      API
                      <span className="beta-badge">BETA</span>
                    </span>
                  </span>
                </button>
              </div>
              {isSalesManagerTemplate ? (
                <p className="help-text">
                  Для шаблона "Менеджер продаж" доступно только подключение Telegram userbot.
                </p>
              ) : null}
            </div>

            {useBotChannel && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Telegram бот</h3>
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
                <h3 className="agent-form-channel-title">Telegram юзербот</h3>
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

                {userbotAuthToken ? (
                  <>
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
                  </>
                ) : null}

                {isUserbotVerified && (
                  <p className="help-text userbot-success">
                    Userbot подтвержден: {verifiedUserbotLabel || 'успешно'}
                  </p>
                )}
              </div>
            )}

            {useWhatsAppBusinessApiChannel && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">WhatsApp Business API</h3>
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
                <h3 className="agent-form-channel-title">WhatsApp userbot</h3>
                <label>Режим подключения WhatsApp userbot:</label>
                <div className="connection-type-grid connection-type-grid--pair">
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

                <label htmlFor="whatsapp_userbot_phone_number" className="mt-input">
                  Номер WhatsApp userbot:
                </label>
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
                    <div className="channel-actions-row">
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleWhatsappUserbotRequestCode}
                        disabled={form.isSubmitting || isSendingWhatsappUserbotCode}
                      >
                        {isSendingWhatsappUserbotCode ? 'Отправка...' : 'Запросить QR-код'}
                      </button>
                    </div>

                    {whatsappUserbotQrDataUrl ? (
                      <div className="wa-qr-card">
                        <p className="wa-qr-title"><strong>QR для подключения</strong></p>
                        <img
                          src={whatsappUserbotQrDataUrl}
                          alt="WhatsApp QR"
                          className="wa-qr-image"
                        />
                        <p className="wa-qr-hint">
                          Откройте WhatsApp → Настройки → Связанные устройства → Привязать устройство и отсканируйте QR.
                        </p>
                      </div>
                    ) : null}

                    {whatsappUserbotAuthToken ? (
                      <div className="channel-actions-row">
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleWhatsappUserbotVerifyCode}
                          disabled={form.isSubmitting || isVerifyingWhatsappUserbotCode}
                        >
                          {isVerifyingWhatsappUserbotCode ? 'Проверка...' : 'Проверить подключение'}
                        </button>
                      </div>
                    ) : null}

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