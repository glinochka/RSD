/**
 * Agents Page
 * Display user's agents and manage full lifecycle
 */

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import AgentsEmptyState from '../components/AgentsEmptyState';
import AgentContractPaymentModal from '../components/AgentContractPaymentModal';
import CreateChoiceModal from '../components/CreateChoiceModal';
import { WebsiteBuilderWizard } from '../website-builder/components';
import { useAsync } from '../hooks/useAsync';
import agentService from '../services/agentService';
import pricingService from '../services/pricingService';
import websiteService from '../services/websiteService';
import { formatRubPrice } from '../utils/agentTemplatePricing';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import { useAuth } from '../context/useAuth';
import { validateFile } from '../utils/validation';
import { isWhatsappUserbotAuthSessionExpiredMessage } from '../utils/errorUtils';
import DemoBadge, { TitleWithDemoBadge } from '../components/DemoBadge';
import UserbotSessionFileUpload from '../components/UserbotSessionFileUpload';
import MaxUserbotAuthPanel from '../components/MaxUserbotAuthPanel';
import {
  TELEPHONY_PROVIDER,
  copyTextToClipboard,
  findTelephonyChannel,
} from '../utils/telephony';
import '../styles/agentsPage.css';

const AGENTS_EMPTY_MESSAGE = 'У вас еще нет агентов, создайте прямо сейчас';
const AGENTS_EMPTY_CTA = 'Создайте прямо сейчас';
const PENDING_AGENT_CONTRACT_PAYMENT_ID_KEY = 'pending_agent_contract_payment_id';
const fileIdentity = (file) => `${file.name}::${file.size}::${file.lastModified}`;
const linkIdentity = (link) => link.trim().toLowerCase();
const isPortraitFeatureEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_portrait !== false;
};
const isHumanDelayEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_human_delay !== false;
};
const isChatHistoryEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_history !== false;
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

/** Validate YooKassa fields before composing shop_id:secret_key for the API. */
const validateYookassaCredentials = (shopId, secretKey) => {
  const trimmedShopId = String(shopId || '').trim();
  const trimmedSecret = String(secretKey || '').trim();
  if (!trimmedShopId || !trimmedSecret) {
    return 'Укажите Shop ID и Secret key ЮKassa';
  }
  if (!/^\d+$/.test(trimmedShopId)) {
    return 'Shop ID ЮKassa — только цифры (идентификатор магазина из личного кабинета)';
  }
  if (!trimmedSecret.startsWith('live_') && !trimmedSecret.startsWith('test_')) {
    return 'Secret key должен начинаться с live_ или test_ (секретный ключ из раздела «Ключи API»)';
  }
  if (trimmedSecret.includes(':')) {
    return 'В поле Secret key укажите только секретный ключ, без Shop ID и без двоеточия';
  }
  if (trimmedShopId.includes(':')) {
    return 'В поле Shop ID укажите только номер магазина, без Secret key';
  }
  return null;
};

/** Build yookassa_api_key for PATCH or validation error; omit key to keep stored credentials. */
const resolveYookassaCredentialsUpdate = ({ paidBookingEnabled, shopId, secretKey, hasStoredKey }) => {
  const trimmedShopId = String(shopId || '').trim();
  const trimmedSecret = String(secretKey || '').trim();
  const hasShop = trimmedShopId.length > 0;
  const hasSecret = trimmedSecret.length > 0;

  if (!paidBookingEnabled) {
    return { yookassa_api_key: '', clearStoredKey: true };
  }

  if (!hasShop && !hasSecret) {
    if (!hasStoredKey) {
      return { error: 'Укажите Shop ID и Secret key из личного кабинета ЮKassa (раздел «Настройки → Ключи API»)' };
    }
    return {};
  }

  if (hasShop !== hasSecret) {
    return {
      error:
        'Заполните оба поля ЮKassa. Это не логин сайта: Shop ID — только цифры, Secret key — ключ вида live_… или test_…',
    };
  }

  const validationError = validateYookassaCredentials(trimmedShopId, trimmedSecret);
  if (validationError) {
    return { error: validationError };
  }

  return {
    yookassa_api_key: `${trimmedShopId}:${trimmedSecret}`,
    credentialsUpdated: true,
  };
};

