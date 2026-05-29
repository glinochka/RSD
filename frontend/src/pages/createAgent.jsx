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
import { TELEPHONY_PROVIDER, copyTextToClipboard } from '../utils/telephony';
import { validateFile } from '../utils/validation';
import { NAVIGATION_ROUTES } from '../config/constants';
import pricingService from '../services/pricingService';
import { formatMaintenancePrice } from '../utils/agentTemplatePricing';
import DemoBadge, { TitleWithDemoBadge } from '../components/DemoBadge';
import UserbotSessionFileUpload from '../components/UserbotSessionFileUpload';
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

const CRM_DOMAIN_OPTIONS_FALLBACK = [
  { value: 'beauty_salon', label: 'Салон красоты' },
  { value: 'dental_clinic', label: 'Стоматологическая клиника' },
];

const CRM_DOMAIN_PLACEHOLDERS = {
  beauty_salon: {
    specialization: 'Парикмахер',
    serviceTitle: 'Стрижка',
  },
  dental_clinic: {
    specialization: 'Стоматолог-терапевт',
    serviceTitle: 'Профессиональная чистка зубов',
  },
  custom: {
    specialization: 'Специалист',
    serviceTitle: 'Консультация',
  },
};

const getCrmDomainPlaceholders = (domainConfig) => {
  const domainKey = String(domainConfig?.key || domainConfig?.value || 'beauty_salon').trim();
  return CRM_DOMAIN_PLACEHOLDERS[domainKey] || CRM_DOMAIN_PLACEHOLDERS.custom;
};

const CRM_MODE_OPTIONS = [
  { value: 'disabled', label: 'Работать без CRM' },
  { value: 'optional', label: 'Подключить CRM (опционально сейчас / позже)' },
];

