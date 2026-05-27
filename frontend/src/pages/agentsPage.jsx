/**
 * Agents Page
 * Display user's agents and manage full lifecycle
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import AgentsEmptyState from '../components/AgentsEmptyState';
import { useAsync } from '../hooks/useAsync';
import agentService from '../services/agentService';
import pricingService from '../services/pricingService';
import { formatRubPrice } from '../utils/agentTemplatePricing';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import { useAuth } from '../context/useAuth';
import { validateFile } from '../utils/validation';
import TelephonyVoicePreview from '../components/TelephonyVoicePreview';
import DemoBadge, { TitleWithDemoBadge } from '../components/DemoBadge';
import {
  TELEPHONY_PROVIDER,
  copyTextToClipboard,
  findTelephonyChannel,
} from '../utils/telephony';
import '../styles/agentsPage.css';

const AGENTS_EMPTY_MESSAGE = 'У вас еще нет агентов, создайте прямо сейчас';
const AGENTS_EMPTY_CTA = 'Создайте прямо сейчас';
const fileIdentity = (file) => `${file.name}::${file.size}::${file.lastModified}`;
const linkIdentity = (link) => link.trim().toLowerCase();
const isPortraitFeatureEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_portrait !== false;
};
const isSmartSearchEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_smart_search !== false;
};
const isChatFreezeEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_freeze !== false;
};
const isStartProcessingEnabled = (agent) => Boolean(agent?.process_start_with_llm);
const getTemplateConfig = (agent) => {
  const cfg = agent?.template_config;
  return cfg && typeof cfg === 'object' ? cfg : {};
};
const AGENT_AVAILABILITY_WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const COMMON_AGENT_TIMEZONES = [
  'Europe/Moscow',
  'Europe/Kaliningrad',
  'Asia/Yekaterinburg',
  'Asia/Novosibirsk',
  'Asia/Vladivostok',
  'Europe/Helsinki',
  'Europe/Berlin',
  'UTC',
  'Europe/London',
  'America/New_York',
];

const getBrowserTimezoneSafe = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Moscow';
  } catch {
    return 'Europe/Moscow';
  }
};

const buildDefaultAgentAvailabilityWeekdays = () =>
  Array.from({ length: 7 }, (_, i) =>
    i < 5
      ? { enabled: true, start: '09:00', end: '18:00' }
      : { enabled: false, start: '09:00', end: '18:00' }
  );

const normalizeWeekdaysFromConfig = (raw) => {
  if (!Array.isArray(raw) || raw.length !== 7) {
    return buildDefaultAgentAvailabilityWeekdays();
  }
  return raw.map((d) => ({
    enabled: Boolean(d?.enabled),
    start: String(d?.start || '09:00').slice(0, 5),
    end: String(d?.end || '18:00').slice(0, 5),
  }));
};

/** Parse HH:MM into two padded strings (clamps to valid clock). */
const splitTimeValue = (v) => {
  const raw = String(v ?? '00:00').trim();
  const [a0 = '0', b0 = '0'] = raw.split(':');
  const hd = (a0 || '').replace(/\D/g, '').slice(0, 2);
  const md = (b0 || '').replace(/\D/g, '').slice(0, 2);
  const hi = Math.max(0, Math.min(23, parseInt(hd || '0', 10) || 0));
  const mi = Math.max(0, Math.min(59, parseInt(md || '0', 10) || 0));
  return [String(hi).padStart(2, '0'), String(mi).padStart(2, '0')];
};

const digits2 = (s) => (s || '').replace(/\D/g, '').slice(0, 2);

/** Два поля ЧЧ и ММ: только набор с клавиатуры, без нативного time-picker браузера. */
const TimeDigitsField = ({ value, onChange, disabled, ariaLabel }) => {
  const hourRef = useRef(null);
  const minRef = useRef(null);
  const [hour, setHour] = useState(() => splitTimeValue(value)[0]);
  const [minute, setMinute] = useState(() => splitTimeValue(value)[1]);
  const focusedRef = useRef(false);
  const hourStrRef = useRef(hour);
  const minStrRef = useRef(minute);
  hourStrRef.current = hour;
  minStrRef.current = minute;

  useEffect(() => {
    if (!focusedRef.current) {
      const [h, m] = splitTimeValue(value);
      setHour(h);
      setMinute(m);
    }
  }, [value]);

  const emitPair = (hStr, mStr) => {
    const hi = Math.max(0, Math.min(23, parseInt(digits2(hStr) || '0', 10) || 0));
    const mi = Math.max(0, Math.min(59, parseInt(digits2(mStr) || '0', 10) || 0));
    const H = String(hi).padStart(2, '0');
    const M = String(mi).padStart(2, '0');
    setHour(H);
    setMinute(M);
    onChange(`${H}:${M}`);
  };

  const handleContainerBlur = () => {
    requestAnimationFrame(() => {
      const ae = document.activeElement;
      if (ae !== hourRef.current && ae !== minRef.current) {
        focusedRef.current = false;
        emitPair(hourStrRef.current, minStrRef.current);
      }
    });
  };

  const onHourChange = (e) => {
    const v = digits2(e.target.value);
    setHour(v);
    if (v.length === 2) {
      requestAnimationFrame(() => {
        minRef.current?.focus();
        minRef.current?.select?.();
      });
    }
  };

  const onMinuteChange = (e) => {
    setMinute(digits2(e.target.value));
  };

  const onHourFocus = () => {
    focusedRef.current = true;
    requestAnimationFrame(() => hourRef.current?.select());
  };

  const onMinuteFocus = () => {
    focusedRef.current = true;
  };

  return (
    <div
      className={`agent-availability-time-field ${disabled ? 'agent-availability-time-field--disabled' : ''}`}
    >
      <div
        className="agent-availability-time-field__box"
        role="group"
        aria-label={ariaLabel}
      >
        <input
          ref={hourRef}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          className="agent-availability-time-digit"
          value={hour}
          onChange={onHourChange}
          onBlur={handleContainerBlur}
          onFocus={onHourFocus}
          disabled={disabled}
          aria-label={`${ariaLabel}, часы (0–23)`}
          maxLength={2}
        />
        <span className="agent-availability-time-colon" aria-hidden="true">
          :
        </span>
        <input
          ref={minRef}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          className="agent-availability-time-digit"
          value={minute}
          onChange={onMinuteChange}
          onBlur={handleContainerBlur}
          onFocus={onMinuteFocus}
          disabled={disabled}
          aria-label={`${ariaLabel}, минуты (0–59)`}
          maxLength={2}
        />
      </div>
    </div>
  );
};
const toCsvOffsets = (value) => {
  if (!Array.isArray(value)) return '24,2';
  const normalized = value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item) && item > 0 && item <= 72);
  return normalized.length > 0 ? normalized.join(',') : '24,2';
};
const parseReminderOffsets = (value) =>
  String(value || '')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0 && item <= 72);

const normalizeSalesTriggerWordsList = (raw) => {
  const list = Array.isArray(raw) ? raw : [];
  const out = [];
  for (const item of list) {
    const w = String(item || '').trim().toLowerCase();
    if (!w || w.length > 64) continue;
    if (!out.includes(w)) out.push(w);
    if (out.length >= 30) break;
  }
  return out.length > 0 ? out : ['купить'];
};
const channelLabel = (channel) => {
  if (!channel) return 'Канал';
  if (channel.provider === 'telegram_bot') return 'Telegram бот';
  if (channel.provider === 'telegram_userbot') return 'Telegram userbot';
  if (channel.provider === 'max_bot') return 'MAX bot';
  if (channel.provider === 'max_userbot') return 'MAX userbot';
  if (channel.provider === 'whatsapp_userbot') return 'WhatsApp userbot';
  if (channel.provider === 'whatsapp_business_api') return 'WhatsApp Business API';
  if (channel.provider === TELEPHONY_PROVIDER) return 'Телефония (ИИ-оператор)';
  return channel.provider || 'Канал';
};
const WIDGET_TEMPLATE_TYPES = new Set(['qa', 'crm_admin']);
const TELEPHONY_VOICE_PREVIEW_TEMPLATES = WIDGET_TEMPLATE_TYPES;

const CustomSelect = ({
  id,
  name,
  value,
  options,
  onChange,
  disabled = false,
  className = 'input-main',
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
  const buttonClassName = ['custom-select-trigger', className].filter(Boolean).join(' ');

  const handleSelectOption = (nextValue) => {
    const optionToSelect = options.find((option) => option.value === nextValue);
    if (optionToSelect?.disabled) return;
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
      {isOpen && !disabled ? (
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
      ) : null}
    </div>
  );
};

const FeatureToggle = ({ checked, onChange, disabled, title, description, helpText }) => {
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
        title={title}
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
        aria-label={`Справка: ${title}`}
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

/** Same switch UX as FeatureToggle, без справки — для компактных рядов (дни недели). */
const FeatureToggleCompact = ({ checked, onChange, disabled, title }) => (
  <div className={`feature-toggle feature-toggle--compact ${checked ? 'feature-toggle--on' : ''}`}>
    <button
      type="button"
      className="feature-toggle__main"
      onClick={() => {
        onChange(!checked);
      }}
      disabled={disabled}
      aria-pressed={checked}
      title={title}
    >
      <span className="feature-toggle__content">
        <span className="feature-toggle__title">{title}</span>
      </span>
      <span className="feature-toggle__switch" aria-hidden="true">
        <span className="feature-toggle__thumb" />
      </span>
    </button>
  </div>
);

const AgentCard = ({ agent, isSelected, onManage, onDelete, onToggle }) => {
  const agentName = agent.bot_username || agent.name || 'Агент';
  const isActive = !!agent.is_active;

  const handleSelect = () => {
    onManage(agent.id);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onManage(agent.id);
    }
  };

  return (
    <div
      className={`agent-item ${isSelected ? 'agent-item--selected' : ''}`}
      onClick={handleSelect}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`Выбрать агента ${agentName}`}
    >
      <div className="agent-info">
        <span
          className={`agent-status-dot ${isActive ? 'agent-status-dot--active' : 'agent-status-dot--inactive'}`}
          title={isActive ? 'Активен' : 'Не активен'}
        ></span>
        <div className="agent-details">
          <h3 className="agent-name">{agentName}</h3>
          <p className="agent-role">{isActive ? 'Активен' : 'Не активен'}</p>
        </div>
      </div>
      <div className="agent-actions">
        <button
          className="edit-btn"
          onClick={(event) => {
            event.stopPropagation();
            onManage(agent.id);
          }}
          title="Управлять агентом"
          aria-label="Manage agent"
        >
          Управлять
        </button>
        <button
          className="edit-btn"
          onClick={(event) => {
            event.stopPropagation();
            onToggle(agent.id);
          }}
          title={isActive ? 'Отключить агента' : 'Включить агента'}
          aria-label={isActive ? 'Disable agent' : 'Enable agent'}
        >
          {isActive ? 'OFF' : 'ON'}
        </button>
        <button
          className="delete-btn"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(agent.id);
          }}
          title="Delete agent"
          aria-label="Delete agent"
        >
          ×
        </button>
      </div>
    </div>
  );
};