const unlockYookassaInput = (event) => {
  event.currentTarget.removeAttribute('readonly');
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

const stripSalesTriggerWord = (value) => {
  let w = String(value || '').trim().toLowerCase();
  if (!w) return '';
  w = w.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');
  if (w.startsWith('json')) w = w.slice(4).replace(/^[\s:[\]-]+/, '');
  w = w.replace(/^[\s[\]"'({]+|[\s[\]"'})]+$/g, '');
  w = w.replace(/^[\s[\]"'({]+|[\s[\]"'})]+$/g, '');
  return w;
};

const coerceSalesTriggerWordsInput = (raw) => {
  if (Array.isArray(raw)) {
    const items = [];
    raw.forEach((item) => {
      if (typeof item === 'string' && item.trim().startsWith('[')) {
        try {
          const nested = JSON.parse(
            item.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, ''),
          );
          if (Array.isArray(nested)) {
            items.push(...nested);
            return;
          }
        } catch {
          // fall through
        }
      }
      items.push(item);
    });
    return items;
  }
  if (typeof raw !== 'string') return [];
  const text = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '');
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : [text];
  } catch {
    const bracketMatch = text.match(/\[[\s\S]*\]/);
    if (bracketMatch) {
      try {
        const parsed = JSON.parse(bracketMatch[0]);
        if (Array.isArray(parsed)) return parsed;
      } catch {
        // fall through
      }
    }
    return text.split(',').map((part) => part.trim()).filter(Boolean);
  }
};

const normalizeSalesTriggerWordsList = (raw) => {
  const list = coerceSalesTriggerWordsInput(raw);
  const out = [];
  for (const item of list) {
    const w = stripSalesTriggerWord(item);
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

const FeatureToggle = ({ checked, onChange, disabled, title, helpText }) => {
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { showError, showSuccess, showInfo } = useNotification();
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
  const [isSavingHumanDelay, setIsSavingHumanDelay] = useState(false);
  const [isSavingChatHistory, setIsSavingChatHistory] = useState(false);
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
  const [isCreateChoiceModalOpen, setIsCreateChoiceModalOpen] = useState(false);
  const [channelModalTab, setChannelModalTab] = useState('bot');
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [isSavingChannel, setIsSavingChannel] = useState(false);
  const [botTokenDraft, setBotTokenDraft] = useState('');
  const [makePrimaryChannel, setMakePrimaryChannel] = useState(false);
  const [userbotResolvedApiId, setUserbotResolvedApiId] = useState(null);
  const [userbotResolvedApiHash, setUserbotResolvedApiHash] = useState('');
  const [userbotPhone, setUserbotPhone] = useState('');
  const [userbotCode, setUserbotCode] = useState('');
  const [userbotPassword, setUserbotPassword] = useState('');
  const [userbotAuthMode, setUserbotAuthMode] = useState('qr');
  const [userbotAuthToken, setUserbotAuthToken] = useState('');
  const [userbotQrAuthToken, setUserbotQrAuthToken] = useState('');
  const [userbotQrDataUrl, setUserbotQrDataUrl] = useState('');
  const [userbotQrNeeds2fa, setUserbotQrNeeds2fa] = useState(false);
  const [userbotSessionString, setUserbotSessionString] = useState('');
  const [userbotVerifiedLabel, setUserbotVerifiedLabel] = useState('');
  const [maxBotTokenDraft, setMaxBotTokenDraft] = useState('');
  const [maxUserbotSessionPayload, setMaxUserbotSessionPayload] = useState('');
  const [isSendingUserbotCode, setIsSendingUserbotCode] = useState(false);
  const [isVerifyingUserbotCode, setIsVerifyingUserbotCode] = useState(false);
  const [isStartingUserbotQr, setIsStartingUserbotQr] = useState(false);
  const [isVerifyingUserbotQr2fa, setIsVerifyingUserbotQr2fa] = useState(false);
  const [isImportingUserbotSession, setIsImportingUserbotSession] = useState(false);
  const userbotLastQrStatusRef = useRef('');
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
  const whatsappAutoVerifyAttemptedRef = useRef(false);
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
  const [adminPaidBookingEnabled, setAdminPaidBookingEnabled] = useState(false);
  const [adminYookassaShopId, setAdminYookassaShopId] = useState('');
  const [adminYookassaSecretKey, setAdminYookassaSecretKey] = useState('');
  const [adminHasYookassaApiKey, setAdminHasYookassaApiKey] = useState(false);
  const [salesProductName, setSalesProductName] = useState('');
  const [salesOfferType, setSalesOfferType] = useState('');
  const [salesUsp, setSalesUsp] = useState('');
  const [salesWorkflowCompletionMode, setSalesWorkflowCompletionMode] = useState('auto_finish_on_signal');
  const [salesLeadScoreScale, setSalesLeadScoreScale] = useState('100');
  const [salesLeadGenerationEnabled, setSalesLeadGenerationEnabled] = useState(true);
  const [salesContactsPoolOnly, setSalesContactsPoolOnly] = useState(false);
  const [salesNeuroCommentingEnabled, setSalesNeuroCommentingEnabled] = useState(false);
  const [salesLiveChatSimulationEnabled, setSalesLiveChatSimulationEnabled] = useState(false);
  const [salesTriggerWords, setSalesTriggerWords] = useState(() => ['купить']);
  const [salesTriggerWordDraft, setSalesTriggerWordDraft] = useState('');
  const [salesExcelUploadBusy, setSalesExcelUploadBusy] = useState(false);
  const [salesExcelImportInfo, setSalesExcelImportInfo] = useState(null);
  const salesExcelFileInputId = useId();
  const [agentAvailAlwaysOn, setAgentAvailAlwaysOn] = useState(true);
  const [agentAvailTimezone, setAgentAvailTimezone] = useState(() => getBrowserTimezoneSafe());
  const [agentAvailWeekdays, setAgentAvailWeekdays] = useState(buildDefaultAgentAvailabilityWeekdays);
  const [isSavingAgentAvailability, setIsSavingAgentAvailability] = useState(false);
  const [agentWebsite, setAgentWebsite] = useState(null);
  const [isWebsiteLoading, setIsWebsiteLoading] = useState(false);
  const [isWebsiteBuilding, setIsWebsiteBuilding] = useState(false);
  const [isWebsiteWizardOpen, setIsWebsiteWizardOpen] = useState(false);
  const websiteGenerationPollRef = useRef(null);
  const detailsRequestIdRef = useRef(0);
  const [contractModalAgent, setContractModalAgent] = useState(null);
  const [contractModalTitle, setContractModalTitle] = useState('');
  const [isContractPaymentProcessing, setIsContractPaymentProcessing] = useState(false);
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    execute();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const pendingPaymentId = localStorage.getItem(PENDING_AGENT_CONTRACT_PAYMENT_ID_KEY);
    if (!pendingPaymentId) return;

    let cancelled = false;
    const verifyPayment = async () => {
      try {
        const statusData = await pricingService.getYooKassaPaymentStatus(pendingPaymentId);
        if (cancelled) return;
        if (statusData?.status === 'succeeded') {
          showSuccess('Подписка на агента успешно оплачена.');
          await refreshAgents();
          if (statusData.agent_id) {
            await loadAgentDetails(statusData.agent_id);
          }
        } else if (statusData?.status === 'canceled') {
          showError('Оплата отменена.');
        }
      } catch (error) {
        if (!cancelled) {
          showError(error?.message || 'Не удалось проверить статус оплаты');
        }
      } finally {
        localStorage.removeItem(PENDING_AGENT_CONTRACT_PAYMENT_ID_KEY);
        if (searchParams.get('agent_payment')) {
          const next = new URLSearchParams(searchParams);
          next.delete('agent_payment');
          setSearchParams(next, { replace: true });
        }
      }
    };
    verifyPayment();
    return () => {
      cancelled = true;
    };
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

  useEffect(() => {
    if (!isAuthenticated) return;
    const createType = String(searchParams.get('create') || '').trim().toLowerCase();
    if (createType !== 'website') return;

    setIsCreateChoiceModalOpen(false);
    setIsWebsiteWizardOpen(true);

    const next = new URLSearchParams(searchParams);
    next.delete('create');
    setSearchParams(next, { replace: true });
  }, [isAuthenticated, searchParams, setSearchParams]);

  const handleCreateAgent = () => {
    setIsCreateChoiceModalOpen(true);
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

  const clearWebsiteGenerationPoll = () => {
    if (websiteGenerationPollRef.current) {
      window.clearInterval(websiteGenerationPollRef.current);
      websiteGenerationPollRef.current = null;
    }
  };

  const loadAgentWebsite = async (agentId) => {
    if (!agentId) {
      setAgentWebsite(null);
      setIsWebsiteBuilding(false);
      clearWebsiteGenerationPoll();
      return null;
    }

    setIsWebsiteLoading(true);
    try {
      const response = await websiteService.list({ page: 1, page_size: 100 });
      const items = Array.isArray(response?.items) ? response.items : [];
      const websitesForAgent = items.filter((item) => item?.agent_id === agentId);
      const latestWebsite = websitesForAgent.sort((a, b) => Number(b.id || 0) - Number(a.id || 0))[0] || null;
      setAgentWebsite(latestWebsite);
      const generationStatus = String(latestWebsite?.generation_status || '').toLowerCase();
      const isGenerationRunning = generationStatus === 'queued' || generationStatus === 'generating';
      setIsWebsiteBuilding(isGenerationRunning);
      if (isGenerationRunning && latestWebsite?.id) {
        startWebsiteGenerationPoll(latestWebsite.id);
      } else {
        clearWebsiteGenerationPoll();
      }
      return latestWebsite;
    } catch (error) {
      setAgentWebsite(null);
      setIsWebsiteBuilding(false);
      showError(error?.message || 'Не удалось загрузить данные сайта');
      return null;
    } finally {
      setIsWebsiteLoading(false);
    }
  };

  const startWebsiteGenerationPoll = (websiteId) => {
    if (!websiteId) return;
    clearWebsiteGenerationPoll();
    websiteGenerationPollRef.current = window.setInterval(async () => {
      try {
        const [statusData, websiteData] = await Promise.all([
          websiteService.getGenerationStatus(websiteId),
          websiteService.getById(websiteId),
        ]);
        const statusValue = String(statusData?.generation_status || '').toLowerCase();
        setAgentWebsite(websiteData || null);
        if (statusValue === 'completed') {
          clearWebsiteGenerationPoll();
          setIsWebsiteBuilding(false);
          showSuccess('Сайт успешно собран');
          if (selectedBotId) {
            await loadAgentWebsite(selectedBotId);
          }
          return;
        }
        if (statusValue === 'failed') {
          clearWebsiteGenerationPoll();
          setIsWebsiteBuilding(false);
          showError(statusData?.error || 'Не удалось собрать сайт');
          return;
        }
        setIsWebsiteBuilding(statusValue === 'queued' || statusValue === 'generating');
      } catch {
        // Keep polling while generation endpoint is temporarily unavailable.
      }
    }, 4000);
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
      await loadAgentWebsite(agent.id);
    } catch (error) {
      if (requestId !== detailsRequestIdRef.current) return;
      clearWebsiteGenerationPoll();
      setAgentWebsite(null);
      setIsWebsiteBuilding(false);
      showError(error?.message || 'Ошибка при загрузке карточки агента');
    } finally {
      if (requestId !== detailsRequestIdRef.current) return;
      setIsLoadingDetails(false);
    }
  };

  useEffect(() => () => {
    clearWebsiteGenerationPoll();
  }, []);

  const handleStartWebsiteBuilder = () => {
    if (!selectedAgent || isWebsiteBuilding) return;
    setIsWebsiteWizardOpen(true);
  };

  const handleWebsiteWizardClose = () => {
    setIsWebsiteWizardOpen(false);
  };

  const handleWebsiteWizardSuccess = (websiteId) => {
    setIsWebsiteWizardOpen(false);
    setIsWebsiteBuilding(true);
    showSuccess('Запустили сборку сайта. Обычно это занимает несколько минут.');
    loadAgentWebsite(selectedAgent?.id);
    startWebsiteGenerationPoll(websiteId);
  };

  const handleOpenWebsiteConstructor = () => {
    if (!agentWebsite?.id) return;
    navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(agentWebsite.id));
  };

  const handleOpenWebsiteView = () => {
    if (!agentWebsite?.slug) {
      showError('У сайта ещё нет публичного адреса. Дождитесь завершения сборки.');
      return;
    }
    if (agentWebsite.status !== 'published') {
      showError('Опубликуйте сайт в конструкторе — ссылка для клиентов станет доступна после публикации.');
      return;
    }
    window.open(NAVIGATION_ROUTES.WEBSITE_PUBLIC(agentWebsite.slug), '_blank', 'noopener,noreferrer');
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

  const openContractPaymentModal = (agent, title) => {
    if (!agent) return;
    setContractModalAgent(agent);
    setContractModalTitle(title);
  };

  const closeContractPaymentModal = () => {
    if (isContractPaymentProcessing) return;
    setContractModalAgent(null);
    setContractModalTitle('');
  };

  const handleContractPaymentSubmit = async ({ agentId, durationMonths, promoCode, enableAutopay }) => {
    if (isContractPaymentProcessing) return;
    setIsContractPaymentProcessing(true);
    try {
      const returnUrl = `${window.location.origin}${NAVIGATION_ROUTES.AGENTS}?agent_payment=1`;
      const payment = await pricingService.createAgentBillingPayment({
        agent_id: agentId,
        payment_kind: 'agent_maintenance',
        return_url: returnUrl,
        promo_code: promoCode,
        duration_months: durationMonths,
        enable_autopay: enableAutopay,
      });

      if (payment?.autopay_warning) {
        showInfo(payment.autopay_warning);
      }

      if (payment?.status === 'succeeded' && !payment?.confirmation_url) {
        showSuccess('Подписка активирована по промокоду.');
        closeContractPaymentModal();
        await refreshAgents();
        if (selectedBotId === agentId) {
          await loadAgentDetails(agentId);
        }
        return;
      }

      if (!payment?.confirmation_url || !payment?.payment_id) {
        throw new Error('Сервис оплаты вернул некорректный ответ.');
      }

      localStorage.setItem(PENDING_AGENT_CONTRACT_PAYMENT_ID_KEY, payment.payment_id);
      window.location.href = payment.confirmation_url;
    } catch (error) {
      showError(error?.message || 'Не удалось создать платёж');
      setIsContractPaymentProcessing(false);
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
      const paymentKind = paymentDetail?.payment_kind;
      if (error?.status === 402 && willActivate && billing?.requires_subscription) {
        openContractPaymentModal(
          { ...agentBeforeToggle, billing },
          'Оплата подписки для активации',
        );
        return;
      }
      if (error?.status === 402 && willActivate && paymentKind === 'agent_activation') {
        openContractPaymentModal(agentBeforeToggle, 'Оплата для активации агента');
        return;
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

  const handleToggleHumanDelay = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = { ...currentConfig, enable_human_delay: Boolean(enabled) };
    setIsSavingHumanDelay(true);
    try {
      await agentService.update(selectedBotId, { template_config: nextConfig });
      setSelectedAgent((prev) => (prev ? { ...prev, template_config: nextConfig } : prev));
      showSuccess(enabled ? 'Имитация присутствия включена' : 'Имитация присутствия отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку имитации присутствия');
    } finally {
      setIsSavingHumanDelay(false);
    }
  };

  const handleToggleChatHistory = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const currentConfig =
      selectedAgent.template_config && typeof selectedAgent.template_config === 'object'
        ? selectedAgent.template_config
        : {};
    const nextConfig = { ...currentConfig, enable_chat_history: Boolean(enabled) };
    setIsSavingChatHistory(true);
    try {
      await agentService.update(selectedBotId, { template_config: nextConfig });
      setSelectedAgent((prev) => (prev ? { ...prev, template_config: nextConfig } : prev));
      showSuccess(enabled ? 'История чата включена' : 'История чата отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку истории чата');
    } finally {
      setIsSavingChatHistory(false);
    }
  };

  const persistTemplateConfigPatch = async (patch, { successMessage, errorMessage } = {}) => {
    if (!selectedBotId || !selectedAgent) return false;
    const currentConfig = getTemplateConfig(selectedAgent);
    const nextConfig = { ...currentConfig, ...patch };
    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, { template_config: nextConfig });
      setSelectedAgent((prev) => (prev ? { ...prev, template_config: nextConfig } : prev));
      if (successMessage) showSuccess(successMessage);
      return true;
    } catch (error) {
      showError(error?.message || errorMessage || 'Не удалось сохранить настройку');
      return false;
    } finally {
      setIsSavingTemplateConfig(false);
    }
  };

  const handleToggleAdminWaitlist = async (enabled) => {
    const next = Boolean(enabled);
    const ok = await persistTemplateConfigPatch(
      { waitlist_enabled: next },
      {
        successMessage: next ? 'Waitlist включён' : 'Waitlist отключён',
        errorMessage: 'Не удалось обновить настройку waitlist',
      },
    );
    if (ok) setAdminWaitlistEnabled(next);
  };

  const handleToggleAdminReminder = async (enabled) => {
    const next = Boolean(enabled);
    const ok = await persistTemplateConfigPatch(
      { reminder_enabled: next },
      {
        successMessage: next ? 'Напоминания включены' : 'Напоминания отключены',
        errorMessage: 'Не удалось обновить настройку напоминаний',
      },
    );
    if (ok) setAdminReminderEnabled(next);
  };

  const handleToggleAdminPaidBooking = async (enabled) => {
    if (!selectedBotId || !selectedAgent) return;
    const next = Boolean(enabled);
    const nextConfig = {
      ...getTemplateConfig(selectedAgent),
      paid_booking_enabled: next,
    };
    const updatePayload = { template_config: nextConfig };
    if (!next) {
      updatePayload.yookassa_api_key = '';
    }
    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, updatePayload);
      const refreshedAgent = await agentService.getById(selectedBotId);
      setSelectedAgent((prev) =>
        prev
          ? {
              ...prev,
              ...refreshedAgent,
              template_config: nextConfig,
            }
          : refreshedAgent
      );
      setAdminPaidBookingEnabled(next);
      if (!next) {
        setAdminHasYookassaApiKey(false);
        setAdminYookassaShopId('');
        setAdminYookassaSecretKey('');
      }
      showSuccess(next ? 'Платная бронь включена' : 'Платная бронь отключена');
    } catch (error) {
      showError(error?.message || 'Не удалось обновить настройку платной брони');
    } finally {
      setIsSavingTemplateConfig(false);
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
      paid_booking_enabled: Boolean(adminPaidBookingEnabled),
    };
    const yookassaUpdate = resolveYookassaCredentialsUpdate({
      paidBookingEnabled: adminPaidBookingEnabled,
      shopId: adminYookassaShopId,
      secretKey: adminYookassaSecretKey,
      hasStoredKey: adminHasYookassaApiKey,
    });
    if (yookassaUpdate.error) {
      showError(yookassaUpdate.error);
      return;
    }
    const updatePayload = { template_config: nextConfig };
    if (Object.prototype.hasOwnProperty.call(yookassaUpdate, 'yookassa_api_key')) {
      updatePayload.yookassa_api_key = yookassaUpdate.yookassa_api_key;
    }
    setIsSavingTemplateConfig(true);
    try {
      await agentService.update(selectedBotId, updatePayload);
      const refreshedAgent = await agentService.getById(selectedBotId);
      setSelectedAgent((prev) => (prev
        ? {
          ...prev,
          ...refreshedAgent,
          template_config: nextConfig,
        }
        : refreshedAgent));
      setAdminYookassaShopId('');
      setAdminYookassaSecretKey('');
      setAdminHasYookassaApiKey(Boolean(refreshedAgent?.has_booking_payment_api_key));
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
      contacts_pool_only: Boolean(salesContactsPoolOnly),
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

  const handleSalesManagerExcelUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !selectedAgent?.id) return;
    setSalesExcelUploadBusy(true);
    try {
      const res = await agentService.uploadSalesManagerExcel(selectedAgent.id, file);
      setSalesExcelImportInfo(res);
      showSuccess(res?.message || 'База загружена, рассылка запущена');
    } catch (error) {
      showError(error?.response?.data?.detail || error?.message || 'Не удалось загрузить Excel');
    } finally {
      setSalesExcelUploadBusy(false);
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
      if (field === 'contacts_pool_only') {
        setSalesContactsPoolOnly(Boolean(enabled));
      }
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
    const draft = salesTriggerWordDraft.trim();
    if (!draft) return;
    const candidates = normalizeSalesTriggerWordsList(
      draft.startsWith('[') || draft.includes('```') ? draft : [draft],
    );
    if (candidates.length === 0) return;
    setSalesTriggerWords((prev) => {
      let next = prev;
      for (const w of candidates) {
        if (!w || w.length > 64) continue;
        if (next.includes(w)) continue;
        if (next.length >= 30) break;
        next = [...next, w];
      }
      return next;
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
    setUserbotResolvedApiId(null);
    setUserbotResolvedApiHash('');
    setUserbotPhone('');
    setUserbotCode('');
    setUserbotPassword('');
    setUserbotAuthMode('qr');
    setUserbotAuthToken('');
    setUserbotQrAuthToken('');
    setUserbotQrDataUrl('');
    setUserbotQrNeeds2fa(false);
    setUserbotSessionString('');
    setUserbotVerifiedLabel('');
    setMaxBotTokenDraft('');
    setMaxUserbotSessionPayload('');
    setIsSendingUserbotCode(false);
    setIsVerifyingUserbotCode(false);
    setIsStartingUserbotQr(false);
    setIsVerifyingUserbotQr2fa(false);
    setIsImportingUserbotSession(false);
    userbotLastQrStatusRef.current = '';
    setWhatsappUserbotPhone('');
    setWhatsappUserbotSessionString('');
    setWhatsappUserbotClientLabel('');
    setWhatsappUserbotMode('simple');
    setWhatsappUserbotAuthToken('');
    setWhatsappUserbotQrDataUrl('');
    whatsappUserbotLastAuthStatusRef.current = '';
    whatsappAutoVerifyAttemptedRef.current = false;
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
    const salesChannels = (selectedAgent?.channels || []).filter((ch) =>
      ['telegram_userbot', 'whatsapp_userbot'].includes(ch.provider)
    );
    const preferredSalesTab = salesChannels.some((ch) => ch.provider === 'whatsapp_userbot')
      ? 'whatsapp_userbot'
      : 'userbot';
    setChannelModalTab(
      selectedAgent?.template_type === 'sales_manager' ? preferredSalesTab : 'bot'
    );
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
    setAdminPaidBookingEnabled(Boolean(cfg.paid_booking_enabled));
    setAdminYookassaShopId('');
    setAdminYookassaSecretKey('');
    setAdminHasYookassaApiKey(Boolean(selectedAgent?.has_booking_payment_api_key));
    setSalesProductName(String(cfg.sales_product_name || ''));
    setSalesOfferType(String(cfg.sales_offer_type || ''));
    setSalesUsp(String(cfg.sales_usp || ''));
    setSalesWorkflowCompletionMode(
      cfg.workflow_completion_mode === 'continue_dialog' ? 'continue_dialog' : 'auto_finish_on_signal'
    );
    setSalesLeadScoreScale(String(Number(cfg.lead_score_scale) === 10 ? 10 : 100));
    setSalesLeadGenerationEnabled(cfg.lead_generation_enabled !== false);
    setSalesContactsPoolOnly(Boolean(cfg.contacts_pool_only));
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


  const agentAvailabilityTimezoneOptions = useMemo(() => {
    const browser = getBrowserTimezoneSafe();
    const ordered = [...new Set([browser, agentAvailTimezone, ...COMMON_AGENT_TIMEZONES])];
    return ordered.map((tz) => ({ value: tz, label: tz }));
  }, [agentAvailTimezone]);

  const buildAgentAvailabilityBlock = (alwaysOn, timezone, weekdays) =>
    alwaysOn
      ? {
          always_on: true,
          timezone: timezone.trim() || 'Europe/Moscow',
        }
      : {
          always_on: false,
          timezone: timezone.trim() || 'Europe/Moscow',
          weekdays: weekdays.map((d) => ({
            enabled: Boolean(d.enabled),
            start: d.start,
            end: d.end,
          })),
        };

  const persistAgentAvailability = async ({ alwaysOn, timezone, weekdays } = {}) => {
    if (!selectedBotId || !selectedAgent) return false;
    const resolvedAlwaysOn = alwaysOn !== undefined ? Boolean(alwaysOn) : agentAvailAlwaysOn;
    const resolvedTimezone = timezone !== undefined ? timezone : agentAvailTimezone;
    const resolvedWeekdays = weekdays !== undefined ? weekdays : agentAvailWeekdays;

    if (!resolvedAlwaysOn) {
      const anyDay = resolvedWeekdays.some((d) => d.enabled);
      if (!anyDay) {
        showError('Включите хотя бы один день недели или вернитесь в режим 24/7');
        return false;
      }
    }

    const currentConfig = getTemplateConfig(selectedAgent);
    const nextConfig = {
      ...currentConfig,
      agent_availability: buildAgentAvailabilityBlock(
        resolvedAlwaysOn,
        resolvedTimezone,
        resolvedWeekdays,
      ),
    };
    setIsSavingAgentAvailability(true);
    try {
      await agentService.update(selectedBotId, { template_config: nextConfig });
      setSelectedAgent((prev) => (prev ? { ...prev, template_config: nextConfig } : prev));
      return true;
    } catch (error) {
      showError(error?.message || 'Не удалось сохранить режим работы');
      return false;
    } finally {
      setIsSavingAgentAvailability(false);
    }
  };

  const handleSaveAgentAvailability = async () => {
    const ok = await persistAgentAvailability();
    if (ok) showSuccess('Режим работы ассистента сохранён');
  };

  const handleToggleAgentAvailAlwaysOn = async (enabled) => {
    const next = Boolean(enabled);
    if (!next) {
      const anyDay = agentAvailWeekdays.some((d) => d.enabled);
      if (!anyDay) {
        showError('Включите хотя бы один день недели или оставьте круглосуточный режим');
        return;
      }
    }
    setAgentAvailAlwaysOn(next);
    const ok = await persistAgentAvailability({ alwaysOn: next });
    if (ok) {
      showSuccess(next ? 'Круглосуточный режим включён' : 'Расписание по дням активировано');
    } else {
      setAgentAvailAlwaysOn(!next);
    }
  };

  const handleToggleAgentAvailabilityDay = async (index, enabled) => {
    const prevWeekdays = agentAvailWeekdays;
    const nextWeekdays = prevWeekdays.map((row, i) =>
      i === index ? { ...row, enabled: Boolean(enabled) } : row,
    );
    if (!agentAvailAlwaysOn) {
      const anyDay = nextWeekdays.some((d) => d.enabled);
      if (!anyDay) {
        showError('Должен быть включён хотя бы один день недели');
        return;
      }
    }
    setAgentAvailWeekdays(nextWeekdays);
    if (!agentAvailAlwaysOn) {
      const ok = await persistAgentAvailability({ weekdays: nextWeekdays });
      if (!ok) {
        setAgentAvailWeekdays(prevWeekdays);
      }
    }
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

  const applyUserbotChannelVerified = (response) => {
    setUserbotSessionString(response?.session_string || '');
    if (response?.api_id != null) {
      setUserbotResolvedApiId(Number(response.api_id));
    }
    if (response?.api_hash) {
      setUserbotResolvedApiHash(String(response.api_hash));
    }
    const label = response?.username
      ? `@${response.username}`
      : [response?.first_name, response?.last_name].filter(Boolean).join(' ')
        || response?.phone_number
        || (response?.telegram_id ? `id: ${response.telegram_id}` : 'успешно');
    setUserbotVerifiedLabel(label);
  };

  const switchUserbotAuthMode = (mode) => {
    setUserbotAuthMode(mode);
    setUserbotAuthToken('');
    setUserbotQrAuthToken('');
    setUserbotQrDataUrl('');
    setUserbotQrNeeds2fa(false);
    setUserbotResolvedApiId(null);
    setUserbotResolvedApiHash('');
    setUserbotSessionString('');
    setUserbotVerifiedLabel('');
    setUserbotCode('');
    setUserbotPassword('');
    userbotLastQrStatusRef.current = '';
  };

  const handleUserbotQrStart = async () => {
    setIsStartingUserbotQr(true);
    try {
      const response = await agentService.startUserbotQr({});
      setUserbotQrAuthToken(response?.auth_token || '');
      setUserbotQrDataUrl(response?.qr_data_url || '');
      setUserbotQrNeeds2fa(false);
      setUserbotSessionString('');
      setUserbotVerifiedLabel('');
      userbotLastQrStatusRef.current = '';
      if (response?.already_authorized && response?.session_string) {
        applyUserbotChannelVerified(response);
        showSuccess('Сессия Telegram уже авторизована');
      } else {
        showSuccess('Отсканируйте QR в Telegram: Настройки → Устройства → Подключить устройство');
      }
    } catch (error) {
      showError(error?.message || 'Не удалось начать QR-вход');
    } finally {
      setIsStartingUserbotQr(false);
    }
  };

  const handleUserbotQrVerify2fa = async () => {
    if (!userbotQrAuthToken) {
      showError('Сначала начните QR-вход');
      return;
    }
    if (!userbotPassword.trim()) {
      showError('Введите пароль 2FA');
      return;
    }
    setIsVerifyingUserbotQr2fa(true);
    try {
      const response = await agentService.verifyUserbotQr2fa({
        auth_token: userbotQrAuthToken,
        password: userbotPassword.trim(),
      });
      applyUserbotChannelVerified(response);
      setUserbotQrNeeds2fa(false);
      showSuccess('2FA подтверждена');
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить 2FA');
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
      applyUserbotChannelVerified(response);
      showSuccess('Сессия импортирована');
    } catch (error) {
      showError(error?.message || 'Не удалось импортировать сессию');
    } finally {
      setIsImportingUserbotSession(false);
    }
  };

  useEffect(() => {
    if (!isChannelsModalOpen || channelModalTab !== 'userbot') return undefined;
    if (userbotAuthMode !== 'qr') return undefined;
    if (!userbotQrAuthToken) return undefined;
    if (userbotSessionString.trim()) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await agentService.userbotQrStatus({ auth_token: userbotQrAuthToken });
        if (cancelled) return;
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = userbotLastQrStatusRef.current;
        if (nextStatus === 'need_2fa') {
          setUserbotQrNeeds2fa(true);
          if (prevStatus !== 'need_2fa') {
            showSuccess('QR принят. Введите пароль 2FA.');
          }
        } else if (nextStatus === 'success' && response?.session_string) {
          applyUserbotChannelVerified(response);
          setUserbotQrNeeds2fa(false);
          if (prevStatus !== 'success') {
            showSuccess('Telegram userbot авторизован');
          }
        } else if (nextStatus === 'expired' || nextStatus === 'error') {
          if (prevStatus !== nextStatus) {
            showError(response?.error || 'QR-вход завершился с ошибкой');
          }
        }
        userbotLastQrStatusRef.current = nextStatus;
      } catch {
        // ignore polling errors
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [
    isChannelsModalOpen,
    channelModalTab,
    userbotAuthMode,
    userbotQrAuthToken,
    userbotSessionString,
    showError,
    showSuccess,
  ]);

  const handleRequestUserbotCode = async () => {
    if (!userbotPhone.trim()) {
      showError('Введите номер телефона');
      return;
    }
    setIsSendingUserbotCode(true);
    try {
      const response = await agentService.requestUserbotCode({
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
      applyUserbotChannelVerified(response);
      showSuccess('Код подтвержден, можно подключать userbot');
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить код');
    } finally {
      setIsVerifyingUserbotCode(false);
    }
  };

  const handleAddUserbotChannel = async () => {
    if (!selectedBotId) return;
    if (!userbotSessionString.trim()) {
      showError('Сначала завершите вход (QR, код или импорт файла)');
      return;
    }
    if (!userbotResolvedApiId || !userbotResolvedApiHash) {
      showError('Сессия userbot неполная. Повторите вход.');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addUserbotChannel({
        agent_id: selectedBotId,
        api_id: Number(userbotResolvedApiId),
        api_hash: userbotResolvedApiHash,
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
    if (!maxUserbotSessionPayload.trim()) {
      showError('Сначала завершите вход (QR, код или импорт файла)');
      return;
    }
    setIsSavingChannel(true);
    try {
      const res = await agentService.addMaxUserbotChannel({
        agent_id: selectedBotId,
        session_payload: maxUserbotSessionPayload.trim(),
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
    whatsappAutoVerifyAttemptedRef.current = false;
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
    whatsappAutoVerifyAttemptedRef.current = false;
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
      setWhatsappUserbotAuthToken('');
      showSuccess('WhatsApp userbot успешно инициализирован');
    } catch (error) {
      setIsWhatsappUserbotVerified(false);
      const message = String(error?.message || '');
      if (isWhatsappUserbotAuthSessionExpiredMessage(message)) {
        setWhatsappUserbotAuthToken('');
        whatsappAutoVerifyAttemptedRef.current = false;
      }
      showError(message || 'Не удалось подтвердить код WhatsApp');
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
        if (nextStatus === 'expired') {
          showError(response?.last_error || 'Сессия подтверждения истекла. Запросите новый QR-код.');
          setWhatsappUserbotAuthToken('');
          return;
        }
        if (nextStatus && nextStatus !== prevStatus) {
          if (nextStatus === 'failed') {
            showError(response?.last_error || 'Сессия WhatsApp завершилась с ошибкой. Запросите новый QR.');
          }
        }
        whatsappUserbotLastAuthStatusRef.current = nextStatus;

        if (nextStatus === 'paired' && !whatsappAutoVerifyAttemptedRef.current) {
          whatsappAutoVerifyAttemptedRef.current = true;
          setIsVerifyingWhatsappUserbotCode(true);
          try {
            const verifyResponse = await agentService.verifyWhatsAppUserbotCode({
              auth_token: whatsappUserbotAuthToken,
            });
            if (cancelled) return;
            setWhatsappUserbotSessionString(verifyResponse?.session_string || '');
            if (verifyResponse?.phone_number) {
              setWhatsappUserbotPhone(verifyResponse.phone_number);
            }
            setWhatsappUserbotAuthToken('');
            setIsWhatsappUserbotVerified(true);
            showSuccess('WhatsApp userbot успешно инициализирован');
          } catch (error) {
            const message = String(error?.message || '');
            if (isWhatsappUserbotAuthSessionExpiredMessage(message)) {
              setWhatsappUserbotAuthToken('');
              whatsappAutoVerifyAttemptedRef.current = false;
              showError(message || 'Сессия подтверждения истекла. Запросите новый QR-код.');
            } else {
              whatsappAutoVerifyAttemptedRef.current = false;
              if (!message.includes('еще не завершено') && !message.includes('ещё не завершено')) {
                showError(message || 'Не удалось подтвердить подключение WhatsApp');
              }
            }
          } finally {
            if (!cancelled) {
              setIsVerifyingWhatsappUserbotCode(false);
            }
          }
        }
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
  const selectedAgentBilling = selectedAgent?.billing;
  const showExtendContractButton = Boolean(
    selectedAgentBilling?.requires_subscription
    && Number(selectedAgentBilling?.monthly_price_rub || 0) > 0,
  );
  const isWidgetSupportedTemplate = WIDGET_TEMPLATE_TYPES.has(
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
                    {showExtendContractButton ? (
                      <button
                        type="button"
                        className="btn btn-outline agent-extend-contract-btn"
                        onClick={() => openContractPaymentModal(selectedAgent, 'Продление подписки')}
                      >
                        Продлить контракт
                      </button>
                    ) : null}
                    {selectedAgentBilling?.requires_subscription ? (
                      <p className="agent-billing-status">
                        {selectedAgentBilling.maintenance_grace_active
                          ? `Пробный период${typeof selectedAgentBilling.trial_days_left === 'number' ? ` (${selectedAgentBilling.trial_days_left} дн.)` : ''}`
                          : selectedAgentBilling.maintenance_current
                            ? selectedAgentBilling.maintenance_paid_until
                              ? `Подписка до ${new Date(selectedAgentBilling.maintenance_paid_until).toLocaleDateString('ru-RU')}`
                              : 'Подписка активна'
                            : 'Подписка не оплачена — агент будет отключён'}
                        {selectedAgentBilling.autopay_enabled
                          ? ` · автопродление на ${selectedAgentBilling.autopay_duration_months} мес.`
                          : ''}
                        {selectedAgentBilling.autopay_last_error
                          ? ` · ${selectedAgentBilling.autopay_last_error}`
                          : ''}
                      </p>
                    ) : null}
                  </div>

                  {/* Website block - moved to top for visibility */}
                  <div className="agent-management-block">
                    <h4 className="agent-form-channel-title">Сайт</h4>
                    {isWebsiteLoading ? (
                      <p className="help-text">Загрузка...</p>
                    ) : !agentWebsite ? (
                      <>
                        <p className="help-text">У вас еще нет сайта</p>
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleStartWebsiteBuilder}
                          disabled={isWebsiteBuilding}
                        >
                          {isWebsiteBuilding ? 'Собираем сайт...' : 'Сайт за 5 минут'}
                        </button>
                      </>
                    ) : (
                      <>
                        {isWebsiteBuilding ? (
                          <p className="help-text">Сайт собирается, это может занять до нескольких минут.</p>
                        ) : null}
                        <button
                          type="button"
                          className="btn btn-black"
                          onClick={handleOpenWebsiteConstructor}
                        >
                          Конструктор
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleOpenWebsiteView}
                        >
                          Перейти
                        </button>
                      </>
                    )}
                  </div>

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
                      onChange={handleToggleAgentAvailAlwaysOn}
                      disabled={isSavingAgentAvailability}
                      title="Круглосуточный режим (24/7)"
                      helpText="Выключите, чтобы вне заданного расписания входящие сообщения не обрабатывались и не получали ответа. Вне окна сообщение не попадает в аналитику и не вызывает LLM; пользователь не получает ответ. Подписка и блокировки пользователя проверяются как обычно."
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
                          onChange={handleToggleAdminWaitlist}
                          disabled={isSavingTemplateConfig}
                          title="Включить waitlist с авто-подбором окон"
                          helpText="Когда включено, агент сможет предлагать клиентам окна из waitlist при освобождении слотов."
                        />
                        <FeatureToggle
                          checked={adminReminderEnabled}
                          onChange={handleToggleAdminReminder}
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
                          checked={adminPaidBookingEnabled}
                          onChange={handleToggleAdminPaidBooking}
                          disabled={isSavingTemplateConfig}
                          title="Платная бронь"
                          helpText="При включении агент сначала отправляет ссылку на оплату, и только после успешной оплаты подтверждает бронь."
                        />
                        {adminPaidBookingEnabled ? (
                          <form
                            className="admin-template-field yookassa-credentials-form"
                            autoComplete="off"
                            onSubmit={(event) => event.preventDefault()}
                          >
                            {adminHasYookassaApiKey ? (
                              <p className="yookassa-credentials-form__status">
                                Ключи ЮKassa сохранены. Чтобы заменить, введите новую пару Shop ID и Secret key.
                              </p>
                            ) : null}
                            <p className="yookassa-credentials-form__hint">
                              Данные из личного кабинета ЮKassa → Настройки → Ключи API. Не используйте логин и пароль от сайта RSD.
                            </p>
                            <label htmlFor="admin_yookassa_shop_id">
                              Shop ID ЮKassa:
                            </label>
                            <input
                              id="admin_yookassa_shop_id"
                              name="yookassa-shop-id"
                              type="text"
                              inputMode="numeric"
                              className="input-main"
                              value={adminYookassaShopId}
                              onChange={(event) => setAdminYookassaShopId(event.target.value)}
                              onFocus={unlockYookassaInput}
                              placeholder={adminHasYookassaApiKey ? 'Новый Shop ID (только цифры)' : '123456'}
                              disabled={isSavingTemplateConfig}
                              autoComplete="off"
                              readOnly
                              data-lpignore="true"
                              data-1p-ignore="true"
                              data-form-type="other"
                            />
                            <label htmlFor="admin_yookassa_secret_key" className="mt-input">
                              Secret key ЮKassa:
                            </label>
                            <input
                              id="admin_yookassa_secret_key"
                              name="yookassa-secret-key"
                              type="text"
                              className="input-main yookassa-secret-input"
                              value={adminYookassaSecretKey}
                              onChange={(event) => setAdminYookassaSecretKey(event.target.value)}
                              onFocus={unlockYookassaInput}
                              placeholder={adminHasYookassaApiKey ? 'Новый Secret key (live_… или test_…)' : 'live_xxxxx'}
                              disabled={isSavingTemplateConfig}
                              autoComplete="new-password"
                              readOnly
                              spellCheck={false}
                              data-lpignore="true"
                              data-1p-ignore="true"
                              data-form-type="other"
                            />
                          </form>
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
                          helpText="Основной контур sales_manager: анализ чатов, отлов лидов и продажа. Если выключить, агент прекращает выполнение основной задачи sales_manager. Если одновременно выключить Лидогенерацию, Нейрокомментинг и Имитацию живого общения, агент будет автоматически выключен."
                        />
                        <FeatureToggle
                          checked={salesContactsPoolOnly}
                          onChange={(enabled) => handleToggleSalesActivity('contacts_pool_only', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Только контакты из пула"
                          helpText="Личные сообщения обрабатываются только для контактов из пула (Excel, лидогенерация, кому агент уже писал). Группы и каналы не сканируются. Случайные входящие в личку игнорируются."
                        />
                        <FeatureToggle
                          checked={salesNeuroCommentingEnabled}
                          onChange={(enabled) => handleToggleSalesActivity('neuro_commenting_enabled', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Нейрокомментинг"
                          helpText="Юзербот комментирует посты в каналах аккаунта, где доступен как участник. К каждому новому посту формируется короткий LLM-комментарий без фильтра по триггер-словам и без квалификации целевого лида. Для групп и чатов по-прежнему действует список триггер-слов ниже (лидогенерация и имитация общения)."
                        />
                        <FeatureToggle
                          checked={salesLiveChatSimulationEnabled}
                          onChange={(enabled) => handleToggleSalesActivity('live_chat_simulation_enabled', enabled)}
                          disabled={isSavingTemplateConfig}
                          title="Имитация живого общения"
                          helpText="Юзербот периодически включается в обсуждения по триггер-словам из списка ниже. Когда включено, юзербот может периодически вступать в разговор в чатах и отправлять 2–3 сообщения за одно включение; сообщение учитывается только если совпало хотя бы с одним триггер-словом."
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
                        <div className="sales-excel-upload-block mt-input">
                          <h4 className="agent-form-channel-title">База клиентов (Excel)</h4>
                          <p className="sales-trigger-words-hint">
                            Загрузите выгрузку 2GIS или совместимую таблицу (.xlsx). Контакты с WhatsApp
                            или Telegram сохраняются; первые сообщения ставятся в очередь с паузой 15–20 минут
                            между контактами. Если нет ответа — напоминания через 1 день, неделю и месяц.
                            Агент ведёт диалог гибко: ресепшен, запрос ЛПР, КП в чат по просьбе клиента.
                          </p>
                          <div className="sales-excel-file-upload">
                            <input
                              id={salesExcelFileInputId}
                              type="file"
                              accept=".xlsx,.xls"
                              className="sales-excel-file-upload__input"
                              onChange={handleSalesManagerExcelUpload}
                              disabled={salesExcelUploadBusy || isSavingTemplateConfig}
                            />
                            <label
                              htmlFor={salesExcelFileInputId}
                              className={`sales-excel-file-upload__label${
                                salesExcelUploadBusy || isSavingTemplateConfig ? ' is-disabled' : ''
                              }`}
                            >
                              <svg
                                className="sales-excel-file-upload__icon"
                                viewBox="0 0 24 24"
                                fill="none"
                                xmlns="http://www.w3.org/2000/svg"
                                aria-hidden="true"
                              >
                                <path
                                  d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"
                                  stroke="currentColor"
                                  strokeWidth="1.75"
                                  strokeLinejoin="round"
                                />
                                <path
                                  d="M14 2v6h6M8 13h8M8 17h5"
                                  stroke="currentColor"
                                  strokeWidth="1.75"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                              <span className="sales-excel-file-upload__title">
                                {salesExcelUploadBusy ? 'Обработка файла…' : 'Выбрать файл Excel'}
                              </span>
                              <span className="sales-excel-file-upload__formats">
                                .xlsx или .xls — выгрузка 2GIS и совместимые таблицы
                              </span>
                            </label>
                          </div>
                          {salesExcelImportInfo ? (
                            <p className="sales-trigger-words-hint">
                              Последняя загрузка: добавлено {salesExcelImportInfo.imported ?? 0}, обновлено{' '}
                              {salesExcelImportInfo.updated ?? 0}
                              {salesExcelImportInfo.skipped_no_messenger
                                ? `, без канала: ${salesExcelImportInfo.skipped_no_messenger}`
                                : ''}
                              .
                            </p>
                          ) : null}
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
                      helpText="ON: LLM формирует RAG-запросы. OFF: в RAG отправляется исходный запрос и извлекается 6 чанков. Управляет логикой поиска в базе знаний."
                    />
                    {isQATemplate ? (
                      <FeatureToggle
                        checked={isChatFreezeEnabled(selectedAgent)}
                        onChange={handleToggleChatFreeze}
                        disabled={isSavingChatFreeze}
                        title="Заморозка чата"
                        helpText="Авто-передача диалога владельцу при неуверенном ответе агента. Доступно только для шаблона Консультант (QA). Если включено, агент может пометить диалог как требующий владельца и временно заморозить чат для пользователя."
                      />
                    ) : null}
                    <FeatureToggle
                      checked={isStartProcessingEnabled(selectedAgent)}
                      onChange={handleToggleStartProcessing}
                      disabled={isSavingStartProcessing}
                      title="Обработка /start"
                      helpText="ON: /start отправляется в LLM. OFF: отправляется дефолтное/пользовательское приветствие. По умолчанию выключено: команда /start вернет текст приветствия. Включите, чтобы /start обрабатывался как обычное сообщение пользователя."
                    />
                    <FeatureToggle
                      checked={isHumanDelayEnabled(selectedAgent)}
                      onChange={handleToggleHumanDelay}
                      disabled={isSavingHumanDelay}
                      title="Имитация присутствия"
                      helpText="Агент ведёт себя как живой человек: на первое сообщение отвечает сразу, а при возобновлении неактивного диалога выдерживает паузу 1–3 минуты перед тем, как «зайти в сеть». Затем имитирует чтение входящего и набор ответа — с задержкой, пропорциональной длине текста. В пределах одного активного диалога паузы на вход-выход из сети нет. Не влияет на телефонию. По умолчанию включено для Telegram-, MAX- и WhatsApp-юзерботов."
                    />
                    <FeatureToggle
                      checked={isChatHistoryEnabled(selectedAgent)}
                      onChange={handleToggleChatHistory}
                      disabled={isSavingChatHistory}
                      title="История чата в запросе"
                      helpText="При каждом обращении в LLM передаётся полная история переписки с меткой времени и указанием кто написал — клиент или агент. Модель видит контекст всего диалога и не повторяет приветствие, помнит сказанное ранее и отвечает связно. По умолчанию включено для всех каналов, включая телефонию."
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
                    className={`connection-type-card ${channelModalTab === 'max_userbot' ? 'active' : ''}`}
                    onClick={() => setChannelModalTab('max_userbot')}
                    disabled={isSavingChannel}
                  >
                    MAX userbot
                  </button>
                  <button
                    type="button"
                    className={`connection-type-card ${channelModalTab === 'whatsapp_userbot' ? 'active' : ''}`}
                    onClick={() => setChannelModalTab('whatsapp_userbot')}
                    disabled={isSavingChannel}
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
                    Для шаблона «ИИ МОП» доступны Telegram userbot, WhatsApp userbot и/или MAX userbot.
                    Сканирование групп — только в Telegram. Рассылка по Excel: телефоны из базы
                    (MAX — только номера, без username).
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
                    <p className="help-text">
                      Как в Telegram: QR, код по SMS или файл сессии. API-ключи с my.telegram.org не нужны.
                    </p>
                    <div className="connection-type-grid connection-type-grid--channels">
                      <button
                        type="button"
                        className={`connection-type-card ${userbotAuthMode === 'qr' ? 'active' : ''}`}
                        onClick={() => switchUserbotAuthMode('qr')}
                        disabled={isSavingChannel}
                      >
                        QR-код
                      </button>
                      <button
                        type="button"
                        className={`connection-type-card ${userbotAuthMode === 'phone' ? 'active' : ''}`}
                        onClick={() => switchUserbotAuthMode('phone')}
                        disabled={isSavingChannel}
                      >
                        Код по SMS
                      </button>
                      <button
                        type="button"
                        className={`connection-type-card ${userbotAuthMode === 'file' ? 'active' : ''}`}
                        onClick={() => switchUserbotAuthMode('file')}
                        disabled={isSavingChannel}
                      >
                        Файл сессии
                      </button>
                    </div>
                    {userbotAuthMode === 'qr' ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleUserbotQrStart}
                          disabled={isSavingChannel || isStartingUserbotQr}
                        >
                          {isStartingUserbotQr ? 'Генерация QR...' : 'Показать QR-код'}
                        </button>
                        {userbotQrDataUrl ? (
                          <div className="userbot-qr-wrap">
                            <img src={userbotQrDataUrl} alt="Telegram QR" className="userbot-qr-image" />
                          </div>
                        ) : null}
                        <input
                          type="password"
                          className="input-main"
                          placeholder="Пароль 2FA (если включена)"
                          value={userbotPassword}
                          onChange={(event) => setUserbotPassword(event.target.value)}
                          disabled={isSavingChannel}
                        />
                        <button
                          type="button"
                          className="btn btn-outline"
                          onClick={handleUserbotQrVerify2fa}
                          disabled={isSavingChannel || isVerifyingUserbotQr2fa || !userbotQrNeeds2fa}
                        >
                          {isVerifyingUserbotQr2fa ? 'Проверка...' : 'Подтвердить 2FA'}
                        </button>
                      </>
                    ) : null}
                    {userbotAuthMode === 'phone' ? (
                      <>
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
                      </>
                    ) : null}
                    {userbotAuthMode === 'file' ? (
                      <>
                        <UserbotSessionFileUpload
                          disabled={isSavingChannel}
                          isImporting={isImportingUserbotSession}
                          onFileSelect={handleUserbotImportSession}
                        />
                      </>
                    ) : null}
                    {userbotVerifiedLabel ? (
                      <p className="help-text userbot-success">Готово: {userbotVerifiedLabel}</p>
                    ) : null}
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
                    <MaxUserbotAuthPanel
                      disabled={isSavingChannel}
                      onSessionReady={({ session_payload }) => {
                        setMaxUserbotSessionPayload(session_payload || '');
                      }}
                      onClear={() => {
                        setMaxUserbotSessionPayload('');
                      }}
                      onError={showError}
                      onSuccess={showSuccess}
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
                      disabled={isSavingChannel || !maxUserbotSessionPayload.trim()}
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

      <AgentContractPaymentModal
        isOpen={Boolean(contractModalAgent)}
        agent={contractModalAgent}
        title={contractModalTitle}
        onClose={closeContractPaymentModal}
        onSubmit={handleContractPaymentSubmit}
        isProcessing={isContractPaymentProcessing}
      />

      <WebsiteBuilderWizard
        isOpen={isWebsiteWizardOpen}
        onClose={handleWebsiteWizardClose}
        agent={selectedAgent}
        onSuccess={handleWebsiteWizardSuccess}
      />

      <CreateChoiceModal
        isOpen={isCreateChoiceModalOpen}
        onClose={() => setIsCreateChoiceModalOpen(false)}
      />
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