const CRM_CONNECT_TIMING_OPTIONS = [
  { value: 'now', label: 'Подключить CRM сейчас' },
  { value: 'later', label: 'Подключить CRM позже' },
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

const normalizeChannelConnectError = (error) => {
  const rawMessage = String(error?.message || '').trim();
  const lower = rawMessage.toLowerCase();
  if (
    lower.includes('telegram') &&
    (lower.includes('404') ||
      lower.includes('not found') ||
      lower.includes('не распознал токен'))
  ) {
    return 'Telegram не распознал токен бота. Проверьте, что вы вставили полный токен из BotFather без лишних пробелов и символов.';
  }
  if (
    lower.includes('telegram') &&
    (lower.includes('401') || lower.includes('unauthorized') || lower.includes('некорректный api ключ'))
  ) {
    return 'Некорректный API ключ Telegram бота. Проверьте токен в BotFather и попробуйте снова.';
  }
  return rawMessage || 'Не удалось подключить выбранный канал';
};

let _staffLocalIdCounter = 0;
const newStaffId = () => `local-${++_staffLocalIdCounter}`;

let _serviceLocalIdCounter = 0;
const newServiceLocalId = () => `svc-${++_serviceLocalIdCounter}`;

const rubToMinor = (raw) => {
  const normalized = String(raw ?? '').replace(',', '.').trim();
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.max(0, Math.round(value * 100));
};

const buildAdminDomainPromptAppendix = (domainConfig, staffList, serviceList) => {
  const domainType = domainConfig?.key || 'beauty_salon';
  const staffRole = domainConfig?.staff_role_default || 'master';
  const staffNames = staffList.map((m) => `${m.firstName} ${m.lastName}`.trim()).filter(Boolean);
  const serviceNames = serviceList.map((s) => s.title).filter(Boolean);
  return [
    '---',
    'Admin domain profile:',
    `domain_type: ${domainType}`,
    `staff_role: ${staffRole}`,
    `staff: ${staffNames.join(', ') || '-'}`,
    `services: ${serviceNames.join(', ') || '-'}`,
  ].join('\n');
};

const StaffCard = ({ staff, onChange, onRemove, disabled, roleLabel, specializationPlaceholder }) => (
  <div className="onboarding-card onboarding-card--staff">
    <button
      type="button"
      className="onboarding-card__remove"
      onClick={onRemove}
      disabled={disabled}
      aria-label="Удалить"
    >
      ×
    </button>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Имя</label>
      <input
        type="text"
        className="onboarding-card__input"
        value={staff.firstName}
        onChange={(e) => onChange({ ...staff, firstName: e.target.value })}
        placeholder="Анна"
        disabled={disabled}
        maxLength={64}
      />
    </div>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Фамилия</label>
      <input
        type="text"
        className="onboarding-card__input"
        value={staff.lastName}
        onChange={(e) => onChange({ ...staff, lastName: e.target.value })}
        placeholder="Петрова"
        disabled={disabled}
        maxLength={64}
      />
    </div>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Специальность</label>
      <input
        type="text"
        className="onboarding-card__input"
        value={staff.specialization}
        onChange={(e) => onChange({ ...staff, specialization: e.target.value })}
        placeholder={specializationPlaceholder || (roleLabel === 'master' ? 'Парикмахер' : 'Терапевт')}
        disabled={disabled}
        maxLength={64}
      />
    </div>
  </div>
);

const ServiceStaffSelect = ({ values = [], onChange, staffList, disabled }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handler = (e) => {
      if (!ref.current?.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  const selectedIds = Array.isArray(values) ? values : [];
  const selectedItems = staffList.filter((s) => selectedIds.includes(s.localId));
  const label = selectedItems.length
    ? selectedItems
      .map((s) => `${s.firstName} ${s.lastName}`.trim() || 'Без имени')
      .join(', ')
    : 'Не выбраны';

  return (
    <div className={`custom-select onboarding-card__select ${disabled ? 'disabled' : ''}`} ref={ref}>
      <button
        type="button"
        className="custom-select-trigger onboarding-card__select-trigger"
        onClick={() => setIsOpen((p) => !p)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="custom-select-value">{label}</span>
        <span className={`custom-select-arrow ${isOpen ? 'open' : ''}`} aria-hidden="true" />
      </button>
      {isOpen && !disabled && (
        <div className="custom-select-dropdown" role="listbox">
          <button
            type="button"
            className={`custom-select-option ${selectedIds.length === 0 ? 'selected' : ''}`}
            onClick={() => onChange([])}
          >
            Не выбраны
          </button>
          {staffList.map((s) => (
            <button
              key={s.localId}
              type="button"
              className={`custom-select-option ${selectedIds.includes(s.localId) ? 'selected' : ''}`}
              onClick={() => {
                const isSelected = selectedIds.includes(s.localId);
                const next = isSelected
                  ? selectedIds.filter((id) => id !== s.localId)
                  : [...selectedIds, s.localId];
                onChange(next);
              }}
            >
              {`${s.firstName} ${s.lastName}`.trim() || 'Без имени'}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const ServiceCard = ({ service, onChange, onRemove, staffList, disabled, titlePlaceholder }) => (
  <div className="onboarding-card onboarding-card--service">
    <button
      type="button"
      className="onboarding-card__remove"
      onClick={onRemove}
      disabled={disabled}
      aria-label="Удалить"
    >
      ×
    </button>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Название</label>
      <input
        type="text"
        className="onboarding-card__input"
        value={service.title}
        onChange={(e) => onChange({ ...service, title: e.target.value })}
        placeholder={titlePlaceholder || 'Услуга'}
        disabled={disabled}
        maxLength={128}
      />
    </div>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Цена (руб)</label>
      <input
        type="number"
        min="0"
        className="onboarding-card__input"
        value={service.price}
        onChange={(e) => onChange({ ...service, price: e.target.value })}
        placeholder="1500"
        disabled={disabled}
      />
    </div>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Длительность (мин)</label>
      <input
        type="number"
        min="1"
        className="onboarding-card__input"
        value={service.duration}
        onChange={(e) => onChange({ ...service, duration: e.target.value })}
        placeholder="60"
        disabled={disabled}
      />
    </div>
    <div className="onboarding-card__field">
      <label className="onboarding-card__label">Мастера/врачи</label>
      <ServiceStaffSelect
        values={service.staffLocalIds}
        onChange={(vals) => onChange({ ...service, staffLocalIds: vals })}
        staffList={staffList}
        disabled={disabled}
      />
    </div>
  </div>
);

const CardCarousel = ({ children, addCard }) => (
  <div className="onboarding-carousel">
    <div className="onboarding-carousel__track">
      <button type="button" className="onboarding-card onboarding-card--add" onClick={addCard}>
        <span className="onboarding-card__plus">+</span>
        <span className="onboarding-card__add-label">Добавить</span>
      </button>
      {children}
    </div>
  </div>
);

const SALES_DEFAULT_TEMPLATE_CONFIG = {
  mode: 'auto',
  qualification_model: 'deepseek-chat',
  generation_model: 'deepseek-chat',
  min_confidence: 0.75,
  sales_product_name: '',
  sales_offer_type: '',
  sales_usp: '',
  workflow_completion_mode: 'auto_finish_on_signal',
  lead_score_scale: 100,
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
  confirmation_policy: 'never_confirm',
  allowed_tools: ['schedule_dm', 'skip_lead', 'record_lead_signal', 'create_crm_lead', 'mark_contacted'],
};

const TEMPLATE_TYPE_HELP = {
  qa: 'Бесплатный пробный шаблон: ответы по базе знаний (RAG) для поддержки и консультаций. Токены LLM включены.',
  crm_admin:
    'ИИ Администратор: запись, расписание, CRM/ERP. 990 ₽/мес, первые 3 дня после создания — бесплатно.',
  sales_manager:
    'ИИ МОП в мессенджерах: квалификация и диалог по стадиям. 1 990 ₽/мес, первые 3 дня — бесплатно.',
  ai_logist: 'Шаблон находится в разработке.',
  content_factory: 'Контент‑завод в разработке — создание временно недоступно.',
  ai_manager: 'ИИ менеджер в разработке — телефония и входящие звонки скоро на платформе.',
};

const TEMPLATE_TYPE_SELECT_OPTIONS = [
  { value: 'qa', label: 'ИИ консультант (бесплатно)' },
  { value: 'crm_admin', label: 'ИИ Администратор (990 ₽/мес)' },
  { value: 'sales_manager', label: 'ИИ МОП (1 990 ₽/мес)' },
  {
    value: 'content_factory',
    disabled: true,
    label: (
      <span className="select-option-label-with-badge">
        Контент‑завод
        <span className="beta-badge">В разработке</span>
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
    value: 'ai_manager',
    disabled: true,
    label: (
      <span className="select-option-label-with-badge">
        ИИ менеджер
        <DemoBadge />
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

const FeatureToggle = ({ checked, onChange, disabled, title, accessibilityTitle, description, helpText }) => {
  const titleForAria = accessibilityTitle || (typeof title === 'string' ? title : '');
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const toggleRef = useRef(null);

  useEffect(() => {
    if (!isHelpOpen) return undefined;

    const handlePointerDown = (event) => {
      if (!toggleRef.current) return;
      if (!toggleRef.current.contains(event.target)) {
        setIsHelpOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsHelpOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown, { passive: true });
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isHelpOpen]);

  return (
    <div
      ref={toggleRef}
      className={`feature-toggle ${checked ? 'feature-toggle--on' : ''} ${isHelpOpen ? 'feature-toggle--help-open' : ''}`}
    >
      <button
        type="button"
        className="feature-toggle__main"
        onClick={() => {
          onChange(!checked);
          setIsHelpOpen(false);
        }}
        disabled={disabled}
        aria-pressed={checked}
        title={titleForAria || undefined}
      >
        <span className="feature-toggle__content">
          <span className="feature-toggle__title">{title}</span>
          {description ? <span className="feature-toggle__description">{description}</span> : null}
        </span>
        <span className="feature-toggle__switch" aria-hidden="true">
          <span className="feature-toggle__thumb" />
        </span>
      </button>
      <button
        type="button"
        className="feature-toggle__help"
        aria-label={titleForAria ? `Справка: ${titleForAria}` : 'Справка'}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setIsHelpOpen((prev) => !prev);
        }}
      >
        ?
      </button>
      <div className="feature-toggle__tooltip" role="note">
        {helpText}
      </div>
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
  const [templatePricingCatalog, setTemplatePricingCatalog] = useState([]);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [useBotChannel, setUseBotChannel] = useState(true);
  const [useMaxBotChannel, setUseMaxBotChannel] = useState(false);
  const [useUserbotChannel, setUseUserbotChannel] = useState(false);
  const [useMaxUserbotChannel, setUseMaxUserbotChannel] = useState(false);
  const [useWhatsAppUserbotChannel, setUseWhatsAppUserbotChannel] = useState(false);
  const [useWhatsAppBusinessApiChannel, setUseWhatsAppBusinessApiChannel] = useState(false);
  const [useTelephonyChannel, setUseTelephonyChannel] = useState(false);
  const [telephonyPlatform, setTelephonyPlatform] = useState(null);
  const [telephonyValidateStatus, setTelephonyValidateStatus] = useState('');
  const [telephonyWebhookUrl, setTelephonyWebhookUrl] = useState('');
  const [isValidatingTelephony, setIsValidatingTelephony] = useState(false);
  const [userbotAuthMode, setUserbotAuthMode] = useState('qr');
  const [userbotResolvedApiId, setUserbotResolvedApiId] = useState(null);
  const [userbotResolvedApiHash, setUserbotResolvedApiHash] = useState('');
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [userbotQrAuthToken, setUserbotQrAuthToken] = useState('');
  const [userbotQrDataUrl, setUserbotQrDataUrl] = useState('');
  const [userbotQrNeeds2fa, setUserbotQrNeeds2fa] = useState(false);
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [isStartingUserbotQr, setIsStartingUserbotQr] = useState(false);
  const [isVerifyingUserbotQr2fa, setIsVerifyingUserbotQr2fa] = useState(false);
  const [isImportingUserbotSession, setIsImportingUserbotSession] = useState(false);
  const [isUserbotVerified, setIsUserbotVerified] = useState(false);
  const [verifiedUserbotLabel, setVerifiedUserbotLabel] = useState('');
  const userbotLastQrStatusRef = useRef('');
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

  const [staffList, setStaffList] = useState([]);
  const [serviceList, setServiceList] = useState([]);
  const [domainRegistry, setDomainRegistry] = useState(CRM_DOMAIN_OPTIONS_FALLBACK);
  const [customStaffRole, setCustomStaffRole] = useState('');
  const [customDomainInstruction, setCustomDomainInstruction] = useState('');
  const [resourcesEnabled, setResourcesEnabled] = useState(false);

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
      phone_number: '',
      verify_code: '',
      password_2fa: '',
      session_string: '',
      max_bot_token: '',
      max_token: '',
      whatsapp_userbot_phone_number: '',
      whatsapp_userbot_session_string: '',
      whatsapp_userbot_client_label: '',
      whatsapp_phone_number_id: '',
      whatsapp_access_token: '',
      whatsapp_business_account_id: '',
      whatsapp_verify_token: '',
      telephony_routing_extension: '',
      telephony_voice_id: 'default',
      telephony_language: 'ru-RU',
      template_type: 'qa',
      crm_domain_type: 'beauty_salon',
      crm_mode: 'disabled',
      crm_connect_timing: 'later',
      crm_provider: 'amocrm',
      crm_account_base_url: '',
      crm_access_token: '',
      crm_allowed_tools: 'find_contact, create_contact, find_lead, create_lead, update_lead, add_note, create_task, assign_owner',
      crm_confirmation_policy: 'confirm_risky',
      crm_fallback_mode: 'ask_clarifying_question',
      waitlist_enabled: true,
      reminder_enabled: true,
      reminder_offsets_hours: '24,2',
      manual_confirmation_enabled: false,
      manual_confirmation_price_minor: '15000',
      manual_confirmation_duration_minutes: '120',
      sales_product_name: '',
      sales_offer_type: '',
      sales_usp: '',
      workflow_completion_mode: 'auto_finish_on_signal',
      lead_score_scale: 100,
      content_company_name: '',
      content_company_activity: '',
      content_brand_tone: '',
      content_language: 'ru',
      system_prompt: '',
    },
    async (values) => {
      if (!isAuthenticated) {
        setShowAuthModal(true);
        return;
      }

      let createdAgentId = null;
      let hasConnectedAtLeastOneChannel = false;
      try {
        if (isEditMode) {
          showError('Редактирование агента сейчас недоступно на этой странице');
          return;
        }

        const isBotMode = useBotChannel;
        const isMaxBotMode = useMaxBotChannel;
        const isUserbotMode = useUserbotChannel;
        const isMaxUserbotMode = useMaxUserbotChannel;
        const isWhatsAppUserbotMode = useWhatsAppUserbotChannel;
        const isWhatsAppBusinessApiMode = useWhatsAppBusinessApiChannel;
        const isTelephonyMode = useTelephonyChannel;

        if (
          !skipChannelSelection &&
          !isBotMode &&
          !isMaxBotMode &&
          !isUserbotMode &&
          !isMaxUserbotMode &&
          !isWhatsAppUserbotMode &&
          !isWhatsAppBusinessApiMode &&
          !isTelephonyMode
        ) {
          const message = 'Добавьте хотя бы 1 канал подключения перед созданием агента.';
          showError(message);
          window.alert(message);
          return;
        }

        if (!skipChannelSelection && isBotMode && !values.bot_token?.trim()) {
          form.setFieldError('bot_token', 'API ключ Telegram бота обязателен');
          return;
        }
        if (!skipChannelSelection && isMaxBotMode && !values.max_bot_token?.trim()) {
          form.setFieldError('max_bot_token', 'MAX bot token обязателен');
          return;
        }
        if (!skipChannelSelection && isUserbotMode && userbotAuthMode === 'phone' && !values.phone_number?.trim()) {
          form.setFieldError('phone_number', 'Номер телефона обязателен');
          return;
        }
        if (!skipChannelSelection && isUserbotMode && (!values.session_string?.trim() || !isUserbotVerified)) {
          const errMsg =
            userbotAuthMode === 'file'
              ? 'Сначала импортируйте файл сессии'
              : userbotAuthMode === 'qr'
                ? 'Сначала завершите вход по QR (и 2FA при необходимости)'
                : 'Сначала подтвердите код и сохраните userbot-сессию';
          form.setFieldError('session_string', errMsg);
          return;
        }
        if (
          !skipChannelSelection
          && isUserbotMode
          && (!userbotResolvedApiId || !userbotResolvedApiHash)
        ) {
          form.setFieldError('session_string', 'Сессия userbot неполная. Повторите вход.');
          return;
        }
        if (!skipChannelSelection && isMaxUserbotMode && !values.max_token?.trim()) {
          form.setFieldError('max_token', 'MAX token обязателен');
          return;
        }
        if (!skipChannelSelection && isWhatsAppUserbotMode && !values.whatsapp_userbot_phone_number?.trim()) {
          form.setFieldError('whatsapp_userbot_phone_number', 'Номер WhatsApp обязателен');
          return;
        }
        if (!skipChannelSelection && isWhatsAppUserbotMode) {
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
        if (!skipChannelSelection && isWhatsAppBusinessApiMode && !values.whatsapp_phone_number_id?.trim()) {
          form.setFieldError('whatsapp_phone_number_id', 'Phone Number ID обязателен');
          return;
        }
        if (!skipChannelSelection && isWhatsAppBusinessApiMode && !values.whatsapp_access_token?.trim()) {
          form.setFieldError('whatsapp_access_token', 'Access Token обязателен');
          return;
        }
        if (!skipChannelSelection && isTelephonyMode) {
          const ext = String(values.telephony_routing_extension || '').trim();
          if (!/^\d{4}$/.test(ext)) {
            form.setFieldError('telephony_routing_extension', 'Укажите добавочный из 4 цифр');
            return;
          }
          if (telephonyPlatform && !telephonyPlatform.platform_ready) {
            showError('Телефония платформы не настроена на сервере (.env)');
            return;
          }
        }

        const selectedTemplate = values.template_type?.trim() || 'qa';
        const crmMode = values.crm_mode?.trim() || 'disabled';
        const crmConnectTiming = values.crm_connect_timing?.trim() || 'later';
        const shouldUseCrm = selectedTemplate === 'crm_admin' && crmMode !== 'disabled';
        const shouldConnectCrmNow = shouldUseCrm && crmConnectTiming === 'now';
        if (selectedTemplate === 'sales_manager' && !values.sales_product_name?.trim()) {
          form.setFieldError('sales_product_name', 'Укажите продукт, который продает агент');
          return;
        }
        if (selectedTemplate === 'sales_manager' && !values.sales_offer_type?.trim()) {
          form.setFieldError('sales_offer_type', 'Укажите тип предложения (например, SaaS, курсы, услуги)');
          return;
        }
        if (selectedTemplate === 'content_factory' && !values.content_company_name?.trim()) {
          form.setFieldError('content_company_name', 'Укажите название компании');
          return;
        }
        if (selectedTemplate === 'content_factory' && !values.content_company_activity?.trim()) {
          form.setFieldError('content_company_activity', 'Укажите деятельность компании');
          return;
        }
        if (shouldConnectCrmNow && !values.crm_account_base_url?.trim()) {
          form.setFieldError('crm_account_base_url', 'Base URL CRM обязателен для подключения сейчас');
          return;
        }
        if (shouldConnectCrmNow && !values.crm_access_token?.trim()) {
          form.setFieldError('crm_access_token', 'Access token CRM обязателен для подключения сейчас');
          return;
        }
        if (shouldConnectCrmNow) {
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
        const _selectedDomainType = values.crm_domain_type?.trim() || 'beauty_salon';
        const _selectedDomainCfg = (Array.isArray(domainRegistry) ? domainRegistry : []).find(
          (d) => (d.key || d.value) === _selectedDomainType
        );
        const templateConfig = selectedTemplate === 'crm_admin'
          ? {
              domain_type: _selectedDomainType,
              crm_mode: crmMode === 'optional' ? 'optional' : 'disabled',
              booking_backend:
                crmMode === 'disabled'
                  ? 'local'
                  : crmConnectTiming === 'now'
                    ? 'crm'
                    : 'auto',
              crm_provider: values.crm_provider?.trim() || 'amocrm',
              allowed_tools: parseAllowedTools(values.crm_allowed_tools),
              allowed_booking_tools: [
                'check_availability',
                'find_next_available',
                'create_appointment',
                'reschedule_appointment',
                'cancel_appointment',
                'list_staff',
                'list_services',
                'list_appointments',
              ],
              confirmation_policy: values.crm_confirmation_policy?.trim() || 'confirm_risky',
              fallback_mode: values.crm_fallback_mode?.trim() || 'ask_clarifying_question',
              waitlist_enabled: Boolean(values.waitlist_enabled),
              reminder_enabled: Boolean(values.reminder_enabled),
              reminder_offsets_hours: String(values.reminder_offsets_hours || '')
                .split(',')
                .map((item) => Number(item.trim()))
                .filter((item) => Number.isFinite(item) && item > 0 && item <= 72),
              manual_confirmation_enabled: Boolean(values.manual_confirmation_enabled),
              manual_confirmation_price_minor: Number(values.manual_confirmation_price_minor || 0),
              manual_confirmation_duration_minutes: Number(values.manual_confirmation_duration_minutes || 120),
              appointment_confirmation_enabled: true,
              resources_enabled: _selectedDomainCfg?.resources_mode !== 'none',
              resource_linked_to_staff: _selectedDomainCfg?.resource_linked_to_staff ?? true,
              custom_staff_role: _selectedDomainType === 'custom' ? (customStaffRole.trim() || null) : null,
              custom_staff_label: null,
              custom_domain_instruction: _selectedDomainType === 'custom' ? (customDomainInstruction.trim() || null) : null,
            }
          : selectedTemplate === 'sales_manager'
            ? {
                ...SALES_DEFAULT_TEMPLATE_CONFIG,
                sales_product_name: values.sales_product_name.trim(),
                sales_offer_type: values.sales_offer_type.trim(),
                sales_usp: values.sales_usp?.trim() || '',
                workflow_completion_mode: values.workflow_completion_mode?.trim() || 'auto_finish_on_signal',
                lead_score_scale: Number(values.lead_score_scale) === 10 ? 10 : 100,
              }
            : selectedTemplate === 'content_factory'
              ? {
                  company_name: values.content_company_name.trim(),
                  company_activity: values.content_company_activity.trim(),
                  brand_tone: values.content_brand_tone?.trim() || undefined,
                  content_language: values.content_language?.trim().toLowerCase() || 'ru',
                }
            : undefined;

        const domainType = values.crm_domain_type?.trim() || 'beauty_salon';
        const activeDomainConfig = (Array.isArray(domainRegistry) ? domainRegistry : []).find(
          (d) => d.value === domainType || d.key === domainType
        ) || { key: domainType, staff_role_default: 'specialist' };

        const adminOnboardingPrompt =
          selectedTemplate === 'crm_admin'
            ? buildAdminDomainPromptAppendix(activeDomainConfig, staffList, serviceList)
            : '';
        const finalSystemPrompt = selectedTemplate === 'crm_admin'
          ? [values.system_prompt.trim(), adminOnboardingPrompt].filter(Boolean).join('\n\n')
          : values.system_prompt.trim();

        const createdAgent = await agentService.createEmpty({
          system_prompt: finalSystemPrompt,
          template_type: selectedTemplate,
          template_config: templateConfig,
        });
        const agentId = createdAgent?.id;
        if (!Number.isFinite(agentId)) {
          showError('Не удалось определить id агента после создания');
          return;
        }
        createdAgentId = agentId;

        if (shouldConnectCrmNow) {
          await agentService.connectCrm({
            agent_id: agentId,
            provider: values.crm_provider?.trim() || 'amocrm',
            account_base_url: values.crm_account_base_url.trim(),
            access_token: values.crm_access_token.trim(),
          });
        }

        if (selectedTemplate === 'crm_admin') {
          const staffRole = activeDomainConfig.staff_role_default
            || (domainType === 'custom' ? (customStaffRole.trim() || 'specialist') : 'specialist');
          const localIdToApiId = {};
          for (const member of staffList) {
            const fullName = `${member.firstName} ${member.lastName}`.trim();
            if (!fullName) continue;
            const created = await agentService.createAdminTemplateStaff({
              agent_id: agentId,
              role: staffRole,
              full_name: fullName,
              specializations: member.specialization ? [member.specialization] : [],
            });
            localIdToApiId[member.localId] = created?.id;
          }
          for (const svc of serviceList) {
            if (!svc.title?.trim()) continue;
            const selectedLocalIds = Array.isArray(svc.staffLocalIds) ? svc.staffLocalIds : [];
            const resolvedStaffIds = selectedLocalIds
              .map((localId) => localIdToApiId[localId])
              .filter((id) => Number.isFinite(id));
            const uniqueResolvedStaffIds = Array.from(new Set(resolvedStaffIds));
            const staffIdsToCreate = uniqueResolvedStaffIds.length > 0 ? uniqueResolvedStaffIds : [null];

            for (const resolvedStaffId of staffIdsToCreate) {
              await agentService.createAdminTemplateService({
                agent_id: agentId,
                target_role: staffRole,
                staff_id: resolvedStaffId,
                title: svc.title.trim(),
                duration_minutes: Number(svc.duration) || 60,
                price_minor: rubToMinor(svc.price),
              });
            }
          }
        }

        const primaryProvider = isBotMode
          ? 'telegram_bot'
          : isMaxBotMode
            ? 'max_bot'
          : isUserbotMode
            ? 'telegram_userbot'
            : isMaxUserbotMode
              ? 'max_userbot'
            : isWhatsAppUserbotMode
              ? 'whatsapp_userbot'
              : isWhatsAppBusinessApiMode
                ? 'whatsapp_business_api'
                : isTelephonyMode
                  ? TELEPHONY_PROVIDER
                  : 'telegram_bot';

        try {
          if (isBotMode) {
            await agentService.addBotChannel({
              agent_id: agentId,
              bot_token: values.bot_token.trim(),
              make_primary: primaryProvider === 'telegram_bot',
            });
            hasConnectedAtLeastOneChannel = true;
          }
          if (isMaxBotMode) {
            await agentService.addMaxBotChannel({
              agent_id: agentId,
              bot_token: values.max_bot_token.trim(),
              make_primary: primaryProvider === 'max_bot',
            });
            hasConnectedAtLeastOneChannel = true;
          }
          if (isUserbotMode) {
            await agentService.addUserbotChannel({
              agent_id: agentId,
              api_id: Number(userbotResolvedApiId),
              api_hash: userbotResolvedApiHash,
              session_string: values.session_string.trim(),
              make_primary: primaryProvider === 'telegram_userbot',
            });
            hasConnectedAtLeastOneChannel = true;
          }
          if (isMaxUserbotMode) {
            await agentService.addMaxUserbotChannel({
              agent_id: agentId,
              max_token: values.max_token.trim(),
              make_primary: primaryProvider === 'max_userbot',
            });
            hasConnectedAtLeastOneChannel = true;
          }
          if (isWhatsAppUserbotMode) {
            await agentService.addWhatsAppUserbotChannel({
              agent_id: agentId,
              phone_number: values.whatsapp_userbot_phone_number.trim(),
              session_string: values.whatsapp_userbot_session_string.trim(),
              client_label: values.whatsapp_userbot_client_label?.trim() || undefined,
              make_primary: primaryProvider === 'whatsapp_userbot',
            });
            hasConnectedAtLeastOneChannel = true;
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
            hasConnectedAtLeastOneChannel = true;
          }
          if (isTelephonyMode) {
            const telRes = await agentService.addTelephonyChannel({
              agent_id: agentId,
              routing_extension: values.telephony_routing_extension.trim(),
              voice_id: (values.telephony_voice_id || 'default').trim(),
              language: (values.telephony_language || 'ru-RU').trim(),
              make_primary: primaryProvider === TELEPHONY_PROVIDER,
            });
            if (telRes?.webhook_url) {
              setTelephonyWebhookUrl(telRes.webhook_url);
            }
            hasConnectedAtLeastOneChannel = true;
          }
        } catch (channelError) {
          if (!hasConnectedAtLeastOneChannel && Number.isFinite(agentId)) {
            try {
              await agentService.delete(agentId);
            } catch {
              // Best-effort rollback; original channel error is still returned to user.
            }
          }
          const normalizedMessage = normalizeChannelConnectError(channelError);
          throw new Error(normalizedMessage);
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
        if (Number.isFinite(createdAgentId) && !hasConnectedAtLeastOneChannel) {
          try {
            await agentService.delete(createdAgentId);
          } catch {
            // Best-effort rollback for any pre-channel or channel-stage failure.
          }
        }
        showError(error.message || 'Ошибка при сохранении агента');
      }
    },
    validationRules
  );
  const isSalesManagerTemplate = form.values.template_type === 'sales_manager';
  const isContentFactoryTemplate = form.values.template_type === 'content_factory';
  const isCrmAdminTemplate = form.values.template_type === 'crm_admin';
  const selectedTemplatePricing = templatePricingCatalog.find(
    (row) => row.code === form.values.template_type
  );

  useEffect(() => {
    let cancelled = false;
    pricingService
      .getAgentTemplates()
      .then((data) => {
        if (!cancelled) {
          setTemplatePricingCatalog(Array.isArray(data?.templates) ? data.templates : []);
        }
      })
      .catch(() => {
        if (!cancelled) setTemplatePricingCatalog([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  const isCrmConnectionEnabled = form.values.crm_mode === 'optional';

  const domainConfig = (Array.isArray(domainRegistry) ? domainRegistry : []).find(
    (d) => (d.key || d.value) === form.values.crm_domain_type
  ) || null;
  const crmDomainPlaceholders = getCrmDomainPlaceholders(domainConfig);
  const isCustomDomain = form.values.crm_domain_type === 'custom';
  const crmDomainOptions = (Array.isArray(domainRegistry) ? domainRegistry : []).map((d) => ({
    value: d.key || d.value,
    label: d.label_ru || d.label,
  }));
  const shouldShowCrmCredentials = isCrmConnectionEnabled && form.values.crm_connect_timing === 'now';
  const skipChannelSelection = isContentFactoryTemplate;

  const clearUserbotLocalState = () => {
    setUserbotAuthToken('');
    setIsUserbotVerified(false);
    setVerifiedUserbotLabel('');
    form.setFieldValue('phone_number', '');
    form.setFieldValue('verify_code', '');
    form.setFieldValue('password_2fa', '');
    form.setFieldValue('session_string', '');
    form.setFieldError('verify_code', undefined);
    form.setFieldError('session_string', undefined);
    setUserbotAuthMode('qr');
    setUserbotResolvedApiId(null);
    setUserbotResolvedApiHash('');
    setUserbotAuthToken('');
    setUserbotQrAuthToken('');
    setUserbotQrDataUrl('');
    setUserbotQrNeeds2fa(false);
    userbotLastQrStatusRef.current = '';
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

  const toggleMaxBotChannel = () => {
    setUseMaxBotChannel((prev) => {
      const next = !prev;
      if (!next) {
        form.setFieldValue('max_bot_token', '');
        form.setFieldError('max_bot_token', undefined);
      }
      return next;
    });
  };

  const toggleMaxUserbotChannel = () => {
    if (isContentFactoryTemplate) return;
    setUseMaxUserbotChannel((prev) => {
      const next = !prev;
      if (!next) {
        form.setFieldValue('max_token', '');
        form.setFieldError('max_token', undefined);
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

  const toggleTelephonyChannel = () => {
    setUseTelephonyChannel((prev) => {
      const next = !prev;
      if (!next) {
        setTelephonyValidateStatus('');
        setTelephonyWebhookUrl('');
        form.setFieldValue('telephony_routing_extension', '');
        form.setFieldValue('telephony_voice_id', 'default');
        form.setFieldValue('telephony_language', 'ru-RU');
      } else {
        agentService
          .getTelephonyPlatformConfig()
          .then(setTelephonyPlatform)
          .catch(() => setTelephonyPlatform(null));
      }
      return next;
    });
  };

  const handleValidateTelephonyOnCreate = async () => {
    const ext = form.values.telephony_routing_extension?.trim() || '';
    if (!/^\d{4}$/.test(ext)) {
      form.setFieldError('telephony_routing_extension', 'Укажите добавочный из 4 цифр');
      return;
    }
    if (telephonyPlatform && !telephonyPlatform.platform_ready) {
      showError('Телефония платформы не настроена на сервере (.env)');
      return;
    }
    const payload = { routing_extension: ext };
    setIsValidatingTelephony(true);
    setTelephonyValidateStatus('');
    try {
      const res = await agentService.validateTelephonyChannel(payload);
      setTelephonyValidateStatus(res?.message || 'Подключение проверено');
      showSuccess(res?.message || 'Voximplant: учётная запись доступна');
    } catch (error) {
      showError(error?.message || 'Ошибка проверки телефонии');
    } finally {
      setIsValidatingTelephony(false);
    }
  };

  const toggleWhatsAppUserbotChannel = () => {
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
    if (!form.values.phone_number?.trim()) {
      form.setFieldError('phone_number', 'Номер телефона обязателен');
      return;
    }

    setIsSendingCode(true);
    try {
      const response = await agentService.requestUserbotCode({
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

  const applyUserbotVerified = (response) => {
    form.setFieldValue('session_string', response?.session_string || '');
    if (response?.api_id != null) {
      setUserbotResolvedApiId(Number(response.api_id));
    }
    if (response?.api_hash) {
      setUserbotResolvedApiHash(String(response.api_hash));
    }
    setIsUserbotVerified(true);
    const label = response?.username
      ? `@${response.username}`
      : [response?.first_name, response?.last_name].filter(Boolean).join(' ')
        || response?.phone_number
        || (response?.telegram_id ? `id: ${response.telegram_id}` : 'успешно');
    setVerifiedUserbotLabel(label);
  };

  const switchUserbotAuthMode = (mode) => {
    setUserbotAuthMode(mode);
    setUserbotAuthToken('');
    setUserbotQrAuthToken('');
    setUserbotQrDataUrl('');
    setUserbotQrNeeds2fa(false);
    setUserbotResolvedApiId(null);
    setUserbotResolvedApiHash('');
    setIsUserbotVerified(false);
    setVerifiedUserbotLabel('');
    userbotLastQrStatusRef.current = '';
    form.setFieldValue('session_string', '');
    form.setFieldValue('verify_code', '');
    form.setFieldValue('password_2fa', '');
    form.setFieldError('session_string', undefined);
    form.setFieldError('verify_code', undefined);
  };

  const handleUserbotQrStart = async () => {
    setIsStartingUserbotQr(true);
    try {
      const response = await agentService.startUserbotQr({});
      setUserbotQrAuthToken(response.auth_token || '');
      setUserbotQrDataUrl(response.qr_data_url || '');
      setUserbotQrNeeds2fa(false);
      setIsUserbotVerified(false);
      setVerifiedUserbotLabel('');
      userbotLastQrStatusRef.current = '';
      form.setFieldValue('session_string', '');
      if (response.already_authorized && response.session_string) {
        applyUserbotVerified(response);
        showSuccess('Сессия Telegram уже авторизована');
      } else {
        showSuccess('Отсканируйте QR в Telegram: Настройки → Устройства → Подключить устройство');
      }
    } catch (error) {
      showError(error.message || 'Не удалось начать QR-вход Telegram');
    } finally {
      setIsStartingUserbotQr(false);
    }
  };

  const handleUserbotQrVerify2fa = async () => {
    if (!userbotQrAuthToken) {
      showError('Сначала начните QR-вход');
      return;
    }
    if (!form.values.password_2fa?.trim()) {
      form.setFieldError('password_2fa', 'Введите пароль 2FA');
      return;
    }
    setIsVerifyingUserbotQr2fa(true);
    try {
      const response = await agentService.verifyUserbotQr2fa({
        auth_token: userbotQrAuthToken,
        password: form.values.password_2fa.trim(),
      });
      applyUserbotVerified(response);
      setUserbotQrNeeds2fa(false);
      showSuccess('2FA подтверждена, userbot готов');
    } catch (error) {
      setIsUserbotVerified(false);
      showError(error.message || 'Не удалось подтвердить 2FA');
    } finally {
      setIsVerifyingUserbotQr2fa(false);
    }
  };

  const handleUserbotImportSession = async (file) => {
    if (!file) return;
    setIsImportingUserbotSession(true);
    try {
      const response = await agentService.importUserbotSession({
        session_file: file,
      });
      applyUserbotVerified(response);
      showSuccess('Сессия Telegram импортирована');
    } catch (error) {
      setIsUserbotVerified(false);
      showError(error.message || 'Не удалось импортировать сессию');
    } finally {
      setIsImportingUserbotSession(false);
    }
  };

  useEffect(() => {
    if (userbotAuthMode !== 'qr') return undefined;
    if (!userbotQrAuthToken) return undefined;
    if (isUserbotVerified) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await agentService.userbotQrStatus({
          auth_token: userbotQrAuthToken,
        });
        if (cancelled) return;
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = userbotLastQrStatusRef.current;
        if (nextStatus === 'need_2fa') {
          setUserbotQrNeeds2fa(true);
          if (prevStatus !== 'need_2fa') {
            showSuccess('QR принят. Введите пароль 2FA и нажмите «Подтвердить 2FA».');
          }
        } else if (nextStatus === 'success' && response?.session_string) {
          applyUserbotVerified(response);
          setUserbotQrNeeds2fa(false);
          if (prevStatus !== 'success') {
            showSuccess('Telegram userbot авторизован по QR');
          }
        } else if (nextStatus === 'expired' || nextStatus === 'error') {
          if (prevStatus !== nextStatus) {
            showError(response?.error || 'QR-вход завершился с ошибкой. Запросите новый QR.');
          }
        }
        userbotLastQrStatusRef.current = nextStatus;
      } catch {
        // polling noise is ok
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [userbotAuthMode, userbotQrAuthToken, isUserbotVerified, showError, showSuccess]);

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
      applyUserbotVerified(response);
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
    if (!shouldShowCrmCredentials) {
      showError('Валидация CRM нужна только при выборе режима "Подключить CRM сейчас".');
      return;
    }
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
    let cancelled = false;
    agentService.getAdminDomainRegistry().then((data) => {
      if (cancelled) return;
      if (Array.isArray(data?.items) && data.items.length > 0) {
        setDomainRegistry(data.items);
      }
    }).catch(() => {
      // fallback to hardcoded options on error
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!isCrmAdminTemplate || !shouldShowCrmCredentials) {
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
    isCrmAdminTemplate,
    shouldShowCrmCredentials,
    form.values.crm_provider,
    form.values.crm_account_base_url,
    form.values.crm_access_token,
    crmValidationSignature,
  ]);

  useEffect(() => {
    if (!isCrmAdminTemplate || shouldShowCrmCredentials) return;
    form.setFieldError('crm_account_base_url', undefined);
    form.setFieldError('crm_access_token', undefined);
  }, [form.setFieldError, isCrmAdminTemplate, shouldShowCrmCredentials]);

  useEffect(() => {
    if (!isContentFactoryTemplate) return;
    if (!useMaxUserbotChannel) return;
    setUseMaxUserbotChannel(false);
    form.setFieldValue('max_token', '');
    form.setFieldError('max_token', undefined);
  }, [form.setFieldValue, form.setFieldError, isContentFactoryTemplate, useMaxUserbotChannel]);

  useEffect(() => {
    if (!isContentFactoryTemplate) return;
    setUseBotChannel(false);
    setUseUserbotChannel(false);
    setUseMaxBotChannel(false);
    setUseMaxUserbotChannel(false);
    setUseWhatsAppUserbotChannel(false);
    setUseWhatsAppBusinessApiChannel(false);
  }, [isContentFactoryTemplate]);

  useEffect(() => {
    if (!isSalesManagerTemplate) return;
    setUseBotChannel(false);
    setUseMaxBotChannel(false);
    setUseMaxUserbotChannel(false);
    setUseWhatsAppBusinessApiChannel(false);
  }, [isSalesManagerTemplate]);

  useEffect(() => {
    if (!isSalesManagerTemplate) return;
    if (!useUserbotChannel && !useWhatsAppUserbotChannel) {
      setUseUserbotChannel(true);
    }
  }, [isSalesManagerTemplate, useUserbotChannel, useWhatsAppUserbotChannel]);

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
                {selectedTemplatePricing?.description
                  || TEMPLATE_TYPE_HELP[form.values.template_type]
                  || TEMPLATE_TYPE_HELP.qa}
              </p>
              {selectedTemplatePricing ? (
                <div className="template-pricing-summary" role="note" aria-label="Стоимость шаблона">
                  {selectedTemplatePricing.is_free ? (
                    <p className="template-pricing-summary__row">
                      <span>Тариф:</span>
                      <strong>Бесплатно</strong>
                    </p>
                  ) : formatMaintenancePrice(selectedTemplatePricing.monthly_maintenance_rub_min) ? (
                    <>
                      <p className="template-pricing-summary__row">
                        <span>Обслуживание:</span>
                        <strong>
                          {formatMaintenancePrice(selectedTemplatePricing.monthly_maintenance_rub_min)}
                        </strong>
                      </p>
                      <p className="help-text template-pricing-summary__note">
                        Агент создаётся активным. Первые 3 дня — бесплатный пробный период,
                        затем нужна оплата подписки.
                      </p>
                    </>
                  ) : null}
                  <p className="help-text template-pricing-summary__note">
                    Токены LLM включены.
                  </p>
                </div>
              ) : null}
            </div>

            <div className="form-group">
              <label>Тип подключения:</label>
              {isContentFactoryTemplate ? (
                <>
                  <div className="connection-type-grid connection-type-grid--channels">
                    <div className="connection-type-card active connection-type-card--disabled connection-type-card--youtube">
                      YouTube
                    </div>
                  </div>
                  <p className="help-text">
                    Для шаблона "Контент-завод" доступен только канал YouTube.
                  </p>
                </>
              ) : (
                <>
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
                      className={`connection-type-card connection-type-card--with-beta ${useMaxBotChannel ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                      onClick={toggleMaxBotChannel}
                      disabled={form.isSubmitting || isSalesManagerTemplate}
                    >
                      <span className="connection-type-card-label connection-type-card-label--stacked-wa-api">
                        <span className="connection-type-card-label__row">MAX бот (API)</span>
                        <span className="connection-type-card-label__row connection-type-card-label__row--api-beta">
                          <span className="beta-badge">BETA</span>
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className={`connection-type-card connection-type-card--with-beta ${useMaxUserbotChannel ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                      onClick={toggleMaxUserbotChannel}
                      disabled={form.isSubmitting || isSalesManagerTemplate}
                    >
                      <span className="connection-type-card-label connection-type-card-label--stacked-wa-api">
                        <span className="connection-type-card-label__row">MAX юзербот</span>
                        <span className="connection-type-card-label__row connection-type-card-label__row--api-beta">
                          <span className="beta-badge">BETA</span>
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className={`connection-type-card ${useWhatsAppUserbotChannel ? 'active' : ''}`}
                      onClick={toggleWhatsAppUserbotChannel}
                      disabled={form.isSubmitting}
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
                      Для шаблона «ИИ МОП» доступны Telegram юзербот и/или WhatsApp юзербот (личные чаты и рассылка по базе).
                    </p>
                  ) : null}

                  {!isContentFactoryTemplate && !isSalesManagerTemplate ? (
                    <div className="form-group telephony-channel-block">
                      <FeatureToggle
                        checked={useTelephonyChannel}
                        onChange={(enabled) => {
                          if (enabled !== useTelephonyChannel) {
                            toggleTelephonyChannel();
                          }
                        }}
                        disabled={form.isSubmitting}
                        title={
                          <TitleWithDemoBadge>
                            Включить телефонный канал (ИИ-оператор)
                          </TitleWithDemoBadge>
                        }
                        accessibilityTitle="Включить телефонный канал (ИИ-оператор)"
                        description="Входящие звонки через Voximplant с голосовым ИИ-оператором."
                        helpText="Общий номер настраивается на сервере. Укажите уникальный добавочный (4 цифры) для этого агента."
                      />
                      {useTelephonyChannel ? (
                        <div className="telephony-channel-fields">
                          {telephonyPlatform ? (
                            <p className="help-text">
                              {telephonyPlatform.platform_ready ? (
                                <>
                                  Общий номер: <strong>{telephonyPlatform.shared_pool_e164}</strong>
                                  {telephonyPlatform.dial_hint ? (
                                    <>
                                      {' '}
                                      — набор: <strong>{telephonyPlatform.dial_hint}</strong>
                                    </>
                                  ) : null}
                                </>
                              ) : (
                                <>Сервер: задайте {telephonyPlatform.missing_env?.join(', ')}</>
                              )}
                            </p>
                          ) : null}
                          <input
                            type="text"
                            className="input-main"
                            name="telephony_routing_extension"
                            placeholder="Добавочный агента (4 цифры) *"
                            value={form.values.telephony_routing_extension}
                            onChange={(e) =>
                              form.setFieldValue(
                                'telephony_routing_extension',
                                e.target.value.replace(/\D/g, '').slice(0, 4),
                              )
                            }
                            disabled={form.isSubmitting}
                            maxLength={4}
                          />
                          {form.errors.telephony_routing_extension ? (
                            <p className="error-text">{form.errors.telephony_routing_extension}</p>
                          ) : null}
                          <input
                            type="text"
                            className="input-main"
                            name="telephony_voice_id"
                            placeholder="Голос TTS (voice_id, например default)"
                            value={form.values.telephony_voice_id}
                            onChange={form.handleChange}
                            disabled={form.isSubmitting}
                          />
                          <input
                            type="text"
                            className="input-main"
                            name="telephony_language"
                            placeholder="Язык (ru-RU)"
                            value={form.values.telephony_language}
                            onChange={form.handleChange}
                            disabled={form.isSubmitting}
                          />
                          <button
                            type="button"
                            className="btn btn-outline"
                            onClick={handleValidateTelephonyOnCreate}
                            disabled={form.isSubmitting || isValidatingTelephony}
                          >
                            {isValidatingTelephony ? 'Проверка...' : 'Проверить подключение'}
                          </button>
                          {telephonyValidateStatus ? (
                            <p className="help-text userbot-success">{telephonyValidateStatus}</p>
                          ) : null}
                          {telephonyWebhookUrl ? (
                            <div className="telephony-webhook-row">
                              <label>Webhook URL</label>
                              <div className="api-key-row">
                                <input type="text" className="input-main" readOnly value={telephonyWebhookUrl} />
                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  onClick={async () => {
                                    try {
                                      await copyTextToClipboard(telephonyWebhookUrl);
                                      showSuccess('Webhook URL скопирован');
                                    } catch {
                                      showError('Не удалось скопировать');
                                    }
                                  }}
                                >
                                  Копировать
                                </button>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              )}
            </div>

            {isCrmAdminTemplate && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Онбординг администратора</h3>
                <label htmlFor="crm_domain_type">Подшаблон:</label>
                <CustomSelect
                  id="crm_domain_type"
                  name="crm_domain_type"
                  className="input-main"
                  value={form.values.crm_domain_type}
                  onChange={form.handleChange}
                  options={crmDomainOptions.length > 0 ? crmDomainOptions : CRM_DOMAIN_OPTIONS_FALLBACK}
                  disabled={form.isSubmitting}
                />

                <label htmlFor="crm_mode" className="mt-input">
                  CRM-режим:
                </label>
                <CustomSelect
                  id="crm_mode"
                  name="crm_mode"
                  className="input-main"
                  value={form.values.crm_mode}
                  onChange={form.handleChange}
                  options={CRM_MODE_OPTIONS}
                  disabled={form.isSubmitting}
                />

                <div className="admin-template-onboarding-block">
                  <h4 className="admin-template-onboarding-title">Дополнительные фичи</h4>
                  <FeatureToggle
                    checked={Boolean(form.values.waitlist_enabled)}
                    onChange={(enabled) => form.setFieldValue('waitlist_enabled', enabled)}
                    disabled={form.isSubmitting}
                    title="Включить waitlist с авто-подбором окон"
                    helpText="Когда включено, агент сможет предлагать клиентам окна из waitlist при освобождении слотов."
                  />
                  <FeatureToggle
                    checked={Boolean(form.values.reminder_enabled)}
                    onChange={(enabled) => form.setFieldValue('reminder_enabled', enabled)}
                    disabled={form.isSubmitting}
                    title="Включить напоминания о визите"
                    helpText="При включении отправляются напоминания клиенту по расписанию, заданному в offsets."
                  />
                  <div className="admin-template-field">
                    <label htmlFor="reminder_offsets_hours">
                      Напоминания за (часы до визита, через запятую):
                    </label>
                    <input
                      id="reminder_offsets_hours"
                      name="reminder_offsets_hours"
                      className="input-main"
                      value={form.values.reminder_offsets_hours}
                      onChange={form.handleChange}
                      disabled={form.isSubmitting}
                      placeholder="24,2"
                    />
                  </div>
                  <FeatureToggle
                    checked={Boolean(form.values.manual_confirmation_enabled)}
                    onChange={(enabled) => form.setFieldValue('manual_confirmation_enabled', enabled)}
                    disabled={form.isSubmitting}
                    title="Ручное подтверждение дорогих/долгих услуг"
                    helpText="Агент будет запрашивать ручное подтверждение при превышении ценового порога или длительности услуги."
                  />
                  <label htmlFor="manual_confirmation_price_minor" className="mt-input">
                    Порог цены (minor):
                  </label>
                  <input
                    id="manual_confirmation_price_minor"
                    type="number"
                    min="0"
                    name="manual_confirmation_price_minor"
                    className="input-main"
                    value={form.values.manual_confirmation_price_minor}
                    onChange={form.handleChange}
                    disabled={form.isSubmitting}
                  />
                  <label htmlFor="manual_confirmation_duration_minutes" className="mt-input">
                    Порог длительности (мин):
                  </label>
                  <input
                    id="manual_confirmation_duration_minutes"
                    type="number"
                    min="1"
                    name="manual_confirmation_duration_minutes"
                    className="input-main"
                    value={form.values.manual_confirmation_duration_minutes}
                    onChange={form.handleChange}
                    disabled={form.isSubmitting}
                  />
                </div>

                <div className="admin-template-onboarding-block">
                    <h4 className="admin-template-onboarding-title">
                      {domainConfig ? domainConfig.label_ru || domainConfig.label : 'Настройки'} — Настройки
                    </h4>

                    {/* Custom domain extra settings */}
                    {isCustomDomain && (
                      <div className="admin-template-custom-domain-settings">
                        <label className="mt-input">Название роли сотрудника:</label>
                        <input
                          type="text"
                          className="input-main"
                          placeholder="Например: Тренер, Инструктор, Консультант"
                          value={customStaffRole}
                          onChange={(e) => setCustomStaffRole(e.target.value)}
                          disabled={form.isSubmitting}
                          maxLength={32}
                        />
                        <label className="mt-input">Доменная инструкция (для ИИ):</label>
                        <textarea
                          className="input-main"
                          placeholder="Опишите сферу деятельности, терминологию, что уточнять у клиента..."
                          value={customDomainInstruction}
                          onChange={(e) => setCustomDomainInstruction(e.target.value)}
                          disabled={form.isSubmitting}
                          rows={3}
                          maxLength={4000}
                        />
                        <FeatureToggle
                          checked={resourcesEnabled}
                          onChange={setResourcesEnabled}
                          disabled={form.isSubmitting}
                          title="Включить отдельные ресурсы"
                          description="Комнаты, оборудование и другие рабочие места будут отдельными сущностями."
                          helpText="Включите, если сотрудник и рабочее место не совпадают 1:1."
                        />
                      </div>
                    )}

                    <label className="mt-input">
                      {domainConfig?.staff_label_ru || 'Сотрудники'}:
                    </label>
                    <CardCarousel
                      addCard={() =>
                        setStaffList((prev) => [
                          ...prev,
                          { localId: newStaffId(), firstName: '', lastName: '', specialization: '' },
                        ])
                      }
                    >
                      {staffList.map((m) => (
                        <StaffCard
                          key={m.localId}
                          staff={m}
                          roleLabel={domainConfig?.staff_role_default || customStaffRole || 'specialist'}
                          specializationPlaceholder={crmDomainPlaceholders.specialization}
                          disabled={form.isSubmitting}
                          onChange={(updated) =>
                            setStaffList((prev) => prev.map((x) => (x.localId === m.localId ? updated : x)))
                          }
                          onRemove={() =>
                            setStaffList((prev) => prev.filter((x) => x.localId !== m.localId))
                          }
                        />
                      ))}
                    </CardCarousel>

                    <label className="mt-input">Услуги:</label>
                    <CardCarousel
                      addCard={() =>
                        setServiceList((prev) => [
                          ...prev,
                          { localId: newServiceLocalId(), title: '', price: '', duration: '', staffLocalIds: [] },
                        ])
                      }
                    >
                      {serviceList.map((s) => (
                        <ServiceCard
                          key={s.localId}
                          service={s}
                          titlePlaceholder={crmDomainPlaceholders.serviceTitle}
                          staffList={staffList}
                          disabled={form.isSubmitting}
                          onChange={(updated) =>
                            setServiceList((prev) => prev.map((x) => (x.localId === s.localId ? updated : x)))
                          }
                          onRemove={() =>
                            setServiceList((prev) => prev.filter((x) => x.localId !== s.localId))
                          }
                        />
                      ))}
                    </CardCarousel>
                  </div>

                {isCrmConnectionEnabled ? (
                  <>
                    <label htmlFor="crm_connect_timing" className="mt-input">
                      Когда подключить CRM:
                    </label>
                    <CustomSelect
                      id="crm_connect_timing"
                      name="crm_connect_timing"
                      className="input-main"
                      value={form.values.crm_connect_timing}
                      onChange={form.handleChange}
                      options={CRM_CONNECT_TIMING_OPTIONS}
                      disabled={form.isSubmitting}
                    />
                  </>
                ) : null}

                {shouldShowCrmCredentials ? (
                  <>
                    <label htmlFor="crm_provider" className="mt-input">CRM провайдер:</label>
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
                  </>
                ) : (
                  <p className="help-text">
                    CRM не требуется на старте. Агент создастся сразу в локальном режиме, а CRM можно подключить позже.
                  </p>
                )}
              </div>
            )}

            {form.values.template_type === 'sales_manager' && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Конфигурация Sales Manager</h3>
                <label htmlFor="sales_product_name">Продукт:</label>
                <input
                  id="sales_product_name"
                  type="text"
                  name="sales_product_name"
                  placeholder="Например: ИИ-автоматизация продаж RSD AI"
                  className={`input-main ${form.errors.sales_product_name ? 'error' : ''}`}
                  value={form.values.sales_product_name}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                />
                {form.errors.sales_product_name && (
                  <span className="error-message">{form.errors.sales_product_name}</span>
                )}

                <label htmlFor="sales_offer_type" className="mt-input">
                  Что продаете (категория):
                </label>
                <input
                  id="sales_offer_type"
                  type="text"
                  name="sales_offer_type"
                  placeholder="Например: SaaS, курсы, консалтинг, внедрение под ключ"
                  className={`input-main ${form.errors.sales_offer_type ? 'error' : ''}`}
                  value={form.values.sales_offer_type}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                />
                {form.errors.sales_offer_type && (
                  <span className="error-message">{form.errors.sales_offer_type}</span>
                )}

                <label htmlFor="sales_usp" className="mt-input">
                  УТП (опционально):
                </label>
                <textarea
                  id="sales_usp"
                  name="sales_usp"
                  placeholder="Например: подключение за 5 минут, быстрая интеграция с CRM, единый дашборд"
                  className="input-main textarea"
                  value={form.values.sales_usp}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  rows="3"
                ></textarea>
                <label htmlFor="workflow_completion_mode" className="mt-input">
                  Завершение диалога:
                </label>
                <CustomSelect
                  id="workflow_completion_mode"
                  name="workflow_completion_mode"
                  className="input-main"
                  value={form.values.workflow_completion_mode}
                  onChange={form.handleChange}
                  options={[
                    {
                      value: 'auto_finish_on_signal',
                      label: 'Продажа/окончание диалога (останавливать автопрогрев)',
                    },
                    {
                      value: 'continue_dialog',
                      label: 'Продолжать диалог по стадиям без авто-остановки',
                    },
                  ]}
                  disabled={form.isSubmitting}
                />
                <label htmlFor="lead_score_scale" className="mt-input">
                  Шкала оценки лида:
                </label>
                <CustomSelect
                  id="lead_score_scale"
                  name="lead_score_scale"
                  className="input-main"
                  value={String(form.values.lead_score_scale)}
                  onChange={form.handleChange}
                  options={[
                    { value: '100', label: '0–100 (детальная)' },
                    { value: '10', label: '0–10 (компактная)' },
                  ]}
                  disabled={form.isSubmitting}
                />
                <p className="help-text">
                  Агент будет сканировать сообщения в Telegram чатах и на каждом шаге принимать решение через
                  function-calling: писать или игнорировать лид. Далее диалог строится по стадиям и генерируется
                  LLM с учетом портрета клиента, истории общения и вашей базы знаний (RAG).
                </p>
              </div>
            )}

            {isContentFactoryTemplate && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">Конфигурация контент-завода</h3>
                <label htmlFor="content_company_name">Название компании:</label>
                <input
                  id="content_company_name"
                  type="text"
                  name="content_company_name"
                  placeholder="Например: RSD AI"
                  className={`input-main ${form.errors.content_company_name ? 'error' : ''}`}
                  value={form.values.content_company_name}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                />
                {form.errors.content_company_name && (
                  <span className="error-message">{form.errors.content_company_name}</span>
                )}

                <label htmlFor="content_company_activity" className="mt-input">
                  Деятельность:
                </label>
                <textarea
                  id="content_company_activity"
                  name="content_company_activity"
                  placeholder="Кратко опишите, чем занимается компания"
                  className={`input-main textarea ${form.errors.content_company_activity ? 'error' : ''}`}
                  value={form.values.content_company_activity}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  rows="3"
                ></textarea>
                {form.errors.content_company_activity && (
                  <span className="error-message">{form.errors.content_company_activity}</span>
                )}

                <label htmlFor="content_brand_tone" className="mt-input">
                  Тон коммуникации (опционально):
                </label>
                <textarea
                  id="content_brand_tone"
                  name="content_brand_tone"
                  placeholder="Например: экспертный, дружелюбный, энергичный"
                  className="input-main textarea"
                  value={form.values.content_brand_tone}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  rows="2"
                ></textarea>

                <label htmlFor="content_language" className="mt-input">
                  Язык контента:
                </label>
                <CustomSelect
                  id="content_language"
                  name="content_language"
                  className="input-main"
                  value={form.values.content_language}
                  onChange={form.handleChange}
                  options={[
                    { value: 'ru', label: 'Русский (ru)' },
                    { value: 'en', label: 'Английский (en)' },
                  ]}
                  disabled={form.isSubmitting}
                />

                <p className="help-text">
                  MVP публикует короткие видео в YouTube: без склеек, 1 публикация в день.
                </p>
              </div>
            )}

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
                <p className="help-text">
                  Как в приложении Telegram: QR или код по SMS. API-ключи с my.telegram.org не нужны.
                </p>

                <label className="mt-input">Способ входа:</label>
                <div className="connection-type-grid connection-type-grid--channels">
                  <button
                    type="button"
                    className={`connection-type-card ${userbotAuthMode === 'qr' ? 'active' : ''}`}
                    onClick={() => switchUserbotAuthMode('qr')}
                    disabled={form.isSubmitting}
                  >
                    QR-код
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${userbotAuthMode === 'phone' ? 'active' : ''}`}
                    onClick={() => switchUserbotAuthMode('phone')}
                    disabled={form.isSubmitting}
                  >
                    Код по SMS
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${userbotAuthMode === 'file' ? 'active' : ''}`}
                    onClick={() => switchUserbotAuthMode('file')}
                    disabled={form.isSubmitting}
                  >
                    Файл сессии
                  </button>
                </div>

                {userbotAuthMode === 'qr' ? (
                  <>
                    <p className="help-text">
                      Telegram → Настройки → Устройства → Подключить устройство. При включённой 2FA введите пароль ниже.
                    </p>
                    <div className="channel-actions-row">
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleUserbotQrStart}
                        disabled={form.isSubmitting || isStartingUserbotQr}
                      >
                        {isStartingUserbotQr ? 'Генерация QR...' : 'Показать QR-код'}
                      </button>
                    </div>
                    {userbotQrDataUrl ? (
                      <div className="userbot-qr-wrap">
                        <img src={userbotQrDataUrl} alt="Telegram QR" className="userbot-qr-image" />
                      </div>
                    ) : null}
                    {(userbotQrNeeds2fa || userbotAuthMode === 'qr') && (
                      <>
                        <label htmlFor="password_2fa" className="mt-input">Пароль 2FA:</label>
                        <input
                          id="password_2fa"
                          type="password"
                          name="password_2fa"
                          placeholder="Обязателен, если на аккаунте включена двухфакторная защита"
                          className="input-main"
                          value={form.values.password_2fa}
                          onChange={form.handleChange}
                          disabled={form.isSubmitting}
                        />
                        <div className="channel-actions-row">
                          <button
                            type="button"
                            className="btn btn-outline"
                            onClick={handleUserbotQrVerify2fa}
                            disabled={form.isSubmitting || isVerifyingUserbotQr2fa || !userbotQrNeeds2fa}
                          >
                            {isVerifyingUserbotQr2fa ? 'Проверка...' : 'Подтвердить 2FA'}
                          </button>
                        </div>
                      </>
                    )}
                  </>
                ) : null}

                {userbotAuthMode === 'phone' ? (
                  <>
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
                        <label htmlFor="password_2fa_phone" className="mt-input">Пароль 2FA (если включен):</label>
                        <input
                          id="password_2fa_phone"
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
                  </>
                ) : null}

                {userbotAuthMode === 'file' ? (
                  <>
                    <p className="help-text">
                      Загрузите .zip с папкой tdata, файл .session (Telethon) или .txt со StringSession.
                    </p>
                    <UserbotSessionFileUpload
                      disabled={form.isSubmitting}
                      isImporting={isImportingUserbotSession}
                      onFileSelect={handleUserbotImportSession}
                    />
                    {form.errors.session_string && (
                      <span className="error-message">{form.errors.session_string}</span>
                    )}
                  </>
                ) : null}

                {isUserbotVerified && (
                  <p className="help-text userbot-success">
                    Userbot подтвержден: {verifiedUserbotLabel || 'успешно'}
                  </p>
                )}
              </div>
            )}

            {useMaxBotChannel && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">MAX бот (официальный API)</h3>
                <label htmlFor="max_bot_token">MAX bot token:</label>
                <input
                  id="max_bot_token"
                  type="text"
                  name="max_bot_token"
                  placeholder="Токен из MAX для партнеров: Чат-боты → Интеграция → Получить токен"
                  className={`input-main ${form.errors.max_bot_token ? 'error' : ''}`}
                  value={form.values.max_bot_token}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                />
                {form.errors.max_bot_token && (
                  <span className="error-message">{form.errors.max_bot_token}</span>
                )}
                <p className="help-text">
                  Для production используйте Webhook в MAX, для разработки поддерживается long polling.
                </p>
              </div>
            )}

            {useMaxUserbotChannel && (
              <div className="form-group">
                <h3 className="agent-form-channel-title">MAX юзербот</h3>
                <label htmlFor="max_token">MAX token:</label>
                <textarea
                  id="max_token"
                  name="max_token"
                  placeholder="Токен из localStorage.__oneme_auth.token"
                  className={`input-main textarea ${form.errors.max_token ? 'error' : ''}`}
                  value={form.values.max_token}
                  onChange={form.handleChange}
                  disabled={form.isSubmitting}
                  rows="3"
                ></textarea>
                {form.errors.max_token && (
                  <span className="error-message">{form.errors.max_token}</span>
                )}

                <p className="help-text">
                  Будут обрабатываться все личные сообщения (ЛС) в MAX.
                </p>
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