const AgentsPageContent = () => {
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();
  const { isAuthenticated } = useAuth();
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);
  const [isSavingWelcome, setIsSavingWelcome] = useState(false);
  const [isSavingPortraitFeature, setIsSavingPortraitFeature] = useState(false);
  const [isSavingSmartSearch, setIsSavingSmartSearch] = useState(false);
  const [isSavingChatFreeze, setIsSavingChatFreeze] = useState(false);
  const [isSavingStartProcessing, setIsSavingStartProcessing] = useState(false);
  const [isSavingTemplateConfig, setIsSavingTemplateConfig] = useState(false);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [isGeneratingWelcome, setIsGeneratingWelcome] = useState(false);
  const [isUploadingDocs, setIsUploadingDocs] = useState(false);
  const [isUploadingLink, setIsUploadingLink] = useState(false);
  const [pendingLink, setPendingLink] = useState('');
  const [systemPromptDraft, setSystemPromptDraft] = useState('');
  const [welcomeDraft, setWelcomeDraft] = useState('');
  const [channels, setChannels] = useState([]);
  const [isChannelsModalOpen, setIsChannelsModalOpen] = useState(false);
  const [channelModalTab, setChannelModalTab] = useState('bot');
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [isSavingChannel, setIsSavingChannel] = useState(false);
  const [botTokenDraft, setBotTokenDraft] = useState('');
  const [makePrimaryChannel, setMakePrimaryChannel] = useState(false);
  const [userbotApiId, setUserbotApiId] = useState('');
  const [userbotApiHash, setUserbotApiHash] = useState('');
  const [userbotPhone, setUserbotPhone] = useState('');
  const [userbotCode, setUserbotCode] = useState('');
  const [userbotPassword, setUserbotPassword] = useState('');
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [userbotSessionString, setUserbotSessionString] = useState('');
  const [maxBotTokenDraft, setMaxBotTokenDraft] = useState('');
  const [maxUserbotTokenDraft, setMaxUserbotTokenDraft] = useState('');
  const [isSendingUserbotCode, setIsSendingUserbotCode] = useState(false);
  const [isVerifyingUserbotCode, setIsVerifyingUserbotCode] = useState(false);
  const [whatsappUserbotPhone, setWhatsappUserbotPhone] = useState('');
  const [whatsappUserbotSessionString, setWhatsappUserbotSessionString] = useState('');
  const [whatsappUserbotClientLabel, setWhatsappUserbotClientLabel] = useState('');
  const [whatsappUserbotMode, setWhatsappUserbotMode] = useState('simple');
  const [whatsappUserbotAuthToken, setWhatsappUserbotAuthToken] = useState('');
  const [whatsappUserbotQrDataUrl, setWhatsappUserbotQrDataUrl] = useState('');
  const [isSendingWhatsappUserbotCode, setIsSendingWhatsappUserbotCode] = useState(false);
  const [isVerifyingWhatsappUserbotCode, setIsVerifyingWhatsappUserbotCode] = useState(false);
  const [isWhatsappUserbotVerified, setIsWhatsappUserbotVerified] = useState(false);
  const whatsappUserbotLastAuthStatusRef = useRef('');
  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const [whatsappAccessToken, setWhatsappAccessToken] = useState('');
  const [whatsappBusinessAccountId, setWhatsappBusinessAccountId] = useState('');
  const [whatsappVerifyToken, setWhatsappVerifyToken] = useState('');
  const [telephonyPlatform, setTelephonyPlatform] = useState(null);
  const [telephonyVoiceId, setTelephonyVoiceId] = useState('default');
  const [telephonyLanguage, setTelephonyLanguage] = useState('ru-RU');
  const [telephonyRecordCalls, setTelephonyRecordCalls] = useState(true);
  const [telephonyDisclaimerPlayed, setTelephonyDisclaimerPlayed] = useState(true);
  const [telephonyRoutingExtension, setTelephonyRoutingExtension] = useState('');
  const [telephonyValidateStatus, setTelephonyValidateStatus] = useState('');
  const [telephonyWebhookUrl, setTelephonyWebhookUrl] = useState('');
  const [isValidatingTelephony, setIsValidatingTelephony] = useState(false);
  const [adminWaitlistEnabled, setAdminWaitlistEnabled] = useState(true);
  const [adminReminderEnabled, setAdminReminderEnabled] = useState(true);
  const [adminReminderOffsets, setAdminReminderOffsets] = useState('24,2');
  const [adminManualConfirmationEnabled, setAdminManualConfirmationEnabled] = useState(false);
  const [adminManualConfirmationPriceMinor, setAdminManualConfirmationPriceMinor] = useState('15000');
  const [adminManualConfirmationDurationMinutes, setAdminManualConfirmationDurationMinutes] = useState('120');
  const [adminPaidBookingEnabled, setAdminPaidBookingEnabled] = useState(false);
  const [adminYookassaApiKey, setAdminYookassaApiKey] = useState('');
  const [adminHasYookassaApiKey, setAdminHasYookassaApiKey] = useState(false);
  const [salesProductName, setSalesProductName] = useState('');
  const [salesOfferType, setSalesOfferType] = useState('');
  const [salesUsp, setSalesUsp] = useState('');
  const [salesWorkflowCompletionMode, setSalesWorkflowCompletionMode] = useState('auto_finish_on_signal');
  const [salesLeadScoreScale, setSalesLeadScoreScale] = useState('100');
  const [salesLeadGenerationEnabled, setSalesLeadGenerationEnabled] = useState(true);
  const [salesNeuroCommentingEnabled, setSalesNeuroCommentingEnabled] = useState(false);
  const [salesLiveChatSimulationEnabled, setSalesLiveChatSimulationEnabled] = useState(false);
  const [salesTriggerWords, setSalesTriggerWords] = useState(() => ['купить']);
  const [salesTriggerWordDraft, setSalesTriggerWordDraft] = useState('');
  const [agentAvailAlwaysOn, setAgentAvailAlwaysOn] = useState(true);
  const [agentAvailTimezone, setAgentAvailTimezone] = useState(() => getBrowserTimezoneSafe());
  const [agentAvailWeekdays, setAgentAvailWeekdays] = useState(buildDefaultAgentAvailabilityWeekdays);
  const [isSavingAgentAvailability, setIsSavingAgentAvailability] = useState(false);
  const detailsRequestIdRef = useRef(0);
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    execute();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isChannelsModalOpen) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isChannelsModalOpen]);

  const handleCreateAgent = () => {
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  const handleOpenDetailedAnalytics = () => {
    if (!selectedBotId) {
      showError('Сначала выберите агента');
      return;
    }
    navigate(NAVIGATION_ROUTES.AGENT_ANALYTICS(selectedBotId));
  };

  const refreshAgents = async () => {
    const updated = await execute();
    return updated || [];
  };

  const loadAgentDetails = async (botId) => {
    const requestId = detailsRequestIdRef.current + 1;
    detailsRequestIdRef.current = requestId;
    setSelectedBotId(botId);
    setSelectedAgent(null);
    setDocuments([]);
    setChannels([]);
    setIsLoadingDetails(true);
    try {
      const [agent, docs] = await Promise.all([
        agentService.getById(botId),
        agentService.getDocumentsByBotId(botId),
      ]);
      if (requestId !== detailsRequestIdRef.current) return;
      setSelectedAgent(agent);
      setSystemPromptDraft(agent.system_prompt || '');
      setWelcomeDraft(agent.welcome_message || '');
      setDocuments(docs || []);
      setChannels(agent.channels || []);
    } catch (error) {
      if (requestId !== detailsRequestIdRef.current) return;
      showError(error?.message || 'Ошибка при загрузке карточки агента');
    } finally {
      if (requestId !== detailsRequestIdRef.current) return;
      setIsLoadingDetails(false);
    }
  };

  const handleDeleteAgent = async (botId) => {
    if (!window.confirm('Вы уверены, что хотите удалить агента?')) {
      return;
    }

    try {
      await agentService.delete(botId);
      showSuccess('Агент успешно удален!');
      const updatedAgents = await refreshAgents();
      if (selectedBotId === botId) {
        setSelectedBotId(null);
        setSelectedAgent(null);
        setDocuments([]);
        if (updatedAgents.length > 0) {
          await loadAgentDetails(updatedAgents[0].id);
        }
      }
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении агента');
    }
  };

  const handleToggleAgent = async (botId) => {
    const agentBeforeToggle = (agents || []).find((item) => item.id === botId)
      || (selectedBotId === botId ? selectedAgent : null);
    const willActivate = agentBeforeToggle && !agentBeforeToggle.is_active;

    try {
      const updatedAgent = await agentService.toggleStatus(botId);
      showSuccess(willActivate ? 'Агент активирован' : 'Агент деактивирован');
      await refreshAgents();
      if (selectedBotId === botId) {
        setSelectedAgent((prev) => ({ ...(prev || {}), ...updatedAgent }));
      }
    } catch (error) {
      const paymentDetail = error?.data?.detail;
      const billing = paymentDetail && typeof paymentDetail === 'object' ? paymentDetail.billing : null;
      const activationRub = Number(billing?.activation_required_rub || 0);
      if (error?.status === 402 && willActivate && activationRub > 0) {
        const confirmed = window.confirm(
          `Для активации требуется оплата запуска от ${formatRubPrice(activationRub)} ₽. Перейти к оплате?`
        );
        if (confirmed) {
          try {
            const returnUrl = `${window.location.origin}${NAVIGATION_ROUTES.AGENTS}?agent_payment=1`;
            const payment = await pricingService.createAgentBillingPayment({
              agent_id: botId,
              payment_kind: 'agent_activation',
              return_url: returnUrl,
            });
            if (payment?.confirmation_url) {
              window.location.href = payment.confirmation_url;
              return;
            }
            showError('Сервис оплаты вернул некорректный ответ.');
          } catch (paymentError) {
            showError(paymentError?.message || 'Не удалось создать платёж');
          }
          return;
        }
      }
      const message =
        (paymentDetail && typeof paymentDetail === 'object' && paymentDetail.message)
        || error?.message
        || 'Ошибка при изменении статуса агента';
      showError(message);
    }
  };

  const handleSaveSystemPrompt = async () => {
    if (!selectedBotId) return;
    if (!systemPromptDraft.trim()) {
      showError('Системный промпт не должен быть пустым');
      return;
    }

    setIsSavingPrompt(true);
    try {
      const nextSystemPrompt = systemPromptDraft.trim();
      await agentService.update(selectedBotId, {
        system_prompt: nextSystemPrompt,
      });
      setSelectedAgent((prev) => (
        prev
          ? {
              ...prev,
              system_prompt: nextSystemPrompt,
            }
          : prev
      ));
      showSuccess('Системный промпт обновлен');
    } catch (error) {
      showError(error?.message || 'Ошибка при обновлении системного промпта');
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const handleSaveWelcomeMessage = async () => {
    if (!selectedBotId) return;

    setIsSavingWelcome(true);
    try {
      const nextWelcome = welcomeDraft.trim() || null;
      await agentService.update(selectedBotId, {
        welcome_message: nextWelcome,
      });
      setSelectedAgent((prev) => (
        prev
          ? {
              ...prev,
              welcome_message: nextWelcome,
            }
          : prev
      ));
      showSuccess('Приветственное сообщение обновлено');
    } catch (error) {
      showError(error?.message || 'Ошибка при обновлении приветствия');
    } finally {
      setIsSavingWelcome(false);
    }
  };

  const handleAiImprovePrompt = async () => {
    if (!selectedBotId) return;
    setIsGeneratingPrompt(true);
    try {
      const result = await agentService.aiImprovePrompt(selectedBotId);
      const nextPrompt = result?.system_prompt || '';
      setSystemPromptDraft(nextPrompt);
      setSelectedAgent((prev) => ({ ...(prev || {}), system_prompt: nextPrompt }));
      showSuccess('ИИ улучшил системный промпт');
    } catch (error) {
      showError(error?.message || 'Ошибка при улучшении промпта через ИИ');
    } finally {
      setIsGeneratingPrompt(false);
    }
  };

  const handleAiGenerateWelcome = async () => {
    if (!selectedBotId) return;
    setIsGeneratingWelcome(true);
    try {
      const result = await agentService.aiGenerateWelcome(selectedBotId);
      const nextWelcome = result?.welcome_message || '';
      setWelcomeDraft(nextWelcome);
      setSelectedAgent((prev) => ({ ...(prev || {}), welcome_message: nextWelcome }));
      showSuccess('ИИ сгенерировал приветствие');
    } catch (error) {
      showError(error?.message || 'Ошибка при генерации приветствия через ИИ');
    } finally {
      setIsGeneratingWelcome(false);
    }
  };

  const handleTogglePortraitFeature = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = {
      ...currentConfig,
      enable_chat_portrait: Boolean(enabled),
    };
    setIsSavingPortraitFeature(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              template_config: nextConfig,
            }
          : prev
      );
      showSuccess(enabled ? 'Функция портрета включена' : 'Функция портрета отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку портрета');
    } finally {
      setIsSavingPortraitFeature(false);
    }
  };

  const handleToggleSmartSearch = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = {
      ...currentConfig,
      enable_smart_search: Boolean(enabled),
    };
    setIsSavingSmartSearch(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              template_config: nextConfig,
            }
          : prev
      );
      showSuccess(enabled ? 'Умный поиск включен' : 'Умный поиск отключен');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку умного поиска');
    } finally {
      setIsSavingSmartSearch(false);
    }
  };

  const handleToggleChatFreeze = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    if (String(selectedAgent.template_type || 'qa').trim().toLowerCase() !== 'qa') {
      showError('Функция заморозки чата доступна только для шаблона Консультант (QA)');
      return;
    }
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = {
      ...currentConfig,
      enable_chat_freeze: Boolean(enabled),
    };
    setIsSavingChatFreeze(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              template_config: nextConfig,
            }
          : prev
      );
      showSuccess(enabled ? 'Функция заморозки чата включена' : 'Функция заморозки чата отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку заморозки чата');
    } finally {
      setIsSavingChatFreeze(false);
    }
  };

  const handleToggleStartProcessing = async (enabled) => {
    if (!selectedBotId) return;
    setIsSavingStartProcessing(true);
    try {
      await agentService.update(selectedBotId, {
        process_start_with_llm: Boolean(enabled),
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              process_start_with_llm: Boolean(enabled),
            }
          : prev
      );
      showSuccess(enabled ? 'Обработка /start через LLM включена' : 'Обработка /start через LLM отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку обработки /start');
    } finally {
      setIsSavingStartProcessing(false);
    }
  };

  const handleSaveAdminTemplateConfig = async () => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig = getTemplateConfig(selectedAgent);
    const nextConfig = {
      ...currentConfig,
      waitlist_enabled: Boolean(adminWaitlistEnabled),
      reminder_enabled: Boolean(adminReminderEnabled),
      reminder_offsets_hours: parseReminderOffsets(adminReminderOffsets),
      manual_confirmation_enabled: Boolean(adminManualConfirmationEnabled),
      manual_confirmation_price_minor: Math.max(0, Number(adminManualConfirmationPriceMinor) || 0),
      manual_confirmation_duration_minutes: Math.max(1, Number(adminManualConfirmationDurationMinutes) || 120),
      paid_booking_enabled: Boolean(adminPaidBookingEnabled),
    };
    const hasTypedYookassaKey = adminYookassaApiKey.trim().length > 0;
    const updatePayload = { template_config: nextConfig };
    if (adminPaidBookingEnabled) {
      if (hasTypedYookassaKey) {
        updatePayload.yookassa_api_key = adminYookassaApiKey.trim();
      } else if (!adminHasYookassaApiKey) {
        showError('Укажите API ключ ЮKassa в формате shop_id:secret_key');
        return;
      }
    } else {
      updatePayload.yookassa_api_key = '';
    }
    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, updatePayload);
      setSelectedAgent((prev) => (prev
        ? { ...prev, template_config: nextConfig, has_booking_payment_api_key: adminPaidBookingEnabled ? (adminHasYookassaApiKey || hasTypedYookassaKey) : false }
        : prev));
      if (adminPaidBookingEnabled && hasTypedYookassaKey) {
        setAdminYookassaApiKey('');
        setAdminHasYookassaApiKey(true);
      }
      if (!adminPaidBookingEnabled) {
        setAdminYookassaApiKey('');
        setAdminHasYookassaApiKey(false);
      }
      showSuccess('Настройки шаблона Администратор обновлены');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройки шаблона Администратор');
    } finally {
      setIsSavingTemplateConfig(false);
    }
  };

  const handleSaveSalesTemplateConfig = async () => {
    if (!selectedBotId || !selectedAgent) return;
    if (!salesProductName.trim()) {
      showError('Укажите продукт');
      return;
    }
    if (!salesOfferType.trim()) {
      showError('Укажите категорию предложения');
      return;
    }
    const currentConfig = getTemplateConfig(selectedAgent);
    const nextConfig = {
      ...currentConfig,
      sales_product_name: salesProductName.trim(),
      sales_offer_type: salesOfferType.trim(),
      sales_usp: salesUsp.trim(),
      workflow_completion_mode:
        salesWorkflowCompletionMode === 'continue_dialog' ? 'continue_dialog' : 'auto_finish_on_signal',
      lead_score_scale: salesLeadScoreScale === '10' ? 10 : 100,
      lead_generation_enabled: Boolean(salesLeadGenerationEnabled),
      neuro_commenting_enabled: Boolean(salesNeuroCommentingEnabled),
      live_chat_simulation_enabled: Boolean(salesLiveChatSimulationEnabled),
      trigger_words: normalizeSalesTriggerWordsList(salesTriggerWords),
    };
    const allSalesActivitiesDisabled =
      !nextConfig.lead_generation_enabled
      && !nextConfig.neuro_commenting_enabled
      && !nextConfig.live_chat_simulation_enabled;
    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
        ...(allSalesActivitiesDisabled ? { is_active: false } : {}),
      });
      setSelectedAgent((prev) => (
        prev
          ? {
              ...prev,
              template_config: nextConfig,
              ...(allSalesActivitiesDisabled ? { is_active: false } : {}),
            }
          : prev
      ));
      showSuccess(
        allSalesActivitiesDisabled
          ? 'Все активности отключены: агент автоматически деактивирован'
          : 'Настройки шаблона Менеджер продаж обновлены'
      );
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройки шаблона Менеджер продаж');
    } finally {
      setIsSavingTemplateConfig(false);
    }
  };

  const handleToggleSalesActivity = async (field, enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig = getTemplateConfig(selectedAgent);
    const nextConfig = {
      ...currentConfig,
      [field]: Boolean(enabled),
      trigger_words: normalizeSalesTriggerWordsList(salesTriggerWords),
    };
    const leadGenerationEnabled = Boolean(nextConfig.lead_generation_enabled);
    const neuroCommentingEnabled = Boolean(nextConfig.neuro_commenting_enabled);
    const liveChatSimulationEnabled = Boolean(nextConfig.live_chat_simulation_enabled);
    const allSalesActivitiesDisabled =
      !leadGenerationEnabled && !neuroCommentingEnabled && !liveChatSimulationEnabled;

    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, {
        template_config: nextConfig,
        ...(allSalesActivitiesDisabled ? { is_active: false } : {}),
      });
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              template_config: nextConfig,
              ...(allSalesActivitiesDisabled ? { is_active: false } : {}),
            }
          : prev
      );
      setSalesLeadGenerationEnabled(leadGenerationEnabled);
      setSalesNeuroCommentingEnabled(neuroCommentingEnabled);
      setSalesLiveChatSimulationEnabled(liveChatSimulationEnabled);
      showSuccess(
        allSalesActivitiesDisabled
          ? 'Все активности отключены: агент автоматически деактивирован'
          : 'Настройка активности обновлена'
      );
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку активности');
    } finally {
      setIsSavingTemplateConfig(false);
    }
  };

  const handleAddSalesTriggerWord = () => {
    const w = salesTriggerWordDraft.trim().toLowerCase();
    if (!w || w.length > 64) return;
    setSalesTriggerWords((prev) => {
      if (prev.includes(w)) return prev;
      if (prev.length >= 30) return prev;
      return [...prev, w];
    });
    setSalesTriggerWordDraft('');
  };

  const handleRemoveSalesTriggerWord = (word) => {
    setSalesTriggerWords((prev) => prev.filter((x) => x !== word));
  };

  const handleSalesTriggerWordDraftKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAddSalesTriggerWord();
    }
  };

  const handleUploadDocuments = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!selectedBotId || files.length === 0) return;
    const uniqueFiles = Array.from(new Map(files.map((f) => [fileIdentity(f), f])).values());

    const validFiles = [];
    const fileErrors = [];
    uniqueFiles.forEach((file) => {
      const check = validateFile(file);
      if (check.isValid) {
        validFiles.push(file);
      } else {
        fileErrors.push(`${file.name}: ${check.errors.join(', ')}`);
      }
    });

    if (fileErrors.length > 0) {
      showError(`Ошибки файлов:\n${fileErrors.join('\n')}`);
    }
    if (validFiles.length === 0) {
      event.target.value = '';
      return;
    }

    setIsUploadingDocs(true);
    try {
      for (const file of validFiles) {
        const res = await agentService.uploadDocumentByBotId(selectedBotId, file);
        if (res?.status === 'limit_error') {
          showError(
            `Лимит базы знаний превышен: план ${res.current_plan}, лимит ${res.limit}, уже ${res.current_count}, файл добавит ${res.new_chunks_count}`
          );
          break;
        }
        if (res?.status === 'duplicate') {
          showSuccess(`Файл ${file.name} уже загружен ранее (статус: ${res?.document_status || 'ready'})`);
          continue;
        }
        if (res?.status === 'reprocessing') {
          showSuccess(`Файл ${file.name} отправлен на повторную обработку`);
          continue;
        }
        showSuccess(`Файл ${file.name} принят к обработке`);
      }
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при загрузке документов');
    } finally {
      setIsUploadingDocs(false);
      event.target.value = '';
    }
  };

  const isValidPublicUrl = (value) => {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const handleUploadLink = async () => {
    const normalized = pendingLink.trim();
    if (!selectedBotId) {
      return;
    }
    if (!normalized) {
      showError('Введите ссылку для добавления');
      return;
    }
    if (!isValidPublicUrl(normalized)) {
      showError('Некорректная ссылка. Разрешены только публичные http/https URL');
      return;
    }

    setIsUploadingLink(true);
    try {
      const res = await agentService.uploadPublicLinkByBotId(selectedBotId, normalized);
      if (res?.status === 'limit_error') {
        showError(
          `Лимит базы знаний превышен: план ${res.current_plan}, лимит ${res.limit}, уже ${res.current_count}, ссылка добавит ${res.new_chunks_count}`
        );
        return;
      }
      if (res?.status === 'duplicate') {
        showSuccess(`Ссылка уже добавлена ранее (статус: ${res?.document_status || 'ready'})`);
        return;
      }
      showSuccess('Ссылка принята к обработке');
      setPendingLink('');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при добавлении ссылки');
    } finally {
      setIsUploadingLink(false);
    }
  };

  const handleLinkKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleUploadLink();
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!window.confirm('Удалить документ из базы знаний агента?')) {
      return;
    }
    try {
      await agentService.deleteDocumentById(docId);
      showSuccess('Документ удален');
      if (selectedBotId) {
        await loadAgentDetails(selectedBotId);
      }
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении документа');
    }
  };

  const handleCopyApiKey = async () => {
    const key = selectedAgent?.external_api_key;
    if (!key) {
      showError('API ключ не найден');
      return;
    }

    try {
      await navigator.clipboard.writeText(key);
      showSuccess('API ключ скопирован');
    } catch (error) {
      showError('Не удалось скопировать API ключ');
    }
  };

  const handleCopyWidgetSnippet = async () => {
    if (!selectedAgent?.external_api_key) {
      showError('API ключ не найден');
      return;
    }
    const origin = window.location.origin;
    const snippet = `<script src="${origin}/api/agents/external/widget.js" data-rsd-widget="1" data-api-base="${origin}" data-api-key="${selectedAgent.external_api_key}" data-position="bottom-right" data-title="Онлайн-консультант" data-theme="dark"></script>`;
    try {
      await navigator.clipboard.writeText(snippet);
      showSuccess('Сниппет виджета скопирован');
    } catch {
      showError('Не удалось скопировать сниппет виджета');
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!selectedBotId) return;
    if (!window.confirm('Вы точно хотите перевыпустить ключ? Нынешний ключ больше не будет активен.')) {
      return;
    }
    try {
      const updated = await agentService.regenerateExternalKey(selectedBotId);
      setSelectedAgent((prev) => ({ ...(prev || {}), ...updated }));
      showSuccess('API ключ перевыпущен');
    } catch (error) {
      showError(error?.message || 'Ошибка перевыпуска API ключа');
    }
  };

  const resetChannelModalFields = () => {
    setBotTokenDraft('');
    setMakePrimaryChannel(false);
    setUserbotApiId('');
    setUserbotApiHash('');
    setUserbotPhone('');
    setUserbotCode('');
    setUserbotPassword('');
    setUserbotAuthToken('');
    setUserbotSessionString('');
    setMaxBotTokenDraft('');
    setMaxUserbotTokenDraft('');
    setIsSendingUserbotCode(false);
    setIsVerifyingUserbotCode(false);
    setWhatsappUserbotPhone('');
    setWhatsappUserbotSessionString('');
    setWhatsappUserbotClientLabel('');
    setWhatsappUserbotMode('simple');
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotQrDataUrl('');
    whatsappUserbotLastAuthStatusRef.current = '';
    setIsSendingWhatsappUserbotCode(false);
    setIsVerifyingWhatsappUserbotCode(false);
    setIsWhatsappUserbotVerified(false);
    setWhatsappPhoneNumberId('');
    setWhatsappAccessToken('');
    setWhatsappBusinessAccountId('');
    setWhatsappVerifyToken('');
    setTelephonyPlatform(null);
    setTelephonyVoiceId('default');
    setTelephonyLanguage('ru-RU');
    setTelephonyRecordCalls(true);
    setTelephonyDisclaimerPlayed(true);
    setTelephonyRoutingExtension('');
    setTelephonyValidateStatus('');
    setTelephonyWebhookUrl('');
    setIsValidatingTelephony(false);
  };

  const buildTelephonyPayload = () => ({
    routing_extension: telephonyRoutingExtension.trim(),
    voice_id: telephonyVoiceId.trim() || 'default',
    language: telephonyLanguage.trim() || 'ru-RU',
    record_calls: telephonyRecordCalls,
    disclaimer_played: telephonyDisclaimerPlayed,
  });

  const handleValidateTelephony = async () => {
    const payload = buildTelephonyPayload();
    if (!/^\d{4}$/.test(payload.routing_extension)) {
      showError('Укажите добавочный номер из 4 цифр');
      return;
    }
    if (telephonyPlatform && !telephonyPlatform.platform_ready) {
      showError('Телефония платформы не настроена на сервере (.env)');
      return;
    }
    setIsValidatingTelephony(true);
    setTelephonyValidateStatus('');
    try {
      const res = await agentService.validateTelephonyChannel({
        routing_extension: payload.routing_extension,
      });
      setTelephonyValidateStatus(res?.message || 'Подключение проверено');
      showSuccess(res?.message || 'Voximplant: учётная запись доступна');
    } catch (error) {
      setTelephonyValidateStatus('');
      showError(error?.message || 'Ошибка проверки телефонии');
    } finally {
      setIsValidatingTelephony(false);
    }
  };

  const handleAddTelephonyChannel = async () => {
    if (!selectedBotId) return;
    if (hasTelephonyChannel) {
      showError('Телефония уже подключена. Удалите текущий канал, чтобы подключить заново.');
      return;
    }
    const payload = buildTelephonyPayload();
    if (!/^\d{4}$/.test(payload.routing_extension)) {
      showError('Укажите добавочный номер из 4 цифр');
      return;
    }
    if (telephonyPlatform && !telephonyPlatform.platform_ready) {
      showError('Телефония платформы не настроена на сервере (.env)');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addTelephonyChannel({
        agent_id: selectedBotId,
        ...buildTelephonyPayload(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      if (res?.webhook_url) {
        setTelephonyWebhookUrl(res.webhook_url);
      }
      showSuccess('Телефонный канал подключён');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении телефонии');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleUpdateTelephonyRouting = async () => {
    if (!selectedBotId) return;
    const ext = telephonyRoutingExtension.trim();
    if (!/^\d{4}$/.test(ext)) {
      showError('Добавочный должен состоять из 4 цифр');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.updateTelephonyRouting({
        agent_id: selectedBotId,
        routing_extension: ext,
      });
      const list = res?.channels || [];
      if (list.length) {
        setChannels(list);
        setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      }
      showSuccess('Маршрутизация телефонии обновлена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить маршрутизацию');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleCopyTelephonyWebhook = async () => {
    const url =
      telephonyWebhookUrl ||
      telephonyChannel?.telephony_webhook_url ||
      '';
    if (!url) {
      showError('Webhook URL пока недоступен');
      return;
    }
    try {
      await copyTextToClipboard(url);
      showSuccess('Webhook URL скопирован');
    } catch {
      showError('Не удалось скопировать URL');
    }
  };

  const refreshChannels = async (botId) => {
    const data = await agentService.getChannels(botId);
    const list = data?.channels || [];
    setChannels(list);
    setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
    return list;
  };

  const handleOpenChannelsModal = async () => {
    if (!selectedBotId) {
      showError('Сначала выберите агента');
      return;
    }
    resetChannelModalFields();
    setChannelModalTab(selectedAgent?.template_type === 'sales_manager' ? 'userbot' : 'bot');
    setIsChannelsModalOpen(true);
    setIsLoadingChannels(true);
    try {
      const [list, platform] = await Promise.all([
        refreshChannels(selectedBotId),
        agentService.getTelephonyPlatformConfig().catch(() => null),
      ]);
      if (platform) {
        setTelephonyPlatform(platform);
      }
      const tel = findTelephonyChannel(list);
      if (tel?.telephony_webhook_url) {
        setTelephonyWebhookUrl(tel.telephony_webhook_url);
      }
      const routing = tel?.telephony_routing;
      if (routing) {
        setTelephonyRoutingExtension(routing.routing_extension || '');
      }
    } catch (error) {
      showError(error?.message || 'Не удалось загрузить каналы подключения');
    } finally {
      setIsLoadingChannels(false);
    }
  };

  const handleCloseChannelsModal = () => {
    setIsChannelsModalOpen(false);
    resetChannelModalFields();
  };

  const isSalesManagerTemplate = selectedAgent?.template_type === 'sales_manager';
  const isQATemplate = String(selectedAgent?.template_type || 'qa').trim().toLowerCase() === 'qa';
  const isCrmAdminTemplate = selectedAgent?.template_type === 'crm_admin';
  const telephonyChannel = useMemo(() => findTelephonyChannel(channels), [channels]);
  const hasTelephonyChannel = Boolean(telephonyChannel);

  useEffect(() => {
    const cfg = getTemplateConfig(selectedAgent);
    setAdminWaitlistEnabled(cfg.waitlist_enabled !== false);
    setAdminReminderEnabled(cfg.reminder_enabled !== false);
    setAdminReminderOffsets(toCsvOffsets(cfg.reminder_offsets_hours));
    setAdminManualConfirmationEnabled(Boolean(cfg.manual_confirmation_enabled));
    setAdminManualConfirmationPriceMinor(String(Number(cfg.manual_confirmation_price_minor) || 15000));
    setAdminManualConfirmationDurationMinutes(
      String(Number(cfg.manual_confirmation_duration_minutes) || 120)
    );
    setAdminPaidBookingEnabled(Boolean(cfg.paid_booking_enabled));
    setAdminYookassaApiKey('');
    setAdminHasYookassaApiKey(Boolean(selectedAgent?.has_booking_payment_api_key));
    setSalesProductName(String(cfg.sales_product_name || ''));
    setSalesOfferType(String(cfg.sales_offer_type || ''));
    setSalesUsp(String(cfg.sales_usp || ''));
    setSalesWorkflowCompletionMode(
      cfg.workflow_completion_mode === 'continue_dialog' ? 'continue_dialog' : 'auto_finish_on_signal'
    );
    setSalesLeadScoreScale(String(Number(cfg.lead_score_scale) === 10 ? 10 : 100));
    setSalesLeadGenerationEnabled(cfg.lead_generation_enabled !== false);
    setSalesNeuroCommentingEnabled(Boolean(cfg.neuro_commenting_enabled));
    setSalesLiveChatSimulationEnabled(Boolean(cfg.live_chat_simulation_enabled));
    setSalesTriggerWords(normalizeSalesTriggerWordsList(cfg.trigger_words));
    setSalesTriggerWordDraft('');

    const av = cfg.agent_availability;
    if (av && typeof av === 'object') {
      setAgentAvailAlwaysOn(av.always_on !== false);
      setAgentAvailTimezone(String(av.timezone || getBrowserTimezoneSafe()).trim() || 'Europe/Moscow');
      setAgentAvailWeekdays(normalizeWeekdaysFromConfig(av.weekdays));
    } else {
      setAgentAvailAlwaysOn(true);
      setAgentAvailTimezone(getBrowserTimezoneSafe());
      setAgentAvailWeekdays(buildDefaultAgentAvailabilityWeekdays());
    }
  }, [selectedAgent]);

  useEffect(() => {
    if (!isChannelsModalOpen || !isSalesManagerTemplate) return;
    if (channelModalTab !== 'userbot') {
      setChannelModalTab('userbot');
    }
  }, [channelModalTab, isChannelsModalOpen, isSalesManagerTemplate]);

  const agentAvailabilityTimezoneOptions = useMemo(() => {
    const browser = getBrowserTimezoneSafe();
    const ordered = [...new Set([browser, agentAvailTimezone, ...COMMON_AGENT_TIMEZONES])];
    return ordered.map((tz) => ({ value: tz, label: tz }));
  }, [agentAvailTimezone]);

  const handleSaveAgentAvailability = async () => {
    if (!selectedBotId || !selectedAgent) return;
    if (!agentAvailAlwaysOn) {
      const anyDay = agentAvailWeekdays.some((d) => d.enabled);
      if (!anyDay) {
        showError('Включите хотя бы один день недели или вернитесь в режим 24/7');
        return;
      }
    }
    const currentConfig = getTemplateConfig(selectedAgent);
    const nextBlock = agentAvailAlwaysOn
      ? {
          always_on: true,
          timezone: agentAvailTimezone.trim() || 'Europe/Moscow',
        }
      : {
          always_on: false,
          timezone: agentAvailTimezone.trim() || 'Europe/Moscow',
          weekdays: agentAvailWeekdays.map((d) => ({
            enabled: Boolean(d.enabled),
            start: d.start,
            end: d.end,
          })),
        };
    const nextConfig = {
      ...currentConfig,
      agent_availability: nextBlock,
    };
    setIsSavingAgentAvailability(true);
    try {
      await agentService.update(selectedBotId, { template_config: nextConfig });
      setSelectedAgent((prev) => (prev ? { ...prev, template_config: nextConfig } : prev));
      showSuccess('Режим работы ассистента сохранён');
    } catch (error) {
      showError(error?.message || 'Не удалось сохранить режим работы');
    } finally {
      setIsSavingAgentAvailability(false);
    }
  };

  const handleToggleAgentAvailabilityDay = (index, enabled) => {
    setAgentAvailWeekdays((prev) =>
      prev.map((row, i) => (i === index ? { ...row, enabled: Boolean(enabled) } : row))
    );
  };

  const handleAgentAvailabilityTimeChange = (index, field, value) => {
    setAgentAvailWeekdays((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
  };

  const handlePresetOfficeWeek = () => {
    setAgentAvailWeekdays(buildDefaultAgentAvailabilityWeekdays());
  };

  const handleRemoveChannel = async (connectionId) => {
    if (!selectedBotId) return;
    if (!window.confirm('Удалить этот канал подключения?')) return;
    setIsSavingChannel(true);
    try {
      const res = await agentService.removeChannel({ agent_id: selectedBotId, connection_id: connectionId });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Канал успешно удален');
      await loadAgentDetails(selectedBotId);
    } catch (error) {
      showError(error?.message || 'Ошибка при удалении канала');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddBotChannel = async () => {
    if (!selectedBotId) return;
    if (!botTokenDraft.trim()) {
      showError('Введите API ключ Telegram бота');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addBotChannel({
        agent_id: selectedBotId,
        bot_token: botTokenDraft.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Telegram бот подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении Telegram бота');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleRequestUserbotCode = async () => {
    if (!userbotApiId.trim() || !userbotApiHash.trim() || !userbotPhone.trim()) {
      showError('Заполните API ID, API hash и номер телефона');
      return;
    }
    setIsSendingUserbotCode(true);
    try {
      const response = await agentService.requestUserbotCode({
        api_id: Number(userbotApiId),
        api_hash: userbotApiHash.trim(),
        phone_number: userbotPhone.trim(),
      });
      setUserbotAuthToken(response?.auth_token || '');
      setUserbotSessionString('');
      showSuccess('Код подтверждения отправлен в Telegram');
    } catch (error) {
      showError(error?.message || 'Не удалось отправить код Telegram');
    } finally {
      setIsSendingUserbotCode(false);
    }
  };

  const handleVerifyUserbotCode = async () => {
    if (!userbotAuthToken) {
      showError('Сначала отправьте код подтверждения');
      return;
    }
    if (!userbotCode.trim()) {
      showError('Введите код из Telegram');
      return;
    }
    setIsVerifyingUserbotCode(true);
    try {
      const response = await agentService.verifyUserbotCode({
        auth_token: userbotAuthToken,
        code: userbotCode.trim(),
        password: userbotPassword.trim() || undefined,
      });
      setUserbotSessionString(response?.session_string || '');
      showSuccess('Код подтвержден, можно подключать userbot');
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить код');
    } finally {
      setIsVerifyingUserbotCode(false);
    }
  };

  const handleAddUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!userbotApiId.trim() || !userbotApiHash.trim()) {
      showError('Заполните API ID и API hash');
      return;
    }
    if (!userbotSessionString.trim()) {
      showError('Сначала подтвердите код Telegram и получите session string');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addUserbotChannel({
        agent_id: selectedBotId,
        api_id: Number(userbotApiId),
        api_hash: userbotApiHash.trim(),
        session_string: userbotSessionString.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('Telegram userbot подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении userbot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddMaxBotChannel = async () => {
    if (!selectedBotId) return;
    if (!maxBotTokenDraft.trim()) {
      showError('Введите MAX bot token');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addMaxBotChannel({
        agent_id: selectedBotId,
        bot_token: maxBotTokenDraft.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('MAX bot канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении MAX bot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddMaxUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!maxUserbotTokenDraft.trim()) {
      showError('Введите MAX token');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addMaxUserbotChannel({
        agent_id: selectedBotId,
        max_token: maxUserbotTokenDraft.trim(),
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('MAX userbot канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении MAX userbot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddWhatsAppBusinessApiChannel = async () => {
    if (!selectedBotId) return;
    if (!whatsappPhoneNumberId.trim()) {
      showError('Введите WhatsApp Phone Number ID');
      return;
    }
    if (!whatsappAccessToken.trim()) {
      showError('Введите WhatsApp Access Token');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addWhatsAppBusinessApiChannel({
        agent_id: selectedBotId,
        phone_number_id: whatsappPhoneNumberId.trim(),
        access_token: whatsappAccessToken.trim(),
        business_account_id: whatsappBusinessAccountId.trim() || undefined,
        verify_token: whatsappVerifyToken.trim() || undefined,
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('WhatsApp Business API канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении WhatsApp Business API');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const handleAddWhatsAppUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!whatsappUserbotPhone.trim()) {
      showError('Введите номер WhatsApp userbot');
      return;
    }
    if (whatsappUserbotMode === 'simple') {
      if (!whatsappUserbotSessionString.trim() || !isWhatsappUserbotVerified) {
        showError('Сначала подтвердите код и инициализируйте WhatsApp userbot-сессию');
        return;
      }
    } else if (!whatsappUserbotSessionString.trim()) {
      showError('Введите session string WhatsApp userbot');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addWhatsAppUserbotChannel({
        agent_id: selectedBotId,
        phone_number: whatsappUserbotPhone.trim(),
        session_string: whatsappUserbotSessionString.trim(),
        client_label: whatsappUserbotClientLabel.trim() || undefined,
        make_primary: makePrimaryChannel,
      });
      const list = res?.channels || [];
      setChannels(list);
      setSelectedAgent((prev) => (prev ? { ...prev, channels: list } : prev));
      showSuccess('WhatsApp userbot канал подключен');
      await loadAgentDetails(selectedBotId);
      resetChannelModalFields();
    } catch (error) {
      showError(error?.message || 'Ошибка при подключении WhatsApp userbot');
    } finally {
      setIsSavingChannel(false);
    }
  };

  const switchWhatsappUserbotMode = (mode) => {
    setWhatsappUserbotMode(mode);
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotQrDataUrl('');
    setWhatsappUserbotSessionString('');
    setIsWhatsappUserbotVerified(false);
    whatsappUserbotLastAuthStatusRef.current = '';
  };

  const handleRequestWhatsappUserbotCode = async () => {
    if (!whatsappUserbotPhone.trim()) {
      showError('Введите номер WhatsApp userbot');
      return;
    }
    setIsSendingWhatsappUserbotCode(true);
    try {
      const response = await agentService.requestWhatsAppUserbotCode({
        phone_number: whatsappUserbotPhone.trim(),
      });
      setWhatsappUserbotAuthToken(response?.auth_token || '');
      setWhatsappUserbotQrDataUrl(response?.qr_data_url || '');
      setWhatsappUserbotSessionString('');
      setIsWhatsappUserbotVerified(false);
      whatsappUserbotLastAuthStatusRef.current = '';
      showSuccess(
        response?.hint || 'QR готов. Отсканируйте его в WhatsApp и затем нажмите «Проверить подключение».'
      );
    } catch (error) {
      showError(error?.message || 'Не удалось запросить QR-код WhatsApp');
    } finally {
      setIsSendingWhatsappUserbotCode(false);
    }
  };

  const handleVerifyWhatsappUserbotCode = async () => {
    if (!whatsappUserbotAuthToken) {
      showError('Сначала запросите код подтверждения WhatsApp');
      return;
    }
    setIsVerifyingWhatsappUserbotCode(true);
    try {
      const response = await agentService.verifyWhatsAppUserbotCode({
        auth_token: whatsappUserbotAuthToken,
      });
      setWhatsappUserbotSessionString(response?.session_string || '');
      if (response?.phone_number) {
        setWhatsappUserbotPhone(response.phone_number);
      }
      setIsWhatsappUserbotVerified(true);
      showSuccess('WhatsApp userbot успешно инициализирован');
    } catch (error) {
      setIsWhatsappUserbotVerified(false);
      showError(error?.message || 'Не удалось подтвердить код WhatsApp');
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

  useEffect(() => {
    if (!isAuthenticated) return;
    const list = agents || [];
    if (list.length > 0 && !selectedBotId) {
      loadAgentDetails(list[0].id);
    }
  }, [agents, isAuthenticated, selectedBotId]);

  const selectedAgentName = useMemo(() => {
    if (!selectedAgent) return '';
    return selectedAgent.bot_username ? `@${selectedAgent.bot_username}` : `Агент #${selectedAgent.id}`;
  }, [selectedAgent]);
  const isWidgetSupportedTemplate = WIDGET_TEMPLATE_TYPES.has(
    String(selectedAgent?.template_type || 'qa').trim().toLowerCase()
  );
  const isTelephonyVoicePreviewTemplate = TELEPHONY_VOICE_PREVIEW_TEMPLATES.has(
    String(selectedAgent?.template_type || 'qa').trim().toLowerCase()
  );

  if (isLoading && isAuthenticated) {
    return <Loading message="Загрузка агентов..." />;
  }

  const displayAgents = agents || [];
  const showEmptyAgentsList = !isAuthenticated || displayAgents.length === 0;

  return (
    <div className="agents-page-content">
      <section className="agents-section">
        <div className="section-header">
          <h2 className="section-title">Ваши агенты:</h2>
          <button type="button" className="btn btn-black btn-add" onClick={handleCreateAgent}>
            + Новый агент
          </button>
        </div>

        {showEmptyAgentsList ? (
          <AgentsEmptyState
            message={AGENTS_EMPTY_MESSAGE}
            ctaLabel={AGENTS_EMPTY_CTA}
            onCtaClick={handleCreateAgent}
          />
        ) : (
          <div className="agents-layout">
            <div className="agents-list">
              {displayAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  isSelected={selectedBotId === agent.id}
                  onManage={loadAgentDetails}
                  onDelete={handleDeleteAgent}
                  onToggle={handleToggleAgent}
                />
              ))}
            </div>

            <div className="agent-management-card">
              {!selectedAgent || isLoadingDetails ? (
                <div className="agent-management-empty">
                  {isLoadingDetails ? 'Загрузка карточки агента...' : 'Выберите агента для управления'}
                </div>
              ) : (
                <>
                  <div className="agent-management-header">
                    <h3>{selectedAgentName}</h3>
                    <p>ID: {selectedAgent.id}</p>
                    {telephonyChannel ? (
                      <p
                        className="agent-telephony-badge title-with-demo-badge"
                        title={telephonyChannel.external_id}
                      >
                        Телефония · {telephonyChannel.external_id}
                        <DemoBadge />
                      </p>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-black analytics-btn"
                      onClick={handleOpenDetailedAnalytics}
                    >
                     Дашборд агента
                    </button>
                  </div>

                  {isTelephonyVoicePreviewTemplate ? (
                    <div className="agent-management-block">
                      <TitleWithDemoBadge as="h4" className="agent-form-channel-title">
                        Голосовой тест (в браузере)
                      </TitleWithDemoBadge>
                      <TelephonyVoicePreview
                        agentId={selectedAgent.id}
                        hasTelephonyChannel={hasTelephonyChannel}
                        showError={showError}
                        showSuccess={showSuccess}
                      />
                    </div>
                  ) : null}

                  <div className="agent-management-block">
                    <label>API ключ для внешних интеграций</label>
                    <div className="api-key-row">
                      <button
                        className="btn btn-black"
                        onClick={handleCopyApiKey}
                        title="Скопировать API ключ"
                        aria-label="Copy API key"
                      >
                        Скопировать API ключ
                      </button>
                      <button
                        className="btn btn-outline"
                        onClick={handleRegenerateApiKey}
                        title="Перевыпустить API ключ"
                        aria-label="Regenerate API key"
                      >
                        Перевыпустить API ключ
                      </button>
                      {isWidgetSupportedTemplate ? (
                        <button
                          className="btn btn-black api-key-row__full-width"
                          onClick={handleCopyWidgetSnippet}
                          title="Скопировать script сниппет"
                          aria-label="Copy widget snippet"
                        >
                          Скопировать сниппет виджета
                        </button>
                      ) : null}
                    </div>
                  </div>

                  <div className="agent-management-block">
                    <div className="docs-header-row">
                      <label>Каналы подключения</label>
                      <button type="button" className="btn btn-outline" onClick={handleOpenChannelsModal}>
                        Управлять каналами
                      </button>
                    </div>
                    {channels.length === 0 ? (
                      <p className="docs-empty">Каналы пока не подключены</p>
                    ) : (
                      <div className="docs-list-web">
                        {channels.map((channel) => (
                          <div key={channel.id} className="doc-row">
                            <div className="doc-meta">
                              <span className="doc-name">
                                {channelLabel(channel)} · {channel.external_id}
                                {channel.provider === TELEPHONY_PROVIDER ? <DemoBadge /> : null}
                              </span>
                              <span className={`doc-status ${channel.is_primary ? 'doc-status--ready' : ''}`}>
                                {channel.is_primary ? 'основной' : 'дополнительный'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="agent-management-block agent-availability-block">
                    <h4 className="agent-form-channel-title">Время работы ассистента</h4>
                    <p className="agent-availability-hint">
                      Время проверяется в выбранном часовом поясе (IANA), независимо от того, где физически
                      расположен сервер. По умолчанию ассистент доступен круглосуточно.
                    </p>
                    <FeatureToggle
                      checked={agentAvailAlwaysOn}
                      onChange={(next) => setAgentAvailAlwaysOn(Boolean(next))}
                      disabled={isSavingAgentAvailability}
                      title="Круглосуточный режим (24/7)"
                      description="Выключите, чтобы вне заданного расписания входящие сообщения не обрабатывались и не получали ответа."
                      helpText="Вне окна сообщение не попадает в аналитику и не вызывает LLM; пользователь не получает ответ. Подписка и блокировки пользователя проверяются как обычно."
                    />
                    <label htmlFor="agent_avail_timezone" className="mt-input">
                      Часовой пояс расписания
                    </label>
                    <CustomSelect
                      id="agent_avail_timezone"
                      name="agent_avail_timezone"
                      value={agentAvailTimezone}
                      onChange={(event) => setAgentAvailTimezone(event.target.value)}
                      options={agentAvailabilityTimezoneOptions}
                      disabled={isSavingAgentAvailability}
                    />
                    {!agentAvailAlwaysOn ? (
                      <div className="agent-availability-weeksheet">
                        <div className="agent-availability-weeksheet-header">
                          <span className="agent-availability-weeksheet-title">Расписание по дням</span>
                          <button
                            type="button"
                            className="btn btn-outline btn-compact"
                            onClick={handlePresetOfficeWeek}
                            disabled={isSavingAgentAvailability}
                          >
                            Пн–Пт 9–18
                          </button>
                        </div>
                        <div className="agent-availability-weekdays" role="list">
                          {agentAvailWeekdays.map((row, index) => (
                            <div
                              key={`${AGENT_AVAILABILITY_WEEKDAY_LABELS[index]}-${String(index)}`}
                              className={`agent-availability-day-row ${row.enabled ? 'agent-availability-day-row--on' : ''}`}
                              role="listitem"
                            >
                              <div className="agent-availability-day-toggle-wrap">
                                <FeatureToggleCompact
                                  checked={row.enabled}
                                  onChange={(next) => handleToggleAgentAvailabilityDay(index, next)}
                                  disabled={isSavingAgentAvailability}
                                  title={AGENT_AVAILABILITY_WEEKDAY_LABELS[index]}
                                />
                              </div>
                              <div className="agent-availability-day-times">
                                <TimeDigitsField
                                  value={row.start}
                                  onChange={(next) =>
                                    handleAgentAvailabilityTimeChange(index, 'start', next)
                                  }
                                  disabled={isSavingAgentAvailability || !row.enabled}
                                  ariaLabel={`Начало, ${AGENT_AVAILABILITY_WEEKDAY_LABELS[index]}`}
                                />
                                <span className="agent-availability-time-sep" aria-hidden="true">
                                  —
                                </span>
                                <TimeDigitsField
                                  value={row.end}
                                  onChange={(next) =>
                                    handleAgentAvailabilityTimeChange(index, 'end', next)
                                  }
                                  disabled={isSavingAgentAvailability || !row.enabled}
                                  ariaLabel={`Конец, ${AGENT_AVAILABILITY_WEEKDAY_LABELS[index]}`}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="agent-availability-footnote">
                          Допускаются «ночные» окна (например 22:00—06:00): конец раньше начала означает
                          переход через полночь.
                        </p>
                      </div>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleSaveAgentAvailability}
                      disabled={isSavingAgentAvailability}
                    >
                      {isSavingAgentAvailability ? 'Сохранение...' : 'Сохранить время работы'}
                    </button>
                  </div>

                  <div className="agent-management-block">
                    {isCrmAdminTemplate ? (
                      <>
                        <h4 className="agent-form-channel-title">Дополнительные фичи</h4>
                        <FeatureToggle
                          checked={adminWaitlistEnabled}
                          onChange={setAdminWaitlistEnabled}
                          disabled={isSavingTemplateConfig}
                          title="Включить waitlist с авто-подбором окон"
                          helpText="Когда включено, агент сможет предлагать клиентам окна из waitlist при освобождении слотов."
                        />
                        <FeatureToggle
                          checked={adminReminderEnabled}
                          onChange={setAdminReminderEnabled}
                          disabled={isSavingTemplateConfig}
                          title="Включить напоминания о визите"
                          helpText="При включении отправляются напоминания клиенту по расписанию, заданному в offsets."
                        />
                        <div className="admin-template-field">
                          <label htmlFor="admin_reminder_offsets_hours">
                            Напоминания за (часы до визита, через запятую):
                          </label>
                          <input
                            id="admin_reminder_offsets_hours"
                            className="input-main"
                            value={adminReminderOffsets}
                            onChange={(event) => setAdminReminderOffsets(event.target.value)}
                            placeholder="24,2"
                            disabled={isSavingTemplateConfig}
                          />
                        </div>
                        <FeatureToggle
                          checked={adminManualConfirmationEnabled}
                          onChange={setAdminManualConfirmationEnabled}
                          disabled={isSavingTemplateConfig}
                          title="Ручное подтверждение дорогих/долгих услуг"
                          helpText="Агент будет запрашивать ручное подтверждение при превышении ценового порога или длительности услуги."
                        />
                        <label htmlFor="admin_manual_confirmation_price_minor" className="mt-input">
                          Порог цены (minor):
                        </label>
                        <input
                          id="admin_manual_confirmation_price_minor"
                          type="number"
                          min="0"
                          className="input-main"
                          value={adminManualConfirmationPriceMinor}
                          onChange={(event) => setAdminManualConfirmationPriceMinor(event.target.value)}
                          disabled={isSavingTemplateConfig}
                        />
                        <label htmlFor="admin_manual_confirmation_duration_minutes" className="mt-input">
                          Порог длительности (мин):
                        </label>
                        <input
                          id="admin_manual_confirmation_duration_minutes"
                          type="number"
                          min="1"
                          className="input-main"
                          value={adminManualConfirmationDurationMinutes}
                          onChange={(event) => setAdminManualConfirmationDurationMinutes(event.target.value)}
                          disabled={isSavingTemplateConfig}
                        />
                        <FeatureToggle
                          checked={adminPaidBookingEnabled}
                          onChange={setAdminPaidBookingEnabled}
                          disabled={isSavingTemplateConfig}
                          title="Платная бронь"
                          helpText="При включении агент сначала отправляет ссылку на оплату, и только после успешной оплаты подтверждает бронь."
                        />
                        {adminPaidBookingEnabled ? (
                          <div className="admin-template-field">
                            <label htmlFor="admin_yookassa_api_key">
                              API ключ ЮKassa (shop_id:secret_key):
                            </label>
                            <input
                              id="admin_yookassa_api_key"
                              type="password"
                              className="input-main"
                              value={adminYookassaApiKey}
                              onChange={(event) => setAdminYookassaApiKey(event.target.value)}
                              placeholder={adminHasYookassaApiKey ? 'Ключ уже сохранен. Введите новый для замены' : '123456:live_xxxxx'}
                              disabled={isSavingTemplateConfig}
                              autoComplete="off"
                            />
                          </div>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleSaveAdminTemplateConfig}
                          disabled={isSavingTemplateConfig}
                        >
                          {isSavingTemplateConfig ? 'Сохранение...' : 'Сохранить настройки Администратора'}
                        </button>
                      </>
                    ) : null}
                    {isSalesManagerTemplate ? (
                      <>
                        <h4 className="agent-form-channel-title">Конфигурация Sales Manager</h4>
                        <label htmlFor="sales_product_name_edit">Продукт:</label>
                        <input
                          id="sales_product_name_edit"
                          type="text"
                          className="input-main"
                          value={salesProductName}
                          onChange={(event) => setSalesProductName(event.target.value)}
                          placeholder="Например: ИИ-автоматизация продаж RSD AI"
                          disabled={isSavingTemplateConfig}
                        />
                        <label htmlFor="sales_offer_type_edit" className="mt-input">
                          Что продаете (категория):
                        </label>
                        <input
                          id="sales_offer_type_edit"
                          type="text"
                          className="input-main"
                          value={salesOfferType}
                          onChange={(event) => setSalesOfferType(event.target.value)}
                          placeholder="Например: SaaS, курсы, консалтинг, внедрение под ключ"
                          disabled={isSavingTemplateConfig}
                        />
                        <label htmlFor="sales_usp_edit" className="mt-input">
                          УТП (опционально):
                        </label>
                        <textarea
                          id="sales_usp_edit"
                          rows="3"
                          className="input-main textarea"
                          value={salesUsp}
                          onChange={(event) => setSalesUsp(event.target.value)}
                          placeholder="Например: подключение за 5 минут, быстрая интеграция с CRM, единый дашборд"
                          disabled={isSavingTemplateConfig}
                        />
                        <label htmlFor="sales_workflow_completion_mode_edit" className="mt-input">
                          Завершение диалога:
                        </label>
                        <CustomSelect
                          id="sales_workflow_completion_mode_edit"
                          name="sales_workflow_completion_mode_edit"
                          value={salesWorkflowCompletionMode}
                          onChange={(event) => setSalesWorkflowCompletionMode(event.target.value)}
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
                          disabled={isSavingTemplateConfig}
                        />
                        <label htmlFor="sales_lead_score_scale_edit" className="mt-input">
                          Шкала оценки лида:
                        </label>
                        <CustomSelect
                          id="sales_lead_score_scale_edit"
                          name="sales_lead_score_scale_edit"
                          value={salesLeadScoreScale}
                          onChange={(event) => setSalesLeadScoreScale(event.target.value)}
                          options={[
                            { value: '100', label: '0-100 (детальная)' },
                            { value: '10', label: '0-10 (компактная)' },
                          ]}
                          disabled={isSavingTemplateConfig}
                        />
                        <FeatureToggle
                          checked={salesLeadGenerationEnabled}
                          onChange={(enabled) => handleToggleSalesActivity('lead_generation_enabled', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Лидогенерация"
                          description="Основной контур sales_manager: анализ чатов, отлов лидов и продажа."
                          helpText="Если выключить, агент прекращает выполнение основной задачи sales_manager. Если одновременно выключить Лидогенерацию, Нейрокомментинг и Имитацию живого общения, агент будет автоматически выключен."
                        />
                        <FeatureToggle
                          checked={salesNeuroCommentingEnabled}
                          onChange={(enabled) => handleToggleSalesActivity('neuro_commenting_enabled', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Нейрокомментинг"
                          description="Юзербот комментирует посты в каналах аккаунта, где доступен как участник."
                          helpText="К каждому новому посту формируется короткий LLM-комментарий без фильтра по триггер-словам и без квалификации целевого лида. Для групп и чатов по-прежнему действует список триггер-слов ниже (лидогенерация и имитация общения)."
                        />
                        <FeatureToggle
                          checked={salesLiveChatSimulationEnabled}
                          onChange={(enabled) => handleToggleSalesActivity('live_chat_simulation_enabled', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Имитация живого общения"
                          description="Юзербот периодически включается в обсуждения по триггер-словам из списка ниже."
                          helpText="Когда включено, юзербот может периодически вступать в разговор в чатах и отправлять 2–3 сообщения за одно включение; сообщение учитывается только если совпало хотя бы с одним триггер-словом."
                        />
                        <div className="sales-trigger-words-block">
                          <label htmlFor="sales_trigger_word_draft" className="sales-trigger-words-label">
                            Триггер-слова (лидогенерация и имитация живого общения)
                          </label>
                          <p className="sales-trigger-words-hint">
                            Сообщения в группах проходят дальше к проверке целевого лида только если текст содержит
                            совпадение с одним из слов (поиск по подстроке внутри слова). На каналы и нейрокомментинг
                            этот список не распространяется.
                          </p>
                          <ul className="sales-trigger-words-list">
                            {salesTriggerWords.map((word) => (
                              <li key={word} className="sales-trigger-word-row">
                                <span className="sales-trigger-word-text">{word}</span>
                                <button
                                  type="button"
                                  className="sales-trigger-word-remove"
                                  onClick={() => handleRemoveSalesTriggerWord(word)}
                                  disabled={isSavingTemplateConfig}
                                >
                                  Удалить
                                </button>
                              </li>
                            ))}
                          </ul>
                          <div className="sales-trigger-word-add-row">
                            <input
                              id="sales_trigger_word_draft"
                              type="text"
                              className="input-main"
                              value={salesTriggerWordDraft}
                              onChange={(event) => setSalesTriggerWordDraft(event.target.value)}
                              onKeyDown={handleSalesTriggerWordDraftKeyDown}
                              placeholder="Новое слово или корень"
                              disabled={isSavingTemplateConfig}
                              maxLength={64}
                            />
                            <button
                              type="button"
                              className="btn btn-black sales-trigger-word-add-btn"
                              onClick={handleAddSalesTriggerWord}
                              disabled={
                                isSavingTemplateConfig
                                || !salesTriggerWordDraft.trim()
                                || salesTriggerWords.length >= 30
                              }
                            >
                              Добавить
                            </button>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleSaveSalesTemplateConfig}
                          disabled={isSavingTemplateConfig}
                        >
                          {isSavingTemplateConfig ? 'Сохранение...' : 'Сохранить настройки Sales Manager'}
                        </button>
                      </>
                    ) : null}
                    <FeatureToggle
                      checked={isPortraitFeatureEnabled(selectedAgent)}
                      onChange={handleTogglePortraitFeature}
                      disabled={isSavingPortraitFeature}
                      title="Включить функцию «Портрет чата»"
                      helpText="Когда включено, система обновляет портрет клиента и использует его в ответах."
                    />
                    <FeatureToggle
                      checked={isSmartSearchEnabled(selectedAgent)}
                      onChange={handleToggleSmartSearch}
                      disabled={isSavingSmartSearch}
                      title="Умный поиск"
                      description="ON: LLM формирует RAG-запросы. OFF: в RAG отправляется исходный запрос и извлекается 6 чанков."
                      helpText="Управляет логикой поиска в базе знаний: LLM-планирование запросов или прямой поиск по исходному сообщению."
                    />
                    {isQATemplate ? (
                      <FeatureToggle
                        checked={isChatFreezeEnabled(selectedAgent)}
                        onChange={handleToggleChatFreeze}
                        disabled={isSavingChatFreeze}
                        title="Заморозка чата"
                        description="Авто-передача диалога владельцу при неуверенном ответе агента."
                        helpText="Доступно только для шаблона Консультант (QA). Если включено, агент может пометить диалог как требующий владельца и временно заморозить чат для пользователя."
                      />
                    ) : null}
                    <FeatureToggle
                      checked={isStartProcessingEnabled(selectedAgent)}
                      onChange={handleToggleStartProcessing}
                      disabled={isSavingStartProcessing}
                      title="Обработка /start"
                      description="ON: /start отправляется в LLM. OFF: отправляется дефолтное/пользовательское приветствие."
                      helpText="По умолчанию выключено: команда /start вернет текст приветствия. Включите, чтобы /start обрабатывался как обычное сообщение пользователя."
                    />
                  </div>

                  <div className="agent-management-block">
                    <label htmlFor="system_prompt">Системный промпт</label>
                    <textarea
                      id="system_prompt"
                      rows="6"
                      className="input-main textarea"
                      value={systemPromptDraft}
                      onChange={(e) => setSystemPromptDraft(e.target.value)}
                    />
                    <button
                      className="btn btn-black"
                      onClick={handleSaveSystemPrompt}
                      disabled={isSavingPrompt}
                    >
                      {isSavingPrompt ? 'Сохранение...' : 'Сохранить промпт'}
                    </button>
                    <button
                      className="btn btn-black"
                      onClick={handleAiImprovePrompt}
                      disabled={isGeneratingPrompt}
                    >
                      {isGeneratingPrompt ? 'ИИ улучшает...' : 'Улучшить промпт ИИ'}
                    </button>
                  </div>

                  <div className="agent-management-block">
                    <label htmlFor="welcome_message">Приветственное сообщение (/start)</label>
                    <textarea
                      id="welcome_message"
                      rows="3"
                      className="input-main textarea"
                      value={welcomeDraft}
                      onChange={(e) => setWelcomeDraft(e.target.value)}
                      placeholder="Введите приветствие или оставьте пустым"
                    />
                    <button
                      className="btn btn-black"
                      onClick={handleSaveWelcomeMessage}
                      disabled={isSavingWelcome}
                    >
                      {isSavingWelcome ? 'Сохранение...' : 'Сохранить приветствие'}
                    </button>
                    <button
                      className="btn btn-black"
                      onClick={handleAiGenerateWelcome}
                      disabled={isGeneratingWelcome}
                    >
                      {isGeneratingWelcome ? 'ИИ генерирует...' : 'Сгенерировать приветствие ИИ'}
                    </button>
                  </div>

                  <div className="agent-management-block">
                    <div className="docs-header-row">
                      <label>База знаний (документы и ссылки)</label>
                      <label className="btn btn-black docs-upload-btn">
                        {isUploadingDocs ? 'Загрузка...' : '+ Добавить файлы'}
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.doc,.docx,.txt"
                          onChange={handleUploadDocuments}
                          disabled={isUploadingDocs}
                          hidden
                        />
                      </label>
                    </div>
                    <div className="kb-link-row">
                      <input
                        type="url"
                        className="input-main"
                        value={pendingLink}
                        onChange={(e) => setPendingLink(e.target.value)}
                        onKeyDown={handleLinkKeyDown}
                        placeholder="https://example.com/article"
                        disabled={isUploadingLink}
                      />
                      <button
                        type="button"
                        className="btn btn-black"
                        onClick={handleUploadLink}
                        disabled={isUploadingLink}
                      >
                        {isUploadingLink ? 'Добавление...' : '+ Добавить ссылку'}
                      </button>
                    </div>
                    <p className="docs-empty">Ссылка обрабатывается один раз и не обновляется автоматически</p>
                    {documents.length === 0 ? (
                      <p className="docs-empty">Документы не добавлены</p>
                    ) : (
                      <div className="docs-list-web">
                        {documents.map((doc) => (
                          <div key={`${doc.id}-${linkIdentity(doc.file_name || '')}`} className="doc-row">
                            <div className="doc-meta">
                              <span className="doc-name">{doc.file_name}</span>
                              <span className={`doc-status doc-status--${doc.status}`}>{doc.status}</span>
                            </div>
                            <button
                              className="delete-btn"
                              onClick={() => handleDeleteDocument(doc.id)}
                              aria-label="Delete document"
                              title="Удалить документ"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </section>

      {isChannelsModalOpen && (
        <div className="auth-modal-backdrop channels-modal-backdrop">
          <div className="auth-modal channels-modal">
            <h3 className="auth-modal-title">Управление каналами подключения</h3>
            {isLoadingChannels ? (
              <p className="help-text">Загрузка каналов...</p>
            ) : (
              <div className="channels-modal__body">
                <div className="channel-modal-list">
                  {channels.length === 0 ? (
                    <p className="help-text">Подключений пока нет</p>
                  ) : (
                    channels.map((channel) => (
                      <div key={channel.id} className="doc-row">
                        <div className="doc-meta">
                          <span className="doc-name">
                            {channelLabel(channel)} · {channel.external_id}
                            {channel.provider === TELEPHONY_PROVIDER ? <DemoBadge /> : null}
                          </span>
                          <span className={`doc-status ${channel.is_primary ? 'doc-status--ready' : ''}`}>
                            {channel.is_primary ? 'основной' : 'дополнительный'}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="delete-btn"
                          disabled={isSavingChannel}
                          onClick={() => handleRemoveChannel(channel.id)}
                        >
                          ×
                        </button>
                      </div>
                    ))
                  )}
                </div>

                <div className="connection-type-grid connection-type-grid--channels channels-tabs">
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'bot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('bot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    Telegram бот
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'userbot' ? 'active' : ''}`}
                    onClick={() => setChannelModalTab('userbot')}
                    disabled={isSavingChannel}
                  >
                    Telegram userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'max_bot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('max_bot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    MAX бот
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'max_userbot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('max_userbot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    MAX userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'whatsapp_userbot' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('whatsapp_userbot')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    WhatsApp userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card connection-type-card--with-beta ${channelModalTab === 'whatsapp' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('whatsapp')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                      <span className="connection-type-card-label connection-type-card-label--stacked-wa-api">
                      <span className="connection-type-card-label__row">WhatsApp Business</span>
                      <span className="connection-type-card-label__row connection-type-card-label__row--api-beta">
                        API
                        <span className="beta-badge">BETA</span>
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card connection-type-card--with-beta ${channelModalTab === 'telephony' ? 'active' : ''} ${isSalesManagerTemplate ? 'connection-type-card--disabled' : ''}`}
                    onClick={() => setChannelModalTab('telephony')}
                    disabled={isSavingChannel || isSalesManagerTemplate}
                  >
                    <span className="connection-type-card-label connection-type-card-label--with-demo">
                      Телефония
                      <DemoBadge />
                    </span>
                  </button>
                </div>
                {isSalesManagerTemplate ? (
                  <p className="help-text">
                    Для шаблона "Менеджер продаж" доступно только подключение Telegram userbot.
                  </p>
                ) : null}

                {channelModalTab === 'bot' ? (
                  <div className="agent-management-block">
                    <input
                      type="text"
                      className="input-main"
                      placeholder="API ключ Telegram бота"
                      value={botTokenDraft}
                      onChange={(event) => setBotTokenDraft(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddBotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить Telegram бота'}
                    </button>
                  </div>
                ) : channelModalTab === 'userbot' ? (
                  <div className="agent-management-block">
                    <input
                      type="number"
                      className="input-main"
                      placeholder="API ID"
                      value={userbotApiId}
                      onChange={(event) => setUserbotApiId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="API hash"
                      value={userbotApiHash}
                      onChange={(event) => setUserbotApiHash(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="+79990001122"
                      value={userbotPhone}
                      onChange={(event) => setUserbotPhone(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={handleRequestUserbotCode}
                      disabled={isSavingChannel || isSendingUserbotCode}
                    >
                      {isSendingUserbotCode ? 'Отправка...' : 'Отправить код'}
                    </button>
                    <input
                      type="text"
                      className="input-main"
                      placeholder="Код из Telegram"
                      value={userbotCode}
                      onChange={(event) => setUserbotCode(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="password"
                      className="input-main"
                      placeholder="Пароль 2FA (если есть)"
                      value={userbotPassword}
                      onChange={(event) => setUserbotPassword(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={handleVerifyUserbotCode}
                      disabled={isSavingChannel || isVerifyingUserbotCode}
                    >
                      {isVerifyingUserbotCode ? 'Проверка...' : 'Подтвердить код'}
                    </button>
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddUserbotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить Telegram userbot'}
                    </button>
                  </div>
                ) : channelModalTab === 'max_bot' ? (
                  <div className="agent-management-block">
                    <input
                      type="text"
                      className="input-main"
                      placeholder="MAX bot token (из MAX для партнеров)"
                      value={maxBotTokenDraft}
                      onChange={(event) => setMaxBotTokenDraft(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddMaxBotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить MAX bot'}
                    </button>
                  </div>
                ) : channelModalTab === 'max_userbot' ? (
                  <div className="agent-management-block">
                    <textarea
                      className="input-main textarea"
                      rows={4}
                      placeholder="MAX token (из localStorage.__oneme_auth.token)"
                      value={maxUserbotTokenDraft}
                      onChange={(event) => setMaxUserbotTokenDraft(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <p className="help-text">
                      Будут обрабатываться все личные сообщения (ЛС) в MAX.
                    </p>
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddMaxUserbotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить MAX userbot'}
                    </button>
                  </div>
                ) : channelModalTab === 'whatsapp_userbot' ? (
                  <div className="agent-management-block">
                    <div className="connection-type-grid connection-type-grid--pair channels-tabs">
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotMode === 'simple' ? 'active' : ''}`}
                        onClick={() => switchWhatsappUserbotMode('simple')}
                        disabled={isSavingChannel}
                      >
                        Простое подключение
                      </button>
                      <button
                        type="button"
                        className={`connection-type-card ${whatsappUserbotMode === 'expert' ? 'active' : ''}`}
                        onClick={() => switchWhatsappUserbotMode('expert')}
                        disabled={isSavingChannel}
                      >
                        Режим эксперта
                      </button>
                    </div>

                    <input
                      type="text"
                      className="input-main"
                      placeholder="Номер WhatsApp userbot (+79990001122)"
                      value={whatsappUserbotPhone}
                      onChange={(event) => setWhatsappUserbotPhone(event.target.value)}
                      disabled={isSavingChannel}
                    />

                    {whatsappUserbotMode === 'simple' ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleRequestWhatsappUserbotCode}
                          disabled={isSavingChannel || isSendingWhatsappUserbotCode}
                        >
                          {isSendingWhatsappUserbotCode ? 'Отправка...' : 'Запросить QR-код'}
                        </button>
                        {whatsappUserbotQrDataUrl ? (
                          <div className="wa-qr-card">
                            <p className="wa-qr-title"><strong>QR для подключения</strong></p>
                            <img
                              src={whatsappUserbotQrDataUrl}
                              alt="WhatsApp QR"
                              className="wa-qr-image"
                            />
                            <p className="wa-qr-hint">
                              На телефоне: WhatsApp → Настройки → Связанные устройства → Привязать устройство — отсканируйте QR.
                            </p>
                          </div>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleVerifyWhatsappUserbotCode}
                          disabled={isSavingChannel || isVerifyingWhatsappUserbotCode}
                        >
                          {isVerifyingWhatsappUserbotCode ? 'Проверка...' : 'Проверить подключение'}
                        </button>
                      </>
                    ) : (
                      <textarea
                        className="input-main textarea"
                        rows={4}
                        placeholder="Session string WhatsApp userbot"
                        value={whatsappUserbotSessionString}
                        onChange={(event) => setWhatsappUserbotSessionString(event.target.value)}
                        disabled={isSavingChannel}
                      />
                    )}

                    <input
                      type="text"
                      className="input-main"
                      placeholder="Название клиента (опционально)"
                      value={whatsappUserbotClientLabel}
                      onChange={(event) => setWhatsappUserbotClientLabel(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddWhatsAppUserbotChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить WhatsApp userbot'}
                    </button>
                    {whatsappUserbotMode === 'simple' && isWhatsappUserbotVerified ? (
                      <p className="help-text userbot-success">Сессия успешно инициализирована</p>
                    ) : null}
                  </div>
                ) : channelModalTab === 'telephony' ? (
                  <div className="agent-management-block">
                    <TitleWithDemoBadge as="h4" className="agent-form-channel-title">
                      Телефония (ИИ-оператор, Voximplant)
                    </TitleWithDemoBadge>
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
                          <>Телефония на сервере не настроена: {telephonyPlatform.missing_env?.join(', ')}</>
                        )}
                      </p>
                    ) : null}
                    {hasTelephonyChannel ? (
                      <>
                        <p className="help-text userbot-success">
                          Канал подключён: добавочный {telephonyChannel.external_id?.replace(/^pool:/, '') || '—'}.
                          Удалите канал в списке выше, чтобы переподключить.
                        </p>
                        <input
                          type="text"
                          className="input-main"
                          placeholder="Добавочный (4 цифры)"
                          value={telephonyRoutingExtension}
                          onChange={(e) =>
                            setTelephonyRoutingExtension(e.target.value.replace(/\D/g, '').slice(0, 4))
                          }
                          disabled={isSavingChannel}
                          maxLength={4}
                        />
                        <p className="help-text">
                          Клиенты звонят на общий номер и вводят добавочный после гудка (или набирают номер,добавочный).
                        </p>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleUpdateTelephonyRouting}
                          disabled={isSavingChannel}
                        >
                          {isSavingChannel ? 'Сохранение...' : 'Сохранить добавочный'}
                        </button>
                      </>
                    ) : (
                      <>
                        <input
                          type="text"
                          className="input-main"
                          placeholder="Добавочный агента (4 цифры) *"
                          value={telephonyRoutingExtension}
                          onChange={(e) =>
                            setTelephonyRoutingExtension(e.target.value.replace(/\D/g, '').slice(0, 4))
                          }
                          disabled={isSavingChannel}
                          maxLength={4}
                        />
                        <div className="telephony-channel-options">
                          <FeatureToggle
                            checked={telephonyRecordCalls}
                            onChange={setTelephonyRecordCalls}
                            disabled={isSavingChannel}
                            title="Записывать звонки"
                            helpText="Сохраняет аудиозапись разговора для последующего прослушивания в аналитике."
                          />
                          <FeatureToggle
                            checked={telephonyDisclaimerPlayed}
                            onChange={setTelephonyDisclaimerPlayed}
                            disabled={isSavingChannel}
                            title="IVR о записи в начале"
                            helpText="Проигрывает короткое уведомление о записи разговора в начале звонка."
                          />
                        </div>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleValidateTelephony}
                          disabled={isSavingChannel || isValidatingTelephony}
                        >
                          {isValidatingTelephony ? 'Проверка...' : 'Проверить подключение'}
                        </button>
                        {telephonyValidateStatus ? (
                          <p className="help-text userbot-success">{telephonyValidateStatus}</p>
                        ) : null}
                        <label className="channel-primary-checkbox">
                          <input
                            type="checkbox"
                            checked={makePrimaryChannel}
                            onChange={(e) => setMakePrimaryChannel(e.target.checked)}
                            disabled={isSavingChannel}
                          />
                          Сделать канал основным
                        </label>
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleAddTelephonyChannel}
                          disabled={isSavingChannel}
                        >
                          {isSavingChannel ? 'Сохранение...' : 'Подключить телефонию'}
                        </button>
                      </>
                    )}
                    {(telephonyWebhookUrl || telephonyChannel?.telephony_webhook_url) ? (
                      <div className="telephony-webhook-row">
                        <label>Webhook URL (вставьте в кабинет Voximplant)</label>
                        <div className="api-key-row">
                          <input
                            type="text"
                            className="input-main"
                            readOnly
                            value={telephonyWebhookUrl || telephonyChannel?.telephony_webhook_url || ''}
                          />
                          <button
                            type="button"
                            className="btn btn-outline"
                            onClick={handleCopyTelephonyWebhook}
                          >
                            Копировать
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="agent-management-block">
                    <input
                      type="text"
                      className="input-main"
                      placeholder="WhatsApp Phone Number ID"
                      value={whatsappPhoneNumberId}
                      onChange={(event) => setWhatsappPhoneNumberId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="password"
                      className="input-main"
                      placeholder="WhatsApp Access Token"
                      value={whatsappAccessToken}
                      onChange={(event) => setWhatsappAccessToken(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="WhatsApp Business Account ID (опционально)"
                      value={whatsappBusinessAccountId}
                      onChange={(event) => setWhatsappBusinessAccountId(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <input
                      type="text"
                      className="input-main"
                      placeholder="Webhook Verify Token (опционально)"
                      value={whatsappVerifyToken}
                      onChange={(event) => setWhatsappVerifyToken(event.target.value)}
                      disabled={isSavingChannel}
                    />
                    <label className="channel-primary-checkbox">
                      <input
                        type="checkbox"
                        checked={makePrimaryChannel}
                        onChange={(event) => setMakePrimaryChannel(event.target.checked)}
                        disabled={isSavingChannel}
                      />
                      Сделать канал основным
                    </label>
                    <button
                      type="button"
                      className="btn btn-black"
                      onClick={handleAddWhatsAppBusinessApiChannel}
                      disabled={isSavingChannel}
                    >
                      {isSavingChannel ? 'Сохранение...' : 'Подключить WhatsApp Business API'}
                    </button>
                  </div>
                )}

                <div className="auth-modal-actions">
                  <button type="button" className="btn btn-black" onClick={handleCloseChannelsModal}>
                    Закрыть
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const AgentsPage = () => {
  return (
    <MainLayout>
      <AgentsPageContent />
    </MainLayout>
  );
};

export default AgentsPage;