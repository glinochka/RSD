import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import agentService from '../services/agentService';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import { findTelephonyChannel, telephonyCallTitle, telephonyStatusLabel } from '../utils/telephony';
import { formatServicePriceLabel, minorToRubInput, rubToMinor } from '../utils/bookingPrice';
import DemoBadge, { TitleWithDemoBadge } from '../components/DemoBadge';
import '../styles/agentDetailedAnalytics.css';

const ANALYTICS_SECTIONS = {
  OVERVIEW: 'overview',
  CHATS: 'chats',
  TELEPHONY: 'telephony',
  BROADCAST: 'broadcast',
  OPERATIONS: 'operations',
  REFUNDS: 'refunds',
};

const refundChannelLabel = (channel) => {
  const key = String(channel || '').trim().toLowerCase();
  if (key === 'telegram' || key === 'telegram_bot') return 'Telegram';
  if (key === 'telegram_userbot') return 'Telegram (аккаунт)';
  if (key === 'whatsapp_userbot') return 'WhatsApp';
  if (key === 'external_api') return 'API';
  return key || '—';
};

const refundStatusLabel = (status) => {
  const key = String(status || '').trim().toLowerCase();
  if (key === 'pending') return 'Ожидает решения';
  if (key === 'refunded') return 'Возврат выполнен';
  if (key === 'rejected') return 'Отклонена';
  if (key === 'failed') return 'Ошибка возврата';
  return key || '—';
};

const BROADCAST_LIMIT_OPTIONS = [100, 250, 500, 1000, 2000, 5000];
const CHART_PERIODS = [7, 30, 90];
const isPortraitFeatureEnabled = (agent) => {
  const cfg = agent?.template_config;
  if (!cfg || typeof cfg !== 'object') return true;
  return cfg.enable_chat_portrait !== false;
};

const formatNumber = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat('ru-RU').format(value);
};

const formatPercent = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return '0%';
  return `${numeric.toFixed(1)}%`;
};

const formatMinutes = (value) => {
  const minutes = Number(value || 0);
  if (!Number.isFinite(minutes) || minutes <= 0) return '0 мин';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h <= 0) return `${m} мин`;
  if (m <= 0) return `${h} ч`;
  return `${h} ч ${m} мин`;
};

const formatDateTime = (value, empty = '') => {
  if (!value) return empty;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

const formatDateShort = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
  }).format(date);
};

const _padTwo = (n) => String(n).padStart(2, '0');
const _toLocalIso = (d) =>
  `${d.getFullYear()}-${_padTwo(d.getMonth() + 1)}-${_padTwo(d.getDate())}T${_padTwo(d.getHours())}:${_padTwo(d.getMinutes())}:${_padTwo(d.getSeconds())}`;

const toIsoInputValue = (value) => {
  if (!value) return '';
  const raw = String(value).trim();
  if (raw.length >= 16 && !raw.includes('Z') && !raw.includes('+')) {
    return raw.replace(' ', 'T').slice(0, 16);
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return '';
  return _toLocalIso(date).slice(0, 16);
};

const fromIsoInputValue = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.length >= 16 && !raw.includes('Z') && !raw.includes('+')) {
    return raw;
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '';
  return _toLocalIso(parsed);
};

const addMinutesToLocalDateTime = (value, minutes) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const normalized = raw.length === 16 ? `${raw}:00` : raw;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return '';
  date.setMinutes(date.getMinutes() + Number(minutes || 0));
  return _toLocalIso(date).slice(0, 16);
};

const startOfDay = (value) => {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
};

const endOfDay = (value) => {
  const date = new Date(value);
  date.setHours(23, 59, 59, 999);
  return date;
};

const startOfWeek = (value) => {
  const date = startOfDay(value);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  return date;
};

const endOfWeek = (value) => {
  const start = startOfWeek(value);
  return endOfDay(new Date(start.getTime() + 6 * 24 * 60 * 60 * 1000));
};

const toDayKey = (value) => {
  const date = value instanceof Date ? new Date(value) : new Date(value || '');
  if (Number.isNaN(date.getTime())) return '';
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const channelLabel = (channel) => {
  if (channel === 'telegram_userbot') return 'Telegram userbot';
  if (channel === 'telegram') return 'Telegram bot';
  if (channel === 'max_bot') return 'MAX bot';
  if (channel === 'max_userbot') return 'MAX userbot';
  if (channel === 'whatsapp_userbot') return 'WhatsApp userbot';
  if (channel === 'external_api') return 'External API';
  if (channel === 'whatsapp_business_api') return 'WhatsApp Business API';
  if (channel === 'phone') return 'Телефония';
  return channel || 'unknown';
};

const normalizeLeadStatus = (status) => String(status || '').trim().toUpperCase();

const leadStatusMeta = (status) => {
  const key = normalizeLeadStatus(status);
  if (key === 'REPLIED_NEGATIVE' || key === 'SKIPPED') {
    return { key, label: 'Отказ', warmth: 'rejected' };
  }
  if (key === 'HANDOFF_CRM') {
    return { key, label: 'Успешно закрыт', warmth: 'closed' };
  }
  if (key === 'REPLIED_POSITIVE') {
    return { key, label: 'Прогрет', warmth: 'warmed' };
  }
  if (key === 'DISCOVERED' || key === 'QUALIFIED' || key === 'QUEUED' || key === 'SENT') {
    return { key, label: 'В работе', warmth: 'in_work' };
  }
  if (key === 'NO_REPLY') {
    return { key, label: 'Без ответа', warmth: 'in_work' };
  }
  if (!key) {
    return { key: 'UNKNOWN', label: 'Статус не определен', warmth: 'unknown' };
  }
  return { key, label: key, warmth: 'unknown' };
};

const formatCallDuration = (sec) => {
  if (sec == null || Number.isNaN(Number(sec))) return '—';
  const total = Math.max(0, Number(sec));
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m <= 0) return `${s} с`;
  return `${m} мин ${s} с`;
};

const buildOverviewMetrics = (summary, docsCount) => {
  const totalUsers = Number(summary?.unique_users || 0);
  const totalQuestions = Number(summary?.total_questions || 0);
  const returningUsers = Number(summary?.returned_over_time_users || 0);
  const avgQuestionsPerUser = Number(summary?.avg_questions_per_user || 0);
  const conversionToQualified = Number(summary?.qualified_leads_share_percent || 0);

  return [
    { id: 'users', label: 'Написало агенту', value: formatNumber(totalUsers) },
    { id: 'questions', label: 'Всего вопросов', value: formatNumber(totalQuestions) },
    { id: 'returning', label: 'Вернулось через время', value: formatNumber(returningUsers) },
    { id: 'avg', label: 'Среднее вопросов на пользователя', value: avgQuestionsPerUser.toFixed(1) },
    { id: 'qualified', label: 'Доля квалифицированных лидов', value: `${conversionToQualified.toFixed(1)}%` },
    { id: 'docs', label: 'Документов в базе знаний', value: formatNumber(docsCount) },
  ];
};

const buildCrmActionMetrics = (crmActions) => {
  if (!crmActions) return [];
  return [
    {
      id: 'crm-tool-calls',
      label: 'Всего CRM tool calls',
      value: formatNumber(Number(crmActions.tool_calls_total || 0)),
    },
    {
      id: 'crm-success-share',
      label: 'Доля успешных tool calls',
      value: formatPercent(crmActions.success_share_percent),
    },
    {
      id: 'crm-latency',
      label: 'Средняя latency CRM операций',
      value: `${formatNumber(Number(crmActions.avg_latency_ms || 0))} мс`,
    },
    {
      id: 'crm-p95-latency',
      label: 'P95 latency CRM операций',
      value: `${formatNumber(Number(crmActions.p95_latency_ms || 0))} мс`,
    },
    {
      id: 'crm-fallback',
      label: 'Частота fallback-to-text',
      value: formatPercent(crmActions.fallback_frequency_percent),
    },
    {
      id: 'crm-error-budget',
      label: 'Использование error budget',
      value: formatPercent(crmActions?.error_budget?.used_percent),
    },
  ];
};

const BroadcastLimitSelect = ({ value, onChange, disabled, options }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="analytics-broadcast-custom" ref={rootRef}>
      <button
        type="button"
        className="analytics-broadcast-custom-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Максимум получателей за одну рассылку"
        onClick={() => !disabled && setOpen((o) => !o)}
      >
        <span className="analytics-broadcast-custom-trigger-value">{formatNumber(value)}</span>
        <span className="analytics-broadcast-custom-trigger-chevron" aria-hidden />
      </button>
      {open ? (
        <ul className="analytics-broadcast-custom-menu" role="listbox" aria-label="Лимит получателей">
          {options.map((n) => (
            <li key={n} role="none">
              <button
                type="button"
                role="option"
                aria-selected={n === value}
                className={`analytics-broadcast-custom-option ${n === value ? 'analytics-broadcast-custom-option--selected' : ''}`}
                onClick={() => {
                  onChange(n);
                  setOpen(false);
                }}
              >
                {formatNumber(n)}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
};

const AnalyticsCustomSelect = ({
  value,
  onChange,
  options,
  placeholder = '',
  disabled = false,
  ariaLabel = 'Выбор значения',
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const normalizedValue = value == null ? '' : String(value);
  const selectedOption = options.find((option) => String(option.value) === normalizedValue);
  const displayLabel = selectedOption?.label || placeholder || 'Выберите значение';

  return (
    <div className={`analytics-ops-custom-select ${disabled ? 'analytics-ops-custom-select--disabled' : ''}`} ref={rootRef}>
      <button
        type="button"
        className={`analytics-ops-custom-select-trigger input-main ${open ? 'analytics-ops-custom-select-trigger--active' : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => !disabled && setOpen((prev) => !prev)}
      >
        <span className={`analytics-ops-custom-select-value ${selectedOption ? '' : 'analytics-ops-custom-select-value--placeholder'}`}>
          {displayLabel}
        </span>
        <span className="analytics-ops-custom-select-chevron" aria-hidden />
      </button>
      {open ? (
        <ul className="analytics-ops-custom-select-menu" role="listbox" aria-label={ariaLabel}>
          {options.map((option) => {
            const optionValue = String(option.value ?? '');
            const isSelected = optionValue === normalizedValue;
            return (
              <li key={`${ariaLabel}-${optionValue || 'empty'}`} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`analytics-ops-custom-select-option ${isSelected ? 'analytics-ops-custom-select-option--selected' : ''}`}
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                >
                  {option.label}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
};

const CalendarAnchorPicker = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(() => startOfDay(value || new Date()));
  const rootRef = useRef(null);

  useEffect(() => {
    if (!value) return;
    setViewMonth(startOfDay(value));
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pickerAnchor = startOfDay(viewMonth || new Date());
  const monthTitle = pickerAnchor.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  const firstDay = new Date(pickerAnchor.getFullYear(), pickerAnchor.getMonth(), 1);
  const lastDay = new Date(pickerAnchor.getFullYear(), pickerAnchor.getMonth() + 1, 0);
  const gridStart = startOfWeek(firstDay);
  const gridEnd = endOfWeek(lastDay);
  const monthDays = [];
  for (let cursor = new Date(gridStart); cursor <= gridEnd; cursor.setDate(cursor.getDate() + 1)) {
    monthDays.push(new Date(cursor));
  }
  const selectedDayKey = toDayKey(value);
  const todayKey = toDayKey(new Date());
  const triggerLabel = (value || new Date()).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="analytics-date-picker" ref={rootRef}>
      <button
        type="button"
        className={`analytics-date-picker-trigger ${open ? 'analytics-date-picker-trigger--active' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="analytics-date-picker-trigger-label">Дата</span>
        <strong className="analytics-date-picker-trigger-value">{triggerLabel}</strong>
      </button>

      {open ? (
        <div className="analytics-date-picker-popover" role="dialog" aria-label="Выбор даты">
          <div className="analytics-date-picker-head">
            <button
              type="button"
              className="btn btn-outline analytics-date-picker-nav-btn"
              onClick={() => setViewMonth(new Date(pickerAnchor.getFullYear(), pickerAnchor.getMonth() - 1, 1))}
            >
              ←
            </button>
            <strong>{monthTitle}</strong>
            <button
              type="button"
              className="btn btn-outline analytics-date-picker-nav-btn"
              onClick={() => setViewMonth(new Date(pickerAnchor.getFullYear(), pickerAnchor.getMonth() + 1, 1))}
            >
              →
            </button>
          </div>

          <div className="analytics-date-picker-grid analytics-date-picker-grid--weekday">
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((weekday) => (
              <span key={weekday}>{weekday}</span>
            ))}
          </div>
          <div className="analytics-date-picker-grid analytics-date-picker-grid--days">
            {monthDays.map((day) => {
              const dayKey = toDayKey(day);
              const isCurrentMonth = day.getMonth() === pickerAnchor.getMonth();
              const isSelected = dayKey === selectedDayKey;
              const isToday = dayKey === todayKey;
              return (
                <button
                  key={dayKey}
                  type="button"
                  className={`analytics-date-picker-day ${!isCurrentMonth ? 'analytics-date-picker-day--muted' : ''} ${isSelected ? 'analytics-date-picker-day--selected' : ''} ${isToday ? 'analytics-date-picker-day--today' : ''}`}
                  onClick={() => {
                    const picked = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 12, 0, 0, 0);
                    onChange(picked);
                    setViewMonth(startOfDay(picked));
                    setOpen(false);
                  }}
                >
                  {day.getDate()}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            className="btn btn-outline analytics-date-picker-today-btn"
            onClick={() => {
              const today = startOfDay(new Date());
              onChange(today);
              setViewMonth(today);
              setOpen(false);
            }}
          >
            Сегодня
          </button>
        </div>
      ) : null}
    </div>
  );
};

const mapChatsPayload = (payload) => {
  const users = Array.isArray(payload?.users) ? payload.users : [];
  return users.map((user) => ({
    id: user.chat_key || `${user.chat_channel || 'telegram'}:${user.user_external_id}`,
    userExternalId: user.user_external_id,
    channel: user.chat_channel || 'telegram',
    name: user.user_display_name || `Пользователь ${user.user_external_id}`,
    questions: Number(user.questions_count || 0),
    lastMessageAt: formatDateTime(user.last_message_at),
    isFrozen: Boolean(user.is_frozen),
    leadStatus: normalizeLeadStatus(user.lead_status),
    chatPortrait: (Array.isArray(user.messages) ? user.messages : [])
      .filter((item) => item?.role === 'portrait' && String(item?.text || '').trim())
      .sort((a, b) => new Date(a?.created_at || 0).getTime() - new Date(b?.created_at || 0).getTime())
      .at(-1)?.text || '',
    messages: (Array.isArray(user.messages) ? user.messages : [])
      .filter((item) => item?.role !== 'portrait')
      .map((item, index) => ({
        id: `${user.chat_key || user.user_external_id}-${index}-${item.created_at || 'time'}`,
        role: item.role,
        text: item.text,
        timestamp: formatDateTime(item.created_at),
        channel: item.channel,
      })),
  }));
};

const AnalyticsChart = ({ timeline, selectedDays, onChangeDays, isLoading }) => {
  const points = Array.isArray(timeline) ? timeline : [];
  const width = 900;
  const height = 260;
  const paddingX = 40;
  const paddingY = 20;
  const chartWidth = width - paddingX * 2;
  const chartHeight = height - paddingY * 2;

  const series = [
    { key: 'users_all_time', label: 'Пользователи за все время', color: '#111827' },
    { key: 'users_today', label: 'Пользователи за сегодня', color: '#2563eb' },
    { key: 'new_users', label: 'Новые пользователи', color: '#16a34a' },
    { key: 'questions_today', label: 'Вопросы сегодня', color: '#dc2626' },
  ];

  const maxValue = Math.max(
    1,
    ...points.flatMap((item) => series.map((serie) => Number(item[serie.key] || 0)))
  );

  const toLine = (key) =>
    points
      .map((item, index) => {
        const x =
          paddingX + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
        const value = Number(item[key] || 0);
        const y = paddingY + chartHeight - (value / maxValue) * chartHeight;
        return `${x},${y}`;
      })
      .join(' ');

  return (
    <div className="analytics-chart-block">
      <div className="analytics-chart-topbar">
        <h4>Динамика метрик</h4>
        <div className="analytics-period-switcher" role="group" aria-label="Период графика">
          {CHART_PERIODS.map((days) => (
            <button
              key={days}
              type="button"
              className={`analytics-period-btn ${selectedDays === days ? 'analytics-period-btn--active' : ''}`}
              onClick={() => onChangeDays(days)}
            >
              {days} дн
            </button>
          ))}
        </div>
      </div>
      <div className="analytics-chart-legend">
        {series.map((serie) => (
          <span key={serie.key}>
            <i style={{ backgroundColor: serie.color }} />
            {serie.label}
          </span>
        ))}
      </div>
      <div className="analytics-chart-wrapper">
        {isLoading ? (
          <p className="analytics-chart-empty">Загрузка данных графика...</p>
        ) : points.length === 0 ? (
          <p className="analytics-chart-empty">Недостаточно данных для графика</p>
        ) : (
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="analytics-chart-svg">
            <line
              className="analytics-chart-axis"
              x1={paddingX}
              y1={paddingY}
              x2={paddingX}
              y2={height - paddingY}
            />
            <line
              className="analytics-chart-axis"
              x1={paddingX}
              y1={height - paddingY}
              x2={width - paddingX}
              y2={height - paddingY}
            />
            {series.map((serie) => (
              <g key={serie.key}>
                <polyline
                  points={toLine(serie.key)}
                  fill="none"
                  stroke={serie.color}
                  strokeWidth="2"
                />
                {points.map((item, index) => {
                  const x =
                    paddingX +
                    (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
                  const value = Number(item[serie.key] || 0);
                  const y = paddingY + chartHeight - (value / maxValue) * chartHeight;
                  return (
                    <circle key={`${serie.key}-${item.date}`} cx={x} cy={y} r="3.2" fill={serie.color}>
                      <title>{`${serie.label}\n${formatDateShort(item.date)}: ${formatNumber(value)}`}</title>
                    </circle>
                  );
                })}
              </g>
            ))}
          </svg>
        )}
      </div>
      <div className="analytics-chart-caption">
        Наведите на точки, чтобы увидеть точные значения за день.
      </div>
    </div>
  );
};

const AgentDetailedAnalyticsPageContent = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showError, showSuccess } = useNotification();
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSection, setSelectedSection] = useState(ANALYTICS_SECTIONS.OVERVIEW);
  const [agent, setAgent] = useState(null);
  const _DEFAULT_RESOURCE_TYPE_OPTIONS = [
    { value: 'chair', label: 'chair' },
    { value: 'room', label: 'room' },
    { value: 'equipment', label: 'equipment' },
  ];
  const [metrics, setMetrics] = useState([]);
  const [crmActionMetrics, setCrmActionMetrics] = useState([]);
  const [crmActions, setCrmActions] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [selectedDays, setSelectedDays] = useState(30);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [chatUsers, setChatUsers] = useState([]);
  const [chatChannelFilter, setChatChannelFilter] = useState('all');
  const [telephonyCalls, setTelephonyCalls] = useState([]);
  const [telephonyCallsLoading, setTelephonyCallsLoading] = useState(false);
  const [selectedCallId, setSelectedCallId] = useState(null);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [ownerReplyText, setOwnerReplyText] = useState('');
  const [isSendingOwnerReply, setIsSendingOwnerReply] = useState(false);
  const [isTogglingFreeze, setIsTogglingFreeze] = useState(false);
  const [chatViewMode, setChatViewMode] = useState('chat');
  const [broadcastStats, setBroadcastStats] = useState(null);
  const [broadcastStatsLoading, setBroadcastStatsLoading] = useState(false);
  const [broadcastBody, setBroadcastBody] = useState('');
  const [broadcastSkipFrozen, setBroadcastSkipFrozen] = useState(true);
  const [broadcastMaxRecipients, setBroadcastMaxRecipients] = useState(500);
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState(null);
  const [waBroadcastStats, setWaBroadcastStats] = useState(null);
  const [waBroadcastStatsLoading, setWaBroadcastStatsLoading] = useState(false);
  const [waBroadcastBody, setWaBroadcastBody] = useState('');
  const [waBroadcastResult, setWaBroadcastResult] = useState(null);
  const [isWaBroadcasting, setIsWaBroadcasting] = useState(false);
  const [staffItems, setStaffItems] = useState([]);
  const [resourceItems, setResourceItems] = useState([]);
  const [serviceItems, setServiceItems] = useState([]);
  const [scheduleItems, setScheduleItems] = useState([]);
  const [appointmentItems, setAppointmentItems] = useState([]);
  const [refundRequestItems, setRefundRequestItems] = useState([]);
  const [calendarScheduleItems, setCalendarScheduleItems] = useState([]);
  const [calendarAppointmentItems, setCalendarAppointmentItems] = useState([]);
  const [occupancyData, setOccupancyData] = useState(null);
  const [opsLoading, setOpsLoading] = useState(false);
  const [calendarView, setCalendarView] = useState('day');
  const [calendarAnchor, setCalendarAnchor] = useState(() => new Date());
  const [selectedCalendarDay, setSelectedCalendarDay] = useState(null);
  const [calendarShiftDraft, setCalendarShiftDraft] = useState({
    staff_id: '',
    resource_id: '',
    ranges: [{ starts_at: '09:00', ends_at: '18:00' }],
  });
  const [editingStaffId, setEditingStaffId] = useState(null);
  const [editingResourceId, setEditingResourceId] = useState(null);
  const [editingServiceId, setEditingServiceId] = useState(null);
  const [editingStaffDraft, setEditingStaffDraft] = useState({ full_name: '', role: 'master', specializations: '' });
  const [editingResourceDraft, setEditingResourceDraft] = useState({ title: '', resource_type: '' });
  const [editingServiceDraft, setEditingServiceDraft] = useState({
    title: '',
    target_role: 'master',
    duration_minutes: 60,
    price_rub: '',
    resource_type_filters: '',
  });
  const [newStaffDraft, setNewStaffDraft] = useState({ full_name: '', role: 'master', specializations: '' });
  const [newResourceDraft, setNewResourceDraft] = useState({ title: '', resource_type: '' });
  const [newServiceDraft, setNewServiceDraft] = useState({
    title: '',
    target_role: 'master',
    duration_minutes: 60,
    price_rub: '',
    resource_type_filters: '',
  });
  const [newScheduleDraft, setNewScheduleDraft] = useState({
    starts_at: '',
    ends_at: '',
    staff_id: '',
    resource_id: '',
    slot_kind: 'work',
  });
  const [newAppointmentDraft, setNewAppointmentDraft] = useState({
    client_external_id: '',
    client_name: '',
    starts_at: '',
    ends_at: '',
    staff_id: '',
    resource_id: '',
    service_id: '',
    notes: '',
  });
  const [selectedDrilldown, setSelectedDrilldown] = useState(null);
  const [waitlistItems, setWaitlistItems] = useState([]);
  const [clientProfileItems, setClientProfileItems] = useState([]);
  const [quickReplyItems, setQuickReplyItems] = useState([]);
  const [newWaitlistDraft, setNewWaitlistDraft] = useState({
    client_external_id: '',
    client_name: '',
    service_id: '',
    desired_staff_id: '',
    desired_resource_id: '',
  });
  const [newQuickReplyDraft, setNewQuickReplyDraft] = useState({ title: '', body: '', category: '' });
  const [reminderRunResult, setReminderRunResult] = useState(null);

  const botId = useMemo(() => Number(id), [id]);
  const isCrmAdminTemplate = String(agent?.template_type || '').trim().toLowerCase() === 'crm_admin';

  const plannedBroadcastRecipients = useMemo(() => {
    if (!broadcastStats) return 0;
    const base = broadcastSkipFrozen
      ? Number(broadcastStats.eligible_when_skip_frozen || 0)
      : Number(broadcastStats.telegram_users_total || 0);
    return Math.min(base, broadcastMaxRecipients);
  }, [broadcastStats, broadcastSkipFrozen, broadcastMaxRecipients]);

  const plannedWaBroadcastRecipients = useMemo(() => {
    if (!waBroadcastStats) return 0;
    const base = broadcastSkipFrozen
      ? Number(waBroadcastStats.eligible_when_skip_frozen || 0)
      : Number(waBroadcastStats.whatsapp_userbot_users_total || 0);
    return Math.min(base, broadcastMaxRecipients);
  }, [waBroadcastStats, broadcastSkipFrozen, broadcastMaxRecipients]);

  const operationRange = useMemo(() => {
    const anchor = startOfDay(calendarAnchor);
    if (calendarView === 'week') {
      const start = startOfWeek(anchor);
      const end = endOfDay(new Date(start.getTime() + 6 * 24 * 60 * 60 * 1000));
      return { start, end };
    }
    return { start: startOfDay(anchor), end: endOfDay(anchor) };
  }, [calendarAnchor, calendarView]);

  const monthRange = useMemo(() => {
    const anchor = startOfDay(calendarAnchor);
    const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 0, 0, 0, 0);
    const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 23, 59, 59, 999);
    return { start, end };
  }, [calendarAnchor]);

  const loadOperationsDashboard = async () => {
    if (!Number.isFinite(botId) || botId <= 0) return;
    setOpsLoading(true);
    try {
      const paramsBase = { bot_id: botId };
      const [
        staff,
        resources,
        services,
        schedule,
        appointments,
        occupancy,
        waitlist,
        profiles,
        quickReplies,
        calendarSchedule,
        calendarAppointments,
      ] = await Promise.all([
        agentService.listAdminTemplateStaff(paramsBase),
        agentService.listAdminTemplateResources(paramsBase),
        agentService.listAdminTemplateServices(paramsBase),
        agentService.listAdminTemplateSchedule({
          ...paramsBase,
          starts_at: _toLocalIso(operationRange.start),
          ends_at: _toLocalIso(operationRange.end),
          active_only: true,
        }),
        agentService.listAdminTemplateAppointments({
          ...paramsBase,
          starts_at: _toLocalIso(operationRange.start),
          ends_at: _toLocalIso(operationRange.end),
        }),
        agentService.getAdminTemplateOccupancy({
          ...paramsBase,
          starts_at: _toLocalIso(operationRange.start),
          ends_at: _toLocalIso(operationRange.end),
          granularity_minutes: 30,
        }),
        agentService.listAdminTemplateWaitlist(paramsBase),
        agentService.listAdminTemplateClientProfiles(paramsBase),
        agentService.listAdminTemplateQuickReplies(paramsBase),
        agentService.listAdminTemplateSchedule({
          ...paramsBase,
          starts_at: _toLocalIso(monthRange.start),
          ends_at: _toLocalIso(monthRange.end),
          active_only: true,
        }),
        agentService.listAdminTemplateAppointments({
          ...paramsBase,
          starts_at: _toLocalIso(monthRange.start),
          ends_at: _toLocalIso(monthRange.end),
        }),
      ]);
      setStaffItems(Array.isArray(staff?.items) ? staff.items : []);
      setResourceItems(Array.isArray(resources?.items) ? resources.items : []);
      setServiceItems(Array.isArray(services?.items) ? services.items : []);
      setScheduleItems(Array.isArray(schedule?.items) ? schedule.items : []);
      setAppointmentItems(Array.isArray(appointments?.items) ? appointments.items : []);
      setCalendarScheduleItems(Array.isArray(calendarSchedule?.items) ? calendarSchedule.items : []);
      setCalendarAppointmentItems(Array.isArray(calendarAppointments?.items) ? calendarAppointments.items : []);
      setOccupancyData(occupancy || null);
      setSelectedDrilldown(null);
      setWaitlistItems(Array.isArray(waitlist?.items) ? waitlist.items : []);
      setClientProfileItems(Array.isArray(profiles?.items) ? profiles.items : []);
      setQuickReplyItems(Array.isArray(quickReplies?.items) ? quickReplies.items : []);
    } catch (error) {
      showError(error?.message || 'Не удалось загрузить операционный дашборд');
    } finally {
      setOpsLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isFinite(botId) || botId <= 0) {
      showError('Некорректный id агента');
      navigate(NAVIGATION_ROUTES.AGENTS);
      return;
    }

    const loadData = async () => {
      setIsLoading(true);
      try {
        const [agentData, docs, summary, chats, crmActionsPayload] = await Promise.all([
          agentService.getById(botId),
          agentService.getDocumentsByBotId(botId),
          agentService.getAnalyticsSummary(botId),
          agentService.getAnalyticsChats(botId, { limit_users: 100, messages_per_user: 100 }),
          agentService.getAnalyticsCrmActions(botId),
        ]);
        const mappedUsers = mapChatsPayload(chats);
        setAgent(agentData);
        setChatUsers(mappedUsers);
        setSelectedUserId(mappedUsers[0]?.id || null);
        setMetrics(buildOverviewMetrics(summary, docs?.length || 0));
        setCrmActions(crmActionsPayload || null);
        setCrmActionMetrics(buildCrmActionMetrics(crmActionsPayload));
      } catch (error) {
        showError(error?.message || 'Не удалось загрузить аналитику агента');
        navigate(NAVIGATION_ROUTES.AGENTS);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [botId, navigate, showError]);

  useEffect(() => {
    if (!Number.isFinite(botId) || botId <= 0) return;

    const loadTimeline = async () => {
      setIsChartLoading(true);
      try {
        const timeseries = await agentService.getAnalyticsTimeseries(botId, selectedDays);
        setTimeline(Array.isArray(timeseries?.timeline) ? timeseries.timeline : []);
      } catch (error) {
        setTimeline([]);
        showError(error?.message || 'Не удалось загрузить график аналитики');
      } finally {
        setIsChartLoading(false);
      }
    };

    loadTimeline();
  }, [botId, selectedDays, showError]);

  useEffect(() => {
    if (selectedSection !== ANALYTICS_SECTIONS.TELEPHONY) return;
    if (!Number.isFinite(botId) || botId <= 0) return;

    const loadCalls = async () => {
      setTelephonyCallsLoading(true);
      try {
        const data = await agentService.getTelephonyCalls(botId, { limit: 50, include_turns: true });
        const list = Array.isArray(data?.calls) ? data.calls : [];
        setTelephonyCalls(list);
        setSelectedCallId(list[0]?.id ?? null);
      } catch (error) {
        setTelephonyCalls([]);
        showError(error?.message || 'Не удалось загрузить звонки');
      } finally {
        setTelephonyCallsLoading(false);
      }
    };

    loadCalls();
  }, [botId, selectedSection, showError]);

  const filteredChatUsers = useMemo(() => {
    if (chatChannelFilter === 'all') return chatUsers;
    return chatUsers.filter((user) => user.channel === chatChannelFilter);
  }, [chatUsers, chatChannelFilter]);

  const selectedCall = useMemo(
    () => telephonyCalls.find((call) => call.id === selectedCallId) || null,
    [telephonyCalls, selectedCallId]
  );

  const telephonyChannel = useMemo(() => findTelephonyChannel(agent?.channels), [agent?.channels]);

  useEffect(() => {
    if (selectedSection !== ANALYTICS_SECTIONS.BROADCAST) return;
    if (!Number.isFinite(botId) || botId <= 0) return;

    const loadBroadcastStats = async () => {
      setBroadcastStatsLoading(true);
      setBroadcastResult(null);
      try {
        const data = await agentService.getTelegramBroadcastRecipients(botId);
        setBroadcastStats(data);
      } catch (error) {
        setBroadcastStats(null);
        showError(error?.message || 'Не удалось загрузить данные рассылки (Telegram)');
      } finally {
        setBroadcastStatsLoading(false);
      }
    };

    const loadWaBroadcastStats = async () => {
      setWaBroadcastStatsLoading(true);
      setWaBroadcastResult(null);
      try {
        const data = await agentService.getWhatsappUserbotBroadcastRecipients(botId);
        setWaBroadcastStats(data);
      } catch (error) {
        setWaBroadcastStats(null);
        showError(error?.message || 'Не удалось загрузить данные рассылки (WhatsApp userbot)');
      } finally {
        setWaBroadcastStatsLoading(false);
      }
    };

    loadBroadcastStats();
    loadWaBroadcastStats();
  }, [selectedSection, botId, showError]);

  const loadRefundRequests = async () => {
    if (!Number.isFinite(botId) || botId <= 0) return;
    setOpsLoading(true);
    try {
      const data = await agentService.listAdminTemplateRefundRequests({ bot_id: botId });
      setRefundRequestItems(Array.isArray(data?.items) ? data.items : []);
    } catch (error) {
      showError(error?.message || 'Не удалось загрузить заявки на возврат');
    } finally {
      setOpsLoading(false);
    }
  };

  useEffect(() => {
    if (!isCrmAdminTemplate) return;
    if (selectedSection !== ANALYTICS_SECTIONS.OPERATIONS) return;
    loadOperationsDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSection, isCrmAdminTemplate, botId, operationRange.start, operationRange.end, monthRange.start, monthRange.end]);

  useEffect(() => {
    if (!isCrmAdminTemplate) return;
    if (selectedSection !== ANALYTICS_SECTIONS.REFUNDS) return;
    loadRefundRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSection, isCrmAdminTemplate, botId]);

  useEffect(() => {
    if (!isCrmAdminTemplate || !Number.isFinite(botId) || botId <= 0) return;
    agentService
      .listAdminTemplateRefundRequests({ bot_id: botId })
      .then((data) => {
        setRefundRequestItems(Array.isArray(data?.items) ? data.items : []);
      })
      .catch(() => {});
  }, [isCrmAdminTemplate, botId]);

  const selectedUser = useMemo(
    () => filteredChatUsers.find((user) => user.id === selectedUserId) || null,
    [filteredChatUsers, selectedUserId]
  );
  const selectedLeadStatusMeta = useMemo(
    () => leadStatusMeta(selectedUser?.leadStatus),
    [selectedUser?.leadStatus]
  );

  const canSendOwnerToUser = Boolean(
    selectedUser &&
      (() => {
        const raw = String(selectedUser.userExternalId || '').trim();
        if (!raw) return false;
        if (selectedUser.channel === 'whatsapp_userbot') {
          if (raw.includes('@')) return raw.length <= 128;
          const digits = raw.replace(/\D/g, '');
          return digits.length >= 5 && digits.length <= 20;
        }
        if (selectedUser.channel === 'external_api') {
          return raw.length > 0 && raw.length <= 128;
        }
        if (selectedUser.channel === 'max_userbot') {
          return raw.length > 0 && raw.length <= 128;
        }
        return (
          ['telegram', 'telegram_userbot'].includes(selectedUser.channel) && /^\d+$/.test(raw)
        );
      })()
  );

  useEffect(() => {
    setOwnerReplyText('');
  }, [selectedUserId]);

  useEffect(() => {
    setChatViewMode('chat');
  }, [selectedUserId]);

  const refreshChats = async () => {
    const chats = await agentService.getAnalyticsChats(botId, {
      limit_users: 100,
      messages_per_user: 100,
    });
    const mapped = mapChatsPayload(chats);
    setChatUsers(mapped);
    setSelectedUserId((prev) => {
      const exists = mapped.some((u) => u.id === prev);
      return exists ? prev : mapped[0]?.id || null;
    });
  };

  const handleToggleFreeze = async () => {
    if (!selectedUser) return;
    setIsTogglingFreeze(true);
    try {
      const nextFrozen = !selectedUser.isFrozen;
      await agentService.setUserFrozen(botId, selectedUser.userExternalId, nextFrozen);
      showSuccess(nextFrozen ? 'Пользователь заморожен' : 'Заморозка снята');
      setChatUsers((prev) =>
        prev.map((u) => (u.id === selectedUser.id ? { ...u, isFrozen: nextFrozen } : u))
      );
    } catch (error) {
      showError(error?.message || 'Не удалось изменить статус пользователя');
    } finally {
      setIsTogglingFreeze(false);
    }
  };

  const portraitFeatureEnabled = isPortraitFeatureEnabled(agent);
  const selectedPortrait = String(selectedUser?.chatPortrait || '').trim();
  const canShowPortrait = portraitFeatureEnabled && Boolean(selectedPortrait);

  const handleSendOwnerMessage = async () => {
    if (!selectedUser) return;
    const text = ownerReplyText.trim();
    if (!text) {
      showError('Введите текст сообщения');
      return;
    }
    if (!canSendOwnerToUser) {
      showError('Отправка недоступна для этого диалога (проверьте канал и id получателя)');
      return;
    }
    setIsSendingOwnerReply(true);
    try {
      if (selectedUser.channel === 'whatsapp_userbot') {
        await agentService.sendWhatsappUserbotMessageAsOwner(botId, selectedUser.userExternalId, text);
      } else if (selectedUser.channel === 'max_userbot') {
        await agentService.sendMaxUserbotMessageAsOwner(botId, selectedUser.userExternalId, text);
      } else if (selectedUser.channel === 'external_api') {
        await agentService.sendExternalMessageAsOwner(botId, selectedUser.userExternalId, text);
      } else {
        await agentService.sendTelegramMessageAsOwner(
          botId,
          selectedUser.userExternalId,
          text,
          selectedUser.channel
        );
      }
      showSuccess('Сообщение отправлено');
      setOwnerReplyText('');
      await refreshChats();
    } catch (error) {
      showError(error?.message || 'Не удалось отправить сообщение');
    } finally {
      setIsSendingOwnerReply(false);
    }
  };

  const handleBroadcastSend = async () => {
    const text = broadcastBody.trim();
    if (!text) {
      showError('Введите текст сообщения');
      return;
    }
    if (plannedBroadcastRecipients <= 0) {
      showError('Нет получателей для рассылки');
      return;
    }
    const n = plannedBroadcastRecipients;
    const noun = n === 1 ? 'получателю' : 'получателям';
    if (
      !window.confirm(
        `Отправить сообщение ${n} ${noun}? Сообщения уйдут в Telegram по каналам чатов (bot/userbot). Отменить рассылку будет нельзя.`
      )
    ) {
      return;
    }
    setIsBroadcasting(true);
    setBroadcastResult(null);
    try {
      const result = await agentService.sendTelegramBroadcast(botId, text, {
        skipFrozen: broadcastSkipFrozen,
        maxRecipients: broadcastMaxRecipients,
      });
      setBroadcastResult(result);
      setBroadcastBody('');
      const parts = [
        `отправлено ${result.sent}`,
        `ошибок ${result.failed}`,
      ];
      if (result.skipped_frozen) parts.push(`пропущено замороженных: ${result.skipped_frozen}`);
      if (result.truncated_over_limit) parts.push(`не вошли в лимит: ${result.truncated_over_limit}`);
      showSuccess(`Рассылка завершена: ${parts.join(', ')}`);
      const data = await agentService.getTelegramBroadcastRecipients(botId);
      setBroadcastStats(data);
      await refreshChats();
    } catch (error) {
      showError(error?.message || 'Рассылка не удалась');
    } finally {
      setIsBroadcasting(false);
    }
  };

  const handleWaBroadcastSend = async () => {
    const text = waBroadcastBody.trim();
    if (!text) {
      showError('Введите текст сообщения');
      return;
    }
    if (plannedWaBroadcastRecipients <= 0) {
      showError('Нет получателей для рассылки в WhatsApp userbot');
      return;
    }
    const n = plannedWaBroadcastRecipients;
    const noun = n === 1 ? 'получателю' : 'получателям';
    if (
      !window.confirm(
        `Отправить сообщение в WhatsApp ${n} ${noun} с подключённого userbot? Отменить будет нельзя.`
      )
    ) {
      return;
    }
    setIsWaBroadcasting(true);
    setWaBroadcastResult(null);
    try {
      const result = await agentService.sendWhatsappUserbotBroadcast(botId, text, {
        skipFrozen: broadcastSkipFrozen,
        maxRecipients: broadcastMaxRecipients,
      });
      setWaBroadcastResult(result);
      setWaBroadcastBody('');
      const parts = [
        `отправлено ${result.sent}`,
        result.failed ? `ошибок ${result.failed}` : null,
        result.skipped_frozen ? `пропущено замороженных ${result.skipped_frozen}` : null,
      ].filter(Boolean);
      showSuccess(`Рассылка WhatsApp завершена: ${parts.join(', ')}`);
      const data = await agentService.getWhatsappUserbotBroadcastRecipients(botId);
      setWaBroadcastStats(data);
      await refreshChats();
    } catch (error) {
      showError(error?.message || 'Рассылка WhatsApp не удалась');
    } finally {
      setIsWaBroadcasting(false);
    }
  };

  const parseCsv = (raw) =>
    String(raw || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

  const handleCreateStaff = async () => {
    if (!newStaffDraft.full_name.trim()) {
      showError('Укажите имя сотрудника');
      return;
    }
    try {
      await agentService.createAdminTemplateStaff({
        bot_id: botId,
        role: newStaffDraft.role,
        full_name: newStaffDraft.full_name.trim(),
        specializations: parseCsv(newStaffDraft.specializations),
        is_active: true,
      });
      setNewStaffDraft({ full_name: '', role: 'master', specializations: '' });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать сотрудника');
    }
  };

  const handleSaveStaff = async () => {
    if (!editingStaffId) return;
    if (!editingStaffDraft.full_name.trim()) {
      showError('Имя сотрудника не может быть пустым');
      return;
    }
    try {
      await agentService.updateAdminTemplateStaff({
        bot_id: botId,
        staff_id: editingStaffId,
        full_name: editingStaffDraft.full_name.trim(),
        specializations: parseCsv(editingStaffDraft.specializations),
      });
      setEditingStaffId(null);
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить сотрудника');
    }
  };

  const handleDeleteStaff = async (staffId) => {
    if (!window.confirm('Удалить сотрудника?')) return;
    try {
      await agentService.deleteAdminTemplateStaff({ bot_id: botId, staff_id: staffId });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить сотрудника');
    }
  };

  const handleCreateResource = async () => {
    if (!newResourceDraft.title.trim()) {
      showError('Укажите название ресурса');
      return;
    }
    try {
      await agentService.createAdminTemplateResource({
        bot_id: botId,
        resource_type: newResourceDraft.resource_type,
        title: newResourceDraft.title.trim(),
      });
      setNewResourceDraft({ title: '', resource_type: '' });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать ресурс');
    }
  };

  const handleSaveResource = async () => {
    if (!editingResourceId) return;
    if (!editingResourceDraft.title.trim()) {
      showError('Название ресурса не может быть пустым');
      return;
    }
    try {
      await agentService.updateAdminTemplateResource({
        bot_id: botId,
        resource_id: editingResourceId,
        title: editingResourceDraft.title.trim(),
      });
      setEditingResourceId(null);
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить ресурс');
    }
  };

  const handleDeleteResource = async (resourceId) => {
    if (!window.confirm('Удалить ресурс?')) return;
    try {
      await agentService.deleteAdminTemplateResource({ bot_id: botId, resource_id: resourceId });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить ресурс');
    }
  };

  const handleCreateService = async () => {
    if (!newServiceDraft.title.trim()) {
      showError('Укажите название услуги');
      return;
    }
    try {
      await agentService.createAdminTemplateService({
        bot_id: botId,
        target_role: newServiceDraft.target_role,
        title: newServiceDraft.title.trim(),
        duration_minutes: Number(newServiceDraft.duration_minutes || 60),
        price_minor: rubToMinor(newServiceDraft.price_rub),
        resource_type_filters: parseCsv(newServiceDraft.resource_type_filters),
      });
      setNewServiceDraft({
        title: '',
        target_role: 'master',
        duration_minutes: 60,
        price_rub: '',
        resource_type_filters: '',
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать услугу');
    }
  };

  const handleSaveService = async () => {
    if (!editingServiceId) return;
    if (!editingServiceDraft.title.trim()) {
      showError('Название услуги не может быть пустым');
      return;
    }
    try {
      await agentService.updateAdminTemplateService({
        bot_id: botId,
        service_id: editingServiceId,
        title: editingServiceDraft.title.trim(),
        duration_minutes: Number(editingServiceDraft.duration_minutes || 60),
        price_minor: rubToMinor(editingServiceDraft.price_rub),
        resource_type_filters: parseCsv(editingServiceDraft.resource_type_filters),
      });
      setEditingServiceId(null);
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить услугу');
    }
  };

  const handleDeleteService = async (serviceId) => {
    if (!window.confirm('Удалить услугу?')) return;
    try {
      await agentService.deleteAdminTemplateService({ bot_id: botId, service_id: serviceId });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить услугу');
    }
  };

  const handleCreateScheduleSlot = async () => {
    if (!newScheduleDraft.starts_at || !newScheduleDraft.ends_at) {
      showError('Укажите начало и конец слота');
      return;
    }
    if (!newScheduleDraft.staff_id && !newScheduleDraft.resource_id) {
      showError('Выберите сотрудника или ресурс');
      return;
    }
    try {
      await agentService.createAdminTemplateSchedule({
        bot_id: botId,
        starts_at: fromIsoInputValue(newScheduleDraft.starts_at),
        ends_at: fromIsoInputValue(newScheduleDraft.ends_at),
        staff_id: newScheduleDraft.staff_id ? Number(newScheduleDraft.staff_id) : undefined,
        resource_id: newScheduleDraft.resource_id ? Number(newScheduleDraft.resource_id) : undefined,
        slot_kind: newScheduleDraft.slot_kind || 'work',
      });
      setNewScheduleDraft({ starts_at: '', ends_at: '', staff_id: '', resource_id: '', slot_kind: 'work' });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось добавить слот');
    }
  };

  const handleDeleteScheduleSlot = async (slotId) => {
    if (!window.confirm('Удалить слот расписания?')) return;
    try {
      await agentService.deleteAdminTemplateSchedule({ bot_id: botId, schedule_slot_id: slotId });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить слот');
    }
  };

  const handleAddShiftRange = () => {
    setCalendarShiftDraft((prev) => ({
      ...prev,
      ranges: [...prev.ranges, { starts_at: '09:00', ends_at: '18:00' }],
    }));
  };

  const handleUpdateShiftRange = (index, key, value) => {
    setCalendarShiftDraft((prev) => ({
      ...prev,
      ranges: prev.ranges.map((range, idx) => (idx === index ? { ...range, [key]: value } : range)),
    }));
  };

  const handleRemoveShiftRange = (index) => {
    setCalendarShiftDraft((prev) => ({
      ...prev,
      ranges: prev.ranges.filter((_, idx) => idx !== index),
    }));
  };

  const handleCreateCalendarShifts = async () => {
    if (!selectedCalendarDay) {
      showError('Сначала выберите день в календаре');
      return;
    }
    if (!calendarShiftDraft.staff_id) {
      showError('Выберите сотрудника для графика');
      return;
    }

    const payloads = calendarShiftDraft.ranges
      .map((range) => {
        const startsRaw = String(range.starts_at || '').trim();
        const endsRaw = String(range.ends_at || '').trim();
        if (!startsRaw || !endsRaw) return null;
        if (startsRaw >= endsRaw) return null;

        const [startHour, startMinute] = startsRaw.split(':').map((part) => Number(part || 0));
        const [endHour, endMinute] = endsRaw.split(':').map((part) => Number(part || 0));
        const startDate = new Date(selectedCalendarDay);
        const endDate = new Date(selectedCalendarDay);
        startDate.setHours(startHour, startMinute, 0, 0);
        endDate.setHours(endHour, endMinute, 0, 0);

        return {
          bot_id: botId,
          starts_at: _toLocalIso(startDate),
          ends_at: _toLocalIso(endDate),
          staff_id: Number(calendarShiftDraft.staff_id),
          resource_id: calendarShiftDraft.resource_id ? Number(calendarShiftDraft.resource_id) : undefined,
          slot_kind: 'work',
        };
      })
      .filter(Boolean);

    if (!payloads.length) {
      showError('Добавьте хотя бы один корректный интервал (от и до)');
      return;
    }

    try {
      await Promise.all(payloads.map((payload) => agentService.createAdminTemplateSchedule(payload)));
      showSuccess('График на выбранный день сохранен');
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось сохранить график на день');
    }
  };

  const handleCreateAppointment = async () => {
    if (!newAppointmentDraft.client_external_id.trim()) {
      showError('Укажите client_external_id');
      return;
    }
    if (!newAppointmentDraft.starts_at || !newAppointmentDraft.ends_at) {
      showError('Укажите дату и время записи');
      return;
    }
    try {
      await agentService.createAdminTemplateAppointment({
        bot_id: botId,
        client_external_id: newAppointmentDraft.client_external_id.trim(),
        client_name: newAppointmentDraft.client_name.trim() || undefined,
        starts_at: fromIsoInputValue(newAppointmentDraft.starts_at),
        ends_at: fromIsoInputValue(newAppointmentDraft.ends_at),
        staff_id: newAppointmentDraft.staff_id ? Number(newAppointmentDraft.staff_id) : undefined,
        resource_id: newAppointmentDraft.resource_id ? Number(newAppointmentDraft.resource_id) : undefined,
        service_id: newAppointmentDraft.service_id ? Number(newAppointmentDraft.service_id) : undefined,
        notes: newAppointmentDraft.notes.trim() || undefined,
      });
      setNewAppointmentDraft({
        client_external_id: '',
        client_name: '',
        starts_at: '',
        ends_at: '',
        staff_id: '',
        resource_id: '',
        service_id: '',
        notes: '',
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать запись');
    }
  };

  const handleRescheduleAppointmentQuick = async (appointment) => {
    const currentStart = new Date(appointment.starts_at);
    const currentEnd = new Date(appointment.ends_at);
    if (Number.isNaN(currentStart.getTime()) || Number.isNaN(currentEnd.getTime())) {
      showError('Некорректное время записи');
      return;
    }
    const nextStart = new Date(currentStart.getTime() + 60 * 60 * 1000);
    const nextEnd = new Date(currentEnd.getTime() + 60 * 60 * 1000);
    try {
      await agentService.rescheduleAdminTemplateAppointment({
        bot_id: botId,
        appointment_id: appointment.id,
        starts_at: _toLocalIso(nextStart),
        ends_at: _toLocalIso(nextEnd),
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось перенести запись');
    }
  };

  const handleCancelAppointmentQuick = async (appointment) => {
    if (!window.confirm('Отменить запись? Слот освободится сразу.')) return;
    try {
      const result = await agentService.cancelAdminTemplateAppointment({
        bot_id: botId,
        appointment_id: appointment.id,
        reason: 'cancelled_from_dashboard',
      });
      await loadOperationsDashboard();
      if (result?.auto_refunded) {
        showSuccess('Запись удалена. Возврат оформлен автоматически, клиенту отправлено уведомление.');
      } else if (result?.refund_request) {
        showSuccess('Запись удалена. Заявка на возврат создана — решение придёт клиенту после проверки.');
      } else {
        showSuccess('Запись удалена');
      }
    } catch (error) {
      showError(error?.message || 'Не удалось отменить запись');
    }
  };

  const handleApproveRefundRequest = async (item) => {
    if (!window.confirm(`Подтвердить полный возврат ${item.amount_rub} ₽ клиенту ${item.client_external_id}?`)) return;
    try {
      await agentService.approveAdminTemplateRefundRequest({
        bot_id: botId,
        refund_request_id: item.id,
      });
      await loadRefundRequests();
      showSuccess('Возврат одобрен. Клиенту отправлено уведомление.');
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить возврат');
    }
  };

  const handleRejectRefundRequest = async (item) => {
    const reason = window.prompt('Причина отклонения (необязательно):', '');
    if (reason === null) return;
    try {
      await agentService.rejectAdminTemplateRefundRequest({
        bot_id: botId,
        refund_request_id: item.id,
        reason: reason.trim() || undefined,
      });
      await loadRefundRequests();
      showSuccess('Заявка отклонена. Клиенту отправлено уведомление.');
    } catch (error) {
      showError(error?.message || 'Не удалось отклонить возврат');
    }
  };

  const handleConfirmAppointmentQuick = async (appointment) => {
    try {
      await agentService.confirmAdminTemplateAppointment({
        bot_id: botId,
        appointment_id: appointment.id,
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось подтвердить запись');
    }
  };

  const handleCreateWaitlist = async () => {
    if (!newWaitlistDraft.client_external_id.trim()) {
      showError('Укажите client_external_id для waitlist');
      return;
    }
    try {
      await agentService.createAdminTemplateWaitlist({
        bot_id: botId,
        client_external_id: newWaitlistDraft.client_external_id.trim(),
        client_name: newWaitlistDraft.client_name.trim() || undefined,
        service_id: newWaitlistDraft.service_id ? Number(newWaitlistDraft.service_id) : undefined,
        desired_staff_id: newWaitlistDraft.desired_staff_id ? Number(newWaitlistDraft.desired_staff_id) : undefined,
        desired_resource_id: newWaitlistDraft.desired_resource_id ? Number(newWaitlistDraft.desired_resource_id) : undefined,
      });
      setNewWaitlistDraft({
        client_external_id: '',
        client_name: '',
        service_id: '',
        desired_staff_id: '',
        desired_resource_id: '',
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось добавить в waitlist');
    }
  };

  const handleCancelWaitlist = async (item) => {
    try {
      await agentService.updateAdminTemplateWaitlist({
        bot_id: botId,
        waitlist_id: item.id,
        status: 'cancelled',
      });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось обновить waitlist');
    }
  };

  const handleCreateQuickReply = async () => {
    if (!newQuickReplyDraft.title.trim() || !newQuickReplyDraft.body.trim()) {
      showError('Укажите title и body для quick reply');
      return;
    }
    try {
      await agentService.createAdminTemplateQuickReply({
        bot_id: botId,
        title: newQuickReplyDraft.title.trim(),
        body: newQuickReplyDraft.body.trim(),
        category: newQuickReplyDraft.category.trim() || undefined,
      });
      setNewQuickReplyDraft({ title: '', body: '', category: '' });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось создать шаблон ответа');
    }
  };

  const handleDeleteQuickReply = async (item) => {
    try {
      await agentService.deleteAdminTemplateQuickReply({ bot_id: botId, quick_reply_id: item.id });
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось удалить шаблон ответа');
    }
  };

  const handleRunReminders = async () => {
    try {
      const result = await agentService.runAdminTemplateReminders({ bot_id: botId });
      setReminderRunResult(result);
      showSuccess(`Напоминаний отправлено: ${result?.sent || 0}`);
      await loadOperationsDashboard();
    } catch (error) {
      showError(error?.message || 'Не удалось выполнить run напоминаний');
    }
  };

  if (isLoading) {
    return <Loading message="Загрузка аналитики..." />;
  }

  const drilldownAppointments = Array.isArray(occupancyData?.drilldown?.appointments)
    ? occupancyData.drilldown.appointments
    : [];
  const selectedDrilldownAppointmentIds = new Set(
    Array.isArray(selectedDrilldown?.appointment_ids) ? selectedDrilldown.appointment_ids : []
  );
  const selectedDrilldownItems = selectedDrilldown
    ? drilldownAppointments.filter((item) => selectedDrilldownAppointmentIds.has(item.id))
    : [];

  const selectedCalendarDayKey = selectedCalendarDay ? toDayKey(selectedCalendarDay) : '';
  const monthAnchor = startOfDay(calendarAnchor);
  const monthTitle = monthAnchor.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  const monthFirstDay = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1);
  const monthLastDay = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth() + 1, 0);
  const monthGridStart = startOfWeek(monthFirstDay);
  const monthGridEnd = endOfWeek(monthLastDay);
  const monthDays = [];
  for (let cursor = new Date(monthGridStart); cursor <= monthGridEnd; cursor.setDate(cursor.getDate() + 1)) {
    monthDays.push(new Date(cursor));
  }

  const staffNameById = new Map(staffItems.map((item) => [item.id, item.full_name || `Сотрудник #${item.id}`]));
  const serviceTitleById = new Map(serviceItems.map((item) => [item.id, item.title || `Услуга #${item.id}`]));

  const dayStats = monthDays.reduce((acc, day) => {
    const dayKey = toDayKey(day);
    const appointmentForDay = calendarAppointmentItems.filter((item) => toDayKey(item.starts_at) === dayKey);
    const scheduleForDay = calendarScheduleItems.filter((item) => toDayKey(item.starts_at) === dayKey);
    acc.set(dayKey, {
      appointments: appointmentForDay,
      schedules: scheduleForDay,
      appointmentsCount: appointmentForDay.length,
    });
    return acc;
  }, new Map());

  const selectedDayAppointments = selectedCalendarDayKey
    ? dayStats.get(selectedCalendarDayKey)?.appointments || []
    : [];
  const selectedDaySchedules = selectedCalendarDayKey
    ? dayStats.get(selectedCalendarDayKey)?.schedules || []
    : [];

  return (
    <div className="agent-analytics-page">
      <div className="agent-analytics-header">
        <div className="agent-analytics-header-main">
          <h2>Дашборд агента</h2>
          <p className="agent-analytics-header-subtitle">
            {agent?.bot_username ? `@${agent.bot_username}` : `Агент #${botId}`}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline agent-analytics-back-btn"
          onClick={() => navigate(NAVIGATION_ROUTES.AGENTS)}
        >
          ← Назад к управлению агентами
        </button>
      </div>

      <div className="agent-analytics-layout">
        <aside className="agent-analytics-sidebar">
          <h4>Разделы</h4>
          <button
            type="button"
            className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.OVERVIEW ? 'analytics-section-btn--active' : ''}`}
            onClick={() => setSelectedSection(ANALYTICS_SECTIONS.OVERVIEW)}
          >
            Общая аналитика
          </button>
          <button
            type="button"
            className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.CHATS ? 'analytics-section-btn--active' : ''}`}
            onClick={() => setSelectedSection(ANALYTICS_SECTIONS.CHATS)}
          >
            Чаты
          </button>
          <button
            type="button"
            className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.TELEPHONY ? 'analytics-section-btn--active' : ''}`}
            onClick={() => setSelectedSection(ANALYTICS_SECTIONS.TELEPHONY)}
          >
            Звонки <DemoBadge />
          </button>
          <button
            type="button"
            className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.BROADCAST ? 'analytics-section-btn--active' : ''}`}
            onClick={() => setSelectedSection(ANALYTICS_SECTIONS.BROADCAST)}
          >
            Рассылка
          </button>
          {isCrmAdminTemplate ? (
            <>
              <button
                type="button"
                className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.OPERATIONS ? 'analytics-section-btn--active' : ''}`}
                onClick={() => setSelectedSection(ANALYTICS_SECTIONS.OPERATIONS)}
              >
                Операционный дашборд
              </button>
              <button
                type="button"
                className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.REFUNDS ? 'analytics-section-btn--active' : ''}`}
                onClick={() => setSelectedSection(ANALYTICS_SECTIONS.REFUNDS)}
              >
                Заявки на возврат
                {refundRequestItems.some((item) => item.status === 'pending') ? (
                  <span className="analytics-section-badge">
                    {refundRequestItems.filter((item) => item.status === 'pending').length}
                  </span>
                ) : null}
              </button>
            </>
          ) : null}
        </aside>

        <div className="agent-analytics-content">
          {selectedSection === ANALYTICS_SECTIONS.OVERVIEW ? (
            <section className="analytics-overview">
              <h3>Общая аналитика</h3>
              <p className="analytics-note">
                Метрики показывают динамику по взаимодействиям с агентом и помогают оценить качество лидов.
              </p>
              <div className="analytics-metrics-grid">
                {metrics.map((metric) => (
                  <article key={metric.id} className="analytics-metric-card">
                    <p className="analytics-metric-value">{metric.value}</p>
                    <p className="analytics-metric-label">{metric.label}</p>
                  </article>
                ))}
              </div>
              <section className="analytics-crm-actions">
                <h4>CRM действия агента</h4>
                <div className="analytics-metrics-grid">
                  {crmActionMetrics.map((metric) => (
                    <article key={metric.id} className="analytics-metric-card analytics-metric-card--crm">
                      <p className="analytics-metric-value">{metric.value}</p>
                      <p className="analytics-metric-label">{metric.label}</p>
                    </article>
                  ))}
                </div>
                <div className="analytics-crm-breakdown">
                  <article className="analytics-crm-breakdown-card">
                    <h5>Топ CRM tools</h5>
                    <ul>
                      {(Array.isArray(crmActions?.by_tool) ? crmActions.by_tool : []).slice(0, 6).map((item) => (
                        <li key={item.tool_name}>
                          <span>{item.tool_name}</span>
                          <strong>{formatNumber(Number(item.count || 0))}</strong>
                        </li>
                      ))}
                    </ul>
                  </article>
                  <article className="analytics-crm-breakdown-card">
                    <h5>Статусы вызовов</h5>
                    <ul>
                      {(Array.isArray(crmActions?.by_status) ? crmActions.by_status : []).slice(0, 6).map((item) => (
                        <li key={item.tool_status}>
                          <span>{item.tool_status}</span>
                          <strong>{formatNumber(Number(item.count || 0))}</strong>
                        </li>
                      ))}
                    </ul>
                  </article>
                </div>
              </section>
              <AnalyticsChart
                timeline={timeline}
                selectedDays={selectedDays}
                onChangeDays={setSelectedDays}
                isLoading={isChartLoading}
              />
            </section>
          ) : selectedSection === ANALYTICS_SECTIONS.TELEPHONY ? (
            <section className="analytics-telephony">
              <TitleWithDemoBadge as="h3">Телефония</TitleWithDemoBadge>
              {telephonyChannel ? (
                <p className="analytics-note">Номер канала: {telephonyChannel.external_id}</p>
              ) : (
                <p className="analytics-note">Телефонный канал не подключён.</p>
              )}
              {telephonyCallsLoading ? (
                <p className="analytics-chat-empty">Загрузка звонков...</p>
              ) : telephonyCalls.length === 0 ? (
                <p className="analytics-chat-empty">Звонков пока нет</p>
              ) : (
                <div className="analytics-telephony-layout">
                  <aside className="analytics-telephony-calls-list">
                    {telephonyCalls.map((call) => (
                      <button
                        key={call.id}
                        type="button"
                        className={`analytics-telephony-call-item ${selectedCallId === call.id ? 'analytics-telephony-call-item--active' : ''}`}
                        onClick={() => setSelectedCallId(call.id)}
                      >
                        <strong>{telephonyCallTitle(call)}</strong>
                        <span>{formatDateTime(call.started_at, '—')}</span>
                        <span>
                          {telephonyStatusLabel(call.status)} · {formatCallDuration(call.duration_sec)}
                        </span>
                      </button>
                    ))}
                  </aside>
                  <div className="analytics-telephony-call-detail">
                    {selectedCall ? (
                      <>
                        <h4>Детали звонка</h4>
                        <ul className="analytics-telephony-meta">
                          <li>
                            <span>Абонент</span>
                            <strong>{telephonyCallTitle(selectedCall)}</strong>
                          </li>
                          <li>
                            <span>Статус</span>
                            <strong>{telephonyStatusLabel(selectedCall.status)}</strong>
                          </li>
                          <li>
                            <span>Начало</span>
                            <strong>{formatDateTime(selectedCall.started_at, '—')}</strong>
                          </li>
                          <li>
                            <span>Длительность</span>
                            <strong>{formatCallDuration(selectedCall.duration_sec)}</strong>
                          </li>
                        </ul>
                        {selectedCall.recording_url ? (
                          <p className="analytics-telephony-recording">
                            <a href={selectedCall.recording_url} target="_blank" rel="noreferrer">
                              Прослушать запись (CPaaS)
                            </a>
                          </p>
                        ) : null}
                        <h5>Реплики</h5>
                        <div className="analytics-telephony-turns">
                          {(selectedCall.turns || []).length === 0 ? (
                            <p className="analytics-chat-empty">Транскриптов пока нет</p>
                          ) : (
                            (selectedCall.turns || []).map((turn) => (
                              <article
                                key={turn.id}
                                className={`analytics-telephony-turn analytics-telephony-turn--${turn.role}`}
                              >
                                <header>
                                  <strong>{turn.role}</strong>
                                  <span>{formatDateTime(turn.created_at, '—')}</span>
                                </header>
                                <p>{turn.transcript}</p>
                              </article>
                            ))
                          )}
                        </div>
                      </>
                    ) : (
                      <p className="analytics-chat-empty">Выберите звонок</p>
                    )}
                  </div>
                </div>
              )}
            </section>
          ) : selectedSection === ANALYTICS_SECTIONS.CHATS ? (
            <section className="analytics-chats">
              <h3>Чаты</h3>
              <div className="analytics-chats-toolbar">
                <label htmlFor="chat-channel-filter">Канал</label>
                <select
                  id="chat-channel-filter"
                  className="input-main"
                  value={chatChannelFilter}
                  onChange={(e) => {
                    setChatChannelFilter(e.target.value);
                    setSelectedUserId(null);
                  }}
                >
                  <option value="all">Все</option>
                  <option value="phone">Телефония</option>
                  <option value="telegram">Telegram bot</option>
                  <option value="telegram_userbot">Telegram userbot</option>
                  <option value="whatsapp_userbot">WhatsApp userbot</option>
                  <option value="max_bot">MAX bot</option>
                  <option value="max_userbot">MAX userbot</option>
                </select>
              </div>
              <div className="analytics-chat-window">
                <aside className="analytics-users-list">
                  {filteredChatUsers.length === 0 ? (
                    <p className="analytics-chat-empty">Пока нет сообщений от пользователей</p>
                  ) : (
                    filteredChatUsers.map((user) => {
                      const statusMeta = leadStatusMeta(user.leadStatus);
                      return (
                      <button
                        key={user.id}
                        type="button"
                        className={`analytics-user-item ${selectedUserId === user.id ? 'analytics-user-item--active' : ''} ${user.isFrozen ? 'analytics-user-item--frozen' : ''}`}
                        onClick={() => setSelectedUserId(user.id)}
                      >
                        <span
                          className={`analytics-user-item-status-dot analytics-user-item-status-dot--${statusMeta.warmth}`}
                          aria-label={`Статус лида: ${statusMeta.label}`}
                          title={`Статус лида: ${statusMeta.label}`}
                        />
                        <strong>{user.name}</strong>
                        <span>{channelLabel(user.channel)}</span>
                        <span>{user.questions} вопросов</span>
                        <span>{user.lastMessageAt}</span>
                        {user.isFrozen ? <span className="analytics-user-frozen-badge">Заморожен</span> : null}
                      </button>
                      );
                    })
                  )}
                </aside>

                <div className="analytics-chat-thread">
                  {!selectedUser ? (
                    <p className="analytics-chat-empty">Выберите пользователя слева для просмотра переписки</p>
                  ) : (
                    <>
                      <header className="analytics-chat-thread-header">
                        <div className="analytics-chat-thread-header-text">
                          <h4>{selectedUser.name}</h4>
                          <p>
                            Вопросов: {selectedUser.questions} · {channelLabel(selectedUser.channel)}
                          </p>
                          <span className={`analytics-lead-status-badge analytics-lead-status-badge--${selectedLeadStatusMeta.warmth}`}>
                            {selectedLeadStatusMeta.label}
                          </span>
                        </div>
                        <div className="analytics-chat-thread-header-actions">
                          {portraitFeatureEnabled ? (
                            <button
                              type="button"
                              className="btn btn-outline analytics-portrait-btn"
                              onClick={() => setChatViewMode((prev) => (prev === 'chat' ? 'portrait' : 'chat'))}
                            >
                              {chatViewMode === 'chat' ? 'Портрет' : 'Чат'}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className={`btn btn-outline analytics-freeze-btn ${selectedUser.isFrozen ? 'analytics-freeze-btn--active' : ''}`}
                            onClick={handleToggleFreeze}
                            disabled={isTogglingFreeze}
                          >
                            {isTogglingFreeze
                              ? '...'
                              : selectedUser.isFrozen
                                ? 'Разморозить'
                                : 'Заморозить'}
                          </button>
                        </div>
                      </header>
                      {chatViewMode === 'portrait' && portraitFeatureEnabled ? (
                        <div className="analytics-portrait-panel">
                          {canShowPortrait ? (
                            <>
                              <h5>Портрет клиента/чата</h5>
                              <p>{selectedPortrait}</p>
                            </>
                          ) : (
                            <p className="analytics-chat-empty">
                              Портрет для этого чата пока не сформирован
                            </p>
                          )}
                        </div>
                      ) : (
                        <div className="analytics-messages-list">
                          {selectedUser.messages.map((message) => {
                            const bubbleRole = message.role === 'operator' ? 'operator' : message.role;
                            const roleLabel =
                              message.role === 'user'
                                ? selectedUser.name
                                : message.role === 'operator'
                                  ? 'Вы (владелец)'
                                  : 'Агент';
                            return (
                              <div
                                key={message.id}
                                className={`analytics-message-bubble analytics-message-bubble--${bubbleRole}`}
                              >
                                <span className="analytics-message-role">{roleLabel}</span>
                                <p>{message.text}</p>
                                <time>{message.timestamp}</time>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <div className="analytics-chat-composer">
                        <p className="analytics-chat-composer-hint">
                          {canSendOwnerToUser
                            ? `Сообщение будет доставлено в выбранный чат (${channelLabel(selectedUser.channel)}).`
                            : 'Отправка: Telegram — числовой id; WhatsApp userbot — номер (или полный JID).'}
                        </p>
                        <div className="analytics-chat-composer-row">
                          <textarea
                            className="input-main analytics-chat-composer-input"
                            rows={2}
                            placeholder="Текст от вашего лица..."
                            value={ownerReplyText}
                            onChange={(e) => setOwnerReplyText(e.target.value)}
                            disabled={!canSendOwnerToUser || isSendingOwnerReply}
                          />
                          <button
                            type="button"
                            className="btn btn-black analytics-chat-composer-send"
                            onClick={handleSendOwnerMessage}
                            disabled={!canSendOwnerToUser || isSendingOwnerReply}
                          >
                            {isSendingOwnerReply ? 'Отправка...' : 'Отправить'}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </section>
          ) : selectedSection === ANALYTICS_SECTIONS.OPERATIONS ? (
            <section className="analytics-operations">
              <div className="analytics-operations-header">
                <h3>Операционный дашборд</h3>
                <div className="analytics-operations-toolbar">
                  <div className="analytics-calendar-switch">
                    <button
                      type="button"
                      className={`btn btn-outline ${calendarView === 'day' ? 'analytics-calendar-switch--active' : ''}`}
                      onClick={() => setCalendarView('day')}
                    >
                      Day
                    </button>
                    <button
                      type="button"
                      className={`btn btn-outline ${calendarView === 'week' ? 'analytics-calendar-switch--active' : ''}`}
                      onClick={() => setCalendarView('week')}
                    >
                      Week
                    </button>
                  </div>
                  <CalendarAnchorPicker value={calendarAnchor} onChange={setCalendarAnchor} />
                  <button type="button" className="btn btn-outline" onClick={loadOperationsDashboard} disabled={opsLoading}>
                    {opsLoading ? 'Обновление...' : 'Обновить'}
                  </button>
                </div>
              </div>

              <article className="analytics-ops-card analytics-ops-card--wide">
                <div className="analytics-admin-calendar-head">
                  <div>
                    <h4>Календарь записи</h4>
                    <p className="analytics-note">
                      Нажмите на день, чтобы посмотреть записи и назначить график сотрудника.
                    </p>
                  </div>
                  <div className="analytics-admin-calendar-nav">
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() =>
                        setCalendarAnchor(
                          new Date(calendarAnchor.getFullYear(), calendarAnchor.getMonth() - 1, 1)
                        )
                      }
                    >
                      ←
                    </button>
                    <strong className="analytics-admin-calendar-title">{monthTitle}</strong>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() =>
                        setCalendarAnchor(
                          new Date(calendarAnchor.getFullYear(), calendarAnchor.getMonth() + 1, 1)
                        )
                      }
                    >
                      →
                    </button>
                  </div>
                </div>
                <div className="analytics-admin-calendar-grid analytics-admin-calendar-grid--weekday">
                  {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((weekday) => (
                    <span key={weekday}>{weekday}</span>
                  ))}
                </div>
                <div className="analytics-admin-calendar-grid">
                  {monthDays.map((day) => {
                    const dayKey = toDayKey(day);
                    const stats = dayStats.get(dayKey) || { appointmentsCount: 0 };
                    const isCurrentMonth = day.getMonth() === monthAnchor.getMonth();
                    const isSelected = selectedCalendarDayKey === dayKey;
                    const dayLoadClass = stats.appointmentsCount === 0
                      ? 'analytics-admin-calendar-day--free'
                      : stats.appointmentsCount >= 4
                        ? 'analytics-admin-calendar-day--busy'
                        : 'analytics-admin-calendar-day--light';

                    return (
                      <button
                        key={dayKey}
                        type="button"
                        className={`analytics-admin-calendar-day ${dayLoadClass} ${!isCurrentMonth ? 'analytics-admin-calendar-day--muted' : ''} ${isSelected ? 'analytics-admin-calendar-day--selected' : ''}`}
                        onClick={() => {
                          setSelectedCalendarDay(day);
                          if (!calendarShiftDraft.staff_id && staffItems[0]?.id) {
                            setCalendarShiftDraft((prev) => ({ ...prev, staff_id: String(staffItems[0].id) }));
                          }
                        }}
                      >
                        <span>{day.getDate()}</span>
                        <small>{stats.appointmentsCount} записей</small>
                      </button>
                    );
                  })}
                </div>
                <div className="analytics-admin-calendar-legend">
                  <span><i className="analytics-admin-calendar-dot analytics-admin-calendar-dot--free" /> Нет записей</span>
                  <span><i className="analytics-admin-calendar-dot analytics-admin-calendar-dot--light" /> Немного записей</span>
                  <span><i className="analytics-admin-calendar-dot analytics-admin-calendar-dot--busy" /> День заполнен</span>
                </div>
              </article>

              <div className="analytics-ops-kpis">
                <article className="analytics-ops-kpi">
                  <span className="analytics-ops-kpi-label">Utilization</span>
                  <strong>{formatPercent(occupancyData?.kpis?.utilization_percent)}</strong>
                  <small>
                    {formatMinutes(occupancyData?.totals?.occupied_minutes)} / {formatMinutes(occupancyData?.totals?.schedulable_minutes)}
                  </small>
                </article>
                <article className="analytics-ops-kpi">
                  <span className="analytics-ops-kpi-label">Peak hours</span>
                  <strong>{occupancyData?.kpis?.peak_hours?.[0]?.label || '-'}</strong>
                  <small>
                    {formatMinutes(occupancyData?.kpis?.peak_hours?.[0]?.occupied_minutes)}
                  </small>
                </article>
                <article className="analytics-ops-kpi">
                  <span className="analytics-ops-kpi-label">No-show rate</span>
                  <strong>
                    {occupancyData?.kpis?.no_show?.enabled
                      ? formatPercent(occupancyData?.kpis?.no_show?.rate_percent)
                      : 'off'}
                  </strong>
                  <small>
                    {occupancyData?.kpis?.no_show?.enabled
                      ? `${occupancyData?.kpis?.no_show?.no_show_count || 0}/${occupancyData?.kpis?.no_show?.basis_appointments || 0}`
                      : 'Подтверждение визитов выключено'}
                  </small>
                </article>
              </div>

              <div className="analytics-ops-aggregates-grid">
                <article className="analytics-ops-card">
                  <h4>Загрузка по сотруднику</h4>
                  <div className="analytics-ops-list">
                    {(occupancyData?.aggregates?.by_staff || []).map((item) => (
                      <button
                        key={`staff-agg-${item.staff_id}`}
                        type="button"
                        className={`analytics-ops-aggregate-row ${selectedDrilldown?.key === `staff-${item.staff_id}` ? 'analytics-ops-aggregate-row--active' : ''}`}
                        onClick={() =>
                          setSelectedDrilldown({
                            key: `staff-${item.staff_id}`,
                            title: `Сотрудник: ${item.staff_name}`,
                            appointment_ids: item.appointment_ids || [],
                          })
                        }
                      >
                        <span>{item.staff_name}</span>
                        <span>{formatMinutes(item.occupied_minutes)} · {formatPercent(item.utilization_percent)}</span>
                      </button>
                    ))}
                  </div>
                </article>
                <article className="analytics-ops-card">
                  <h4>Загрузка по кабинету/креслу</h4>
                  <div className="analytics-ops-list">
                    {(occupancyData?.aggregates?.by_resource || []).map((item) => (
                      <button
                        key={`resource-agg-${item.resource_id}`}
                        type="button"
                        className={`analytics-ops-aggregate-row ${selectedDrilldown?.key === `resource-${item.resource_id}` ? 'analytics-ops-aggregate-row--active' : ''}`}
                        onClick={() =>
                          setSelectedDrilldown({
                            key: `resource-${item.resource_id}`,
                            title: `Ресурс: ${item.resource_title}`,
                            appointment_ids: item.appointment_ids || [],
                          })
                        }
                      >
                        <span>{item.resource_title}</span>
                        <span>{formatMinutes(item.occupied_minutes)} · {formatPercent(item.utilization_percent)}</span>
                      </button>
                    ))}
                  </div>
                </article>
                <article className="analytics-ops-card">
                  <h4>Загрузка по услуге</h4>
                  <div className="analytics-ops-list">
                    {(occupancyData?.aggregates?.by_service || []).map((item) => (
                      <button
                        key={`service-agg-${item.service_id}`}
                        type="button"
                        className={`analytics-ops-aggregate-row ${selectedDrilldown?.key === `service-${item.service_id}` ? 'analytics-ops-aggregate-row--active' : ''}`}
                        onClick={() =>
                          setSelectedDrilldown({
                            key: `service-${item.service_id}`,
                            title: `Услуга: ${item.service_title}`,
                            appointment_ids: item.appointment_ids || [],
                          })
                        }
                      >
                        <span>{item.service_title}</span>
                        <span>{formatMinutes(item.occupied_minutes)} · {item.appointments} записей</span>
                      </button>
                    ))}
                  </div>
                </article>
                <article className="analytics-ops-card">
                  <h4>Пиковые часы</h4>
                  <div className="analytics-ops-list">
                    {(occupancyData?.kpis?.peak_hours || []).map((item) => (
                      <button
                        key={`peak-${item.hour}`}
                        type="button"
                        className={`analytics-ops-aggregate-row ${selectedDrilldown?.key === `peak-${item.hour}` ? 'analytics-ops-aggregate-row--active' : ''}`}
                        onClick={() =>
                          setSelectedDrilldown({
                            key: `peak-${item.hour}`,
                            title: `Пиковый час: ${item.label}`,
                            appointment_ids: item.appointment_ids || [],
                          })
                        }
                      >
                        <span>{item.label}</span>
                        <span>{formatMinutes(item.occupied_minutes)} · {item.appointments} записей</span>
                      </button>
                    ))}
                  </div>
                </article>
                <article className="analytics-ops-card analytics-ops-card--wide">
                  <h4>Провалы расписания (пустые окна)</h4>
                  <div className="analytics-ops-list">
                    {(occupancyData?.aggregates?.schedule_gaps || []).slice(0, 15).map((item, idx) => (
                      <div key={`gap-${idx}`} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)}</strong>
                          <span>
                            {formatMinutes(item.duration_minutes)} · {item.staff_name || 'Без сотрудника'} · {item.resource_title || 'Без ресурса'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              </div>

              {selectedDrilldown ? (
                <article className="analytics-ops-card analytics-ops-card--wide">
                  <div className="analytics-ops-drilldown-header">
                    <h4>{selectedDrilldown.title}</h4>
                    <button type="button" className="btn btn-outline" onClick={() => setSelectedDrilldown(null)}>
                      Сбросить
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {selectedDrilldownItems.length ? (
                      selectedDrilldownItems.map((item) => (
                        <div key={`drill-${item.id}`} className="analytics-ops-row">
                          <div className="analytics-ops-row-main">
                            <strong>{item.client_name || item.client_external_id}</strong>
                            <span>
                              {formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)} · status: {item.status}
                            </span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="analytics-note">Нет записей для выбранного агрегата.</p>
                    )}
                  </div>
                </article>
              ) : null}

              <div className="analytics-ops-aggregates-grid">
                <article className="analytics-ops-card">
                  <div className="analytics-ops-drilldown-header">
                    <h4>Waitlist</h4>
                    <button type="button" className="btn btn-outline" onClick={handleRunReminders}>
                      Run reminders
                    </button>
                  </div>
                  <div className="analytics-ops-inline-form">
                    <input
                      className="input-main"
                      placeholder="client_external_id"
                      value={newWaitlistDraft.client_external_id}
                      onChange={(e) => setNewWaitlistDraft((prev) => ({ ...prev, client_external_id: e.target.value }))}
                    />
                    <input
                      className="input-main"
                      placeholder="Имя клиента"
                      value={newWaitlistDraft.client_name}
                      onChange={(e) => setNewWaitlistDraft((prev) => ({ ...prev, client_name: e.target.value }))}
                    />
                    <AnalyticsCustomSelect
                      value={newWaitlistDraft.service_id}
                      onChange={(selectedValue) => setNewWaitlistDraft((prev) => ({ ...prev, service_id: selectedValue }))}
                      placeholder="Услуга"
                      ariaLabel="Выбор услуги для листа ожидания"
                      options={[
                        { value: '', label: 'Услуга' },
                        ...serviceItems.map((service) => ({ value: service.id, label: service.title })),
                      ]}
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateWaitlist}>
                      Добавить
                    </button>
                  </div>
                  {reminderRunResult ? (
                    <p className="analytics-note">Последний запуск напоминаний: {reminderRunResult.sent || 0}</p>
                  ) : null}
                  <div className="analytics-ops-list">
                    {waitlistItems.map((item) => (
                      <div key={`waitlist-${item.id}`} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{item.client_name || item.client_external_id}</strong>
                          <span>status: {item.status} · service: {item.service_id || '-'}</span>
                        </div>
                        <div className="analytics-ops-row-actions">
                          {item.status === 'waiting' ? (
                            <button type="button" className="btn btn-outline" onClick={() => handleCancelWaitlist(item)}>
                              Отменить
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="analytics-ops-card">
                  <h4>Клиенты: теги и предпочтения</h4>
                  <div className="analytics-ops-list">
                    {clientProfileItems.map((item) => (
                      <div key={`profile-${item.id}`} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{item.client_name || item.client_external_id}</strong>
                          <span>
                            tags: {Array.isArray(item.tags) && item.tags.length ? item.tags.join(', ') : '-'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="analytics-ops-card analytics-ops-card--wide">
                  <h4>Шаблоны быстрых ответов</h4>
                  <div className="analytics-ops-inline-form analytics-ops-inline-form--service">
                    <input
                      className="input-main"
                      placeholder="Название шаблона"
                      value={newQuickReplyDraft.title}
                      onChange={(e) => setNewQuickReplyDraft((prev) => ({ ...prev, title: e.target.value }))}
                    />
                    <input
                      className="input-main"
                      placeholder="Категория"
                      value={newQuickReplyDraft.category}
                      onChange={(e) => setNewQuickReplyDraft((prev) => ({ ...prev, category: e.target.value }))}
                    />
                    <input
                      className="input-main"
                      placeholder="Текст ответа"
                      value={newQuickReplyDraft.body}
                      onChange={(e) => setNewQuickReplyDraft((prev) => ({ ...prev, body: e.target.value }))}
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateQuickReply}>
                      Добавить
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {quickReplyItems.map((item) => (
                      <div key={`quick-reply-${item.id}`} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{item.title}</strong>
                          <span>{item.body}</span>
                        </div>
                        <div className="analytics-ops-row-actions">
                          <button type="button" className="btn btn-outline" onClick={() => handleDeleteQuickReply(item)}>
                            Удалить
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              </div>

              <div className="analytics-operations-grid">
                <article className="analytics-ops-card">
                  <h4>Сотрудники</h4>
                  <div className="analytics-ops-inline-form">
                    <input
                      className="input-main"
                      placeholder="Имя"
                      value={newStaffDraft.full_name}
                      onChange={(e) => setNewStaffDraft((prev) => ({ ...prev, full_name: e.target.value }))}
                    />
                    <AnalyticsCustomSelect
                      value={newStaffDraft.role}
                      onChange={(selectedValue) => setNewStaffDraft((prev) => ({ ...prev, role: selectedValue }))}
                      ariaLabel="Выбор роли сотрудника"
                      options={[
                        { value: 'master', label: 'master' },
                        { value: 'doctor', label: 'doctor' },
                      ]}
                    />
                    <input
                      className="input-main"
                      placeholder="Специализации через запятую"
                      value={newStaffDraft.specializations}
                      onChange={(e) => setNewStaffDraft((prev) => ({ ...prev, specializations: e.target.value }))}
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateStaff}>
                      Добавить
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {staffItems.map((item) => {
                      const isEditing = editingStaffId === item.id;
                      return (
                        <div key={item.id} className="analytics-ops-row">
                          {isEditing ? (
                            <>
                              <input
                                className="input-main"
                                value={editingStaffDraft.full_name}
                                onChange={(e) => setEditingStaffDraft((prev) => ({ ...prev, full_name: e.target.value }))}
                              />
                              <input
                                className="input-main"
                                value={editingStaffDraft.specializations}
                                onChange={(e) =>
                                  setEditingStaffDraft((prev) => ({ ...prev, specializations: e.target.value }))
                                }
                              />
                              <button type="button" className="btn btn-black" onClick={handleSaveStaff}>Сохранить</button>
                              <button type="button" className="btn btn-outline" onClick={() => setEditingStaffId(null)}>Отмена</button>
                            </>
                          ) : (
                            <>
                              <div className="analytics-ops-row-main">
                                <strong>{item.full_name}</strong>
                                <span>{item.role}</span>
                              </div>
                              <div className="analytics-ops-row-actions">
                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  onClick={() => {
                                    setEditingStaffId(item.id);
                                    setEditingStaffDraft({
                                      full_name: item.full_name || '',
                                      role: item.role || 'master',
                                      specializations: Array.isArray(item.specializations) ? item.specializations.join(', ') : '',
                                    });
                                  }}
                                >
                                  Изменить
                                </button>
                                <button type="button" className="btn btn-outline" onClick={() => handleDeleteStaff(item.id)}>
                                  Удалить
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </article>

                <article className="analytics-ops-card">
                  <h4>Ресурсы</h4>
                  <div className="analytics-ops-inline-form">
                    <input
                      className="input-main"
                      placeholder="Название ресурса"
                      value={newResourceDraft.title}
                      onChange={(e) => setNewResourceDraft((prev) => ({ ...prev, title: e.target.value }))}
                    />
                    <AnalyticsCustomSelect
                      value={newResourceDraft.resource_type}
                      onChange={(selectedValue) => setNewResourceDraft((prev) => ({ ...prev, resource_type: selectedValue }))}
                      ariaLabel="Выбор типа ресурса"
                      options={(() => {
                        const examples = agent?.template_config?.custom_resource_types
                          || (agent?.template_config?.domain_type
                            ? undefined
                            : null);
                        if (Array.isArray(examples) && examples.length > 0) {
                          return examples.map((t) => ({ value: t, label: t }));
                        }
                        return _DEFAULT_RESOURCE_TYPE_OPTIONS;
                      })()}
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateResource}>
                      Добавить
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {resourceItems.map((item) => {
                      const isEditing = editingResourceId === item.id;
                      return (
                        <div key={item.id} className="analytics-ops-row">
                          {isEditing ? (
                            <>
                              <input
                                className="input-main"
                                value={editingResourceDraft.title}
                                onChange={(e) => setEditingResourceDraft((prev) => ({ ...prev, title: e.target.value }))}
                              />
                              <button type="button" className="btn btn-black" onClick={handleSaveResource}>Сохранить</button>
                              <button type="button" className="btn btn-outline" onClick={() => setEditingResourceId(null)}>Отмена</button>
                            </>
                          ) : (
                            <>
                              <div className="analytics-ops-row-main">
                                <strong>{item.title}</strong>
                                <span>{item.resource_type}</span>
                              </div>
                              <div className="analytics-ops-row-actions">
                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  onClick={() => {
                                    setEditingResourceId(item.id);
                                    setEditingResourceDraft({
                                      title: item.title || '',
                                      resource_type: item.resource_type || '',
                                    });
                                  }}
                                >
                                  Изменить
                                </button>
                                <button type="button" className="btn btn-outline" onClick={() => handleDeleteResource(item.id)}>
                                  Удалить
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </article>

                <article className="analytics-ops-card analytics-ops-card--wide">
                  <h4>Услуги</h4>
                  <div className="analytics-ops-inline-form analytics-ops-inline-form--service">
                    <input
                      className="input-main"
                      placeholder="Название услуги"
                      value={newServiceDraft.title}
                      onChange={(e) => setNewServiceDraft((prev) => ({ ...prev, title: e.target.value }))}
                    />
                    <AnalyticsCustomSelect
                      value={newServiceDraft.target_role}
                      onChange={(selectedValue) => setNewServiceDraft((prev) => ({ ...prev, target_role: selectedValue }))}
                      ariaLabel="Выбор роли для услуги"
                      options={[
                        { value: 'master', label: 'master' },
                        { value: 'doctor', label: 'doctor' },
                      ]}
                    />
                    <input
                      className="input-main"
                      type="number"
                      min="1"
                      placeholder="Минут"
                      value={newServiceDraft.duration_minutes}
                      onChange={(e) => setNewServiceDraft((prev) => ({ ...prev, duration_minutes: e.target.value }))}
                    />
                    <input
                      className="input-main"
                      type="number"
                      min="0"
                      placeholder="Цена (руб)"
                      value={newServiceDraft.price_rub}
                      onChange={(e) => setNewServiceDraft((prev) => ({ ...prev, price_rub: e.target.value }))}
                    />
                    <input
                      className="input-main"
                      placeholder="Фильтры ресурсов, через запятую"
                      value={newServiceDraft.resource_type_filters}
                      onChange={(e) =>
                        setNewServiceDraft((prev) => ({ ...prev, resource_type_filters: e.target.value }))
                      }
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateService}>
                      Добавить
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {serviceItems.map((item) => {
                      const isEditing = editingServiceId === item.id;
                      return (
                        <div key={item.id} className="analytics-ops-row">
                          {isEditing ? (
                            <>
                              <input
                                className="input-main"
                                value={editingServiceDraft.title}
                                onChange={(e) => setEditingServiceDraft((prev) => ({ ...prev, title: e.target.value }))}
                              />
                              <input
                                className="input-main"
                                type="number"
                                min="1"
                                value={editingServiceDraft.duration_minutes}
                                onChange={(e) =>
                                  setEditingServiceDraft((prev) => ({ ...prev, duration_minutes: e.target.value }))
                                }
                              />
                              <input
                                className="input-main"
                                type="number"
                                min="0"
                                value={editingServiceDraft.price_rub}
                                onChange={(e) =>
                                  setEditingServiceDraft((prev) => ({ ...prev, price_rub: e.target.value }))
                                }
                              />
                              <button type="button" className="btn btn-black" onClick={handleSaveService}>Сохранить</button>
                              <button type="button" className="btn btn-outline" onClick={() => setEditingServiceId(null)}>Отмена</button>
                            </>
                          ) : (
                            <>
                              <div className="analytics-ops-row-main">
                                <strong>{item.title}</strong>
                                <span>
                                  {item.target_role} · {item.duration_minutes} мин · {formatServicePriceLabel(item.price_minor)}
                                </span>
                              </div>
                              <div className="analytics-ops-row-actions">
                                <button
                                  type="button"
                                  className="btn btn-outline"
                                  onClick={() => {
                                    setEditingServiceId(item.id);
                                    setEditingServiceDraft({
                                      title: item.title || '',
                                      target_role: item.target_role || 'master',
                                      duration_minutes: item.duration_minutes || 60,
                                      price_rub: minorToRubInput(item.price_minor),
                                      resource_type_filters: Array.isArray(item.resource_type_filters)
                                        ? item.resource_type_filters.join(', ')
                                        : '',
                                    });
                                  }}
                                >
                                  Изменить
                                </button>
                                <button type="button" className="btn btn-outline" onClick={() => handleDeleteService(item.id)}>
                                  Удалить
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </article>

                <article className="analytics-ops-card analytics-ops-card--wide">
                  <h4>Расписание</h4>
                  <div className="analytics-ops-inline-form analytics-ops-inline-form--schedule">
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Начало</span>
                      <input
                        className="input-main analytics-datetime-input"
                        type="datetime-local"
                        step={300}
                        value={newScheduleDraft.starts_at}
                        onChange={(e) =>
                          setNewScheduleDraft((prev) => {
                            const nextStartsAt = e.target.value;
                            const nextDraft = { ...prev, starts_at: nextStartsAt };
                            const currentEndMs = Date.parse(prev.ends_at || '');
                            const nextStartMs = Date.parse(nextStartsAt || '');
                            if (!prev.ends_at || (Number.isFinite(nextStartMs) && Number.isFinite(currentEndMs) && currentEndMs <= nextStartMs)) {
                              const suggestedEnd = addMinutesToLocalDateTime(nextStartsAt, 60);
                              nextDraft.ends_at = suggestedEnd || prev.ends_at;
                            }
                            return nextDraft;
                          })
                        }
                      />
                    </div>
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Окончание</span>
                      <input
                        className="input-main analytics-datetime-input"
                        type="datetime-local"
                        step={300}
                        value={newScheduleDraft.ends_at}
                        onChange={(e) => setNewScheduleDraft((prev) => ({ ...prev, ends_at: e.target.value }))}
                      />
                    </div>
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Сотрудник</span>
                      <AnalyticsCustomSelect
                        value={newScheduleDraft.staff_id}
                        onChange={(selectedValue) => setNewScheduleDraft((prev) => ({ ...prev, staff_id: selectedValue }))}
                        placeholder="Сотрудник (опц.)"
                        ariaLabel="Выбор сотрудника для слота"
                        options={[
                          { value: '', label: 'Сотрудник (опц.)' },
                          ...staffItems.map((staff) => ({ value: staff.id, label: staff.full_name })),
                        ]}
                      />
                    </div>
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Ресурс</span>
                      <AnalyticsCustomSelect
                        value={newScheduleDraft.resource_id}
                        onChange={(selectedValue) => setNewScheduleDraft((prev) => ({ ...prev, resource_id: selectedValue }))}
                        placeholder="Ресурс (опц.)"
                        ariaLabel="Выбор ресурса для слота"
                        options={[
                          { value: '', label: 'Ресурс (опц.)' },
                          ...resourceItems.map((resource) => ({ value: resource.id, label: resource.title })),
                        ]}
                      />
                    </div>
                    <button type="button" className="btn btn-black" onClick={handleCreateScheduleSlot}>
                      Добавить слот
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {scheduleItems.map((item) => (
                      <div key={item.id} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)}</strong>
                          <span>
                            staff:{item.staff_id || '-'} · resource:{item.resource_id || '-'}
                          </span>
                        </div>
                        <div className="analytics-ops-row-actions">
                          <button type="button" className="btn btn-outline" onClick={() => handleDeleteScheduleSlot(item.id)}>
                            Удалить
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="analytics-ops-card analytics-ops-card--wide">
                  <h4>Записи</h4>
                  <div className="analytics-ops-inline-form analytics-ops-inline-form--appointment">
                    <input
                      className="input-main"
                      placeholder="client_external_id"
                      value={newAppointmentDraft.client_external_id}
                      onChange={(e) =>
                        setNewAppointmentDraft((prev) => ({ ...prev, client_external_id: e.target.value }))
                      }
                    />
                    <input
                      className="input-main"
                      placeholder="Имя клиента"
                      value={newAppointmentDraft.client_name}
                      onChange={(e) => setNewAppointmentDraft((prev) => ({ ...prev, client_name: e.target.value }))}
                    />
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Начало</span>
                      <input
                        className="input-main analytics-datetime-input"
                        type="datetime-local"
                        step={300}
                        value={newAppointmentDraft.starts_at}
                        onChange={(e) =>
                          setNewAppointmentDraft((prev) => {
                            const nextStartsAt = e.target.value;
                            const nextDraft = { ...prev, starts_at: nextStartsAt };
                            const currentEndMs = Date.parse(prev.ends_at || '');
                            const nextStartMs = Date.parse(nextStartsAt || '');
                            if (!prev.ends_at || (Number.isFinite(nextStartMs) && Number.isFinite(currentEndMs) && currentEndMs <= nextStartMs)) {
                              const suggestedEnd = addMinutesToLocalDateTime(nextStartsAt, 60);
                              nextDraft.ends_at = suggestedEnd || prev.ends_at;
                            }
                            return nextDraft;
                          })
                        }
                      />
                    </div>
                    <div className="analytics-time-field">
                      <span className="analytics-time-field-label">Окончание</span>
                      <input
                        className="input-main analytics-datetime-input"
                        type="datetime-local"
                        step={300}
                        value={newAppointmentDraft.ends_at}
                        onChange={(e) => setNewAppointmentDraft((prev) => ({ ...prev, ends_at: e.target.value }))}
                      />
                    </div>
                    <AnalyticsCustomSelect
                      value={newAppointmentDraft.staff_id}
                      onChange={(selectedValue) => setNewAppointmentDraft((prev) => ({ ...prev, staff_id: selectedValue }))}
                      placeholder="Сотрудник"
                      ariaLabel="Выбор сотрудника для записи"
                      options={[
                        { value: '', label: 'Сотрудник' },
                        ...staffItems.map((staff) => ({ value: staff.id, label: staff.full_name })),
                      ]}
                    />
                    <AnalyticsCustomSelect
                      value={newAppointmentDraft.resource_id}
                      onChange={(selectedValue) => setNewAppointmentDraft((prev) => ({ ...prev, resource_id: selectedValue }))}
                      placeholder="Ресурс"
                      ariaLabel="Выбор ресурса для записи"
                      options={[
                        { value: '', label: 'Ресурс' },
                        ...resourceItems.map((resource) => ({ value: resource.id, label: resource.title })),
                      ]}
                    />
                    <AnalyticsCustomSelect
                      value={newAppointmentDraft.service_id}
                      onChange={(selectedValue) => setNewAppointmentDraft((prev) => ({ ...prev, service_id: selectedValue }))}
                      placeholder="Услуга"
                      ariaLabel="Выбор услуги для записи"
                      options={[
                        { value: '', label: 'Услуга' },
                        ...serviceItems.map((service) => ({ value: service.id, label: service.title })),
                      ]}
                    />
                    <button type="button" className="btn btn-black" onClick={handleCreateAppointment}>
                      Создать запись
                    </button>
                  </div>
                  <div className="analytics-ops-list">
                    {appointmentItems.map((item) => (
                      <div key={item.id} className="analytics-ops-row">
                        <div className="analytics-ops-row-main">
                          <strong>{item.client_name || item.client_external_id}</strong>
                          <span>
                            {formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)} · status: {item.status}
                          </span>
                        </div>
                        <div className="analytics-ops-row-actions">
                          <button type="button" className="btn btn-outline" onClick={() => handleRescheduleAppointmentQuick(item)}>
                            +1ч перенос
                          </button>
                          <button type="button" className="btn btn-outline" onClick={() => handleConfirmAppointmentQuick(item)}>
                            Подтвердить
                          </button>
                          <button type="button" className="btn btn-outline" onClick={() => handleCancelAppointmentQuick(item)}>
                            Отменить
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>

              </div>

              <article className="analytics-ops-card analytics-ops-card--wide">
                <h4>Календарь и занятость ({calendarView})</h4>
                {occupancyData?.matrix?.length ? (
                  <div className="analytics-occupancy-matrix">
                    <div className="analytics-occupancy-header-row">
                      <span>Ресурс</span>
                      {(occupancyData.matrix[0]?.cells || []).map((cell) => (
                        <span key={`${cell.starts_at}-${cell.ends_at}`}>
                          {formatDateShort(cell.starts_at)} {new Date(cell.starts_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      ))}
                    </div>
                    {occupancyData.matrix.map((row) => (
                      <div key={row.resource_id} className="analytics-occupancy-row">
                        <span className="analytics-occupancy-resource">{row.resource_title}</span>
                        {row.cells.map((cell) => (
                          <span
                            key={`${row.resource_id}-${cell.starts_at}`}
                            className={`analytics-occupancy-cell ${
                              cell.appointments_count > 1
                                ? 'analytics-occupancy-cell--conflict'
                                : cell.occupied
                                  ? 'analytics-occupancy-cell--occupied'
                                  : 'analytics-occupancy-cell--free'
                            }`}
                            title={`appointments: ${cell.appointments_count}`}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="analytics-note">Нет данных занятости за выбранный период.</p>
                )}
              </article>

              {selectedCalendarDay ? (
                <div className="analytics-admin-day-modal-backdrop" onClick={() => setSelectedCalendarDay(null)}>
                  <article className="analytics-admin-day-modal" onClick={(e) => e.stopPropagation()}>
                    <div className="analytics-admin-day-modal-head">
                      <h4>{selectedCalendarDay.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', year: 'numeric' })}</h4>
                      <button type="button" className="btn btn-outline" onClick={() => setSelectedCalendarDay(null)}>
                        Закрыть
                      </button>
                    </div>

                    <div className="analytics-admin-day-modal-columns">
                      <section className="analytics-admin-day-modal-section">
                        <h5>Записи на день</h5>
                        {selectedDayAppointments.length ? (
                          <div className="analytics-ops-list">
                            {selectedDayAppointments.map((item) => {
                              const staffName = staffNameById.get(item.staff_id) || 'Сотрудник не назначен';
                              const serviceTitle = serviceTitleById.get(item.service_id) || 'Без услуги';
                              return (
                                <div key={`calendar-appt-${item.id}`} className="analytics-ops-row">
                                  <div className="analytics-ops-row-main">
                                    <strong>{item.client_name || item.client_external_id}</strong>
                                    <span>
                                      {formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)}
                                    </span>
                                    <span>{staffName} · {serviceTitle} · статус: {item.status}</span>
                                  </div>
                                <div className="analytics-ops-row-actions">
                                  <button
                                    type="button"
                                    className="btn btn-outline"
                                    onClick={() => handleDeleteAppointmentQuick(item)}
                                  >
                                    Удалить
                                  </button>
                                </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="analytics-note">На выбранный день записей нет.</p>
                        )}
                      </section>

                      <section className="analytics-admin-day-modal-section">
                        <h5>График сотрудников</h5>
                        <div className="analytics-ops-inline-form analytics-admin-day-schedule-form">
                          <AnalyticsCustomSelect
                            value={calendarShiftDraft.staff_id}
                            onChange={(selectedValue) =>
                              setCalendarShiftDraft((prev) => ({ ...prev, staff_id: selectedValue }))
                            }
                            placeholder="Выберите сотрудника"
                            ariaLabel="Выбор сотрудника для графика"
                            options={[
                              { value: '', label: 'Выберите сотрудника' },
                              ...staffItems.map((staff) => ({ value: staff.id, label: staff.full_name })),
                            ]}
                          />
                          <AnalyticsCustomSelect
                            value={calendarShiftDraft.resource_id}
                            onChange={(selectedValue) =>
                              setCalendarShiftDraft((prev) => ({ ...prev, resource_id: selectedValue }))
                            }
                            placeholder="Ресурс (опционально)"
                            ariaLabel="Выбор ресурса для графика"
                            options={[
                              { value: '', label: 'Ресурс (опционально)' },
                              ...resourceItems.map((resource) => ({ value: resource.id, label: resource.title })),
                            ]}
                          />
                        </div>

                        <div className="analytics-admin-shift-ranges">
                          {calendarShiftDraft.ranges.map((range, idx) => (
                            <div key={`calendar-range-${idx}`} className="analytics-admin-shift-range-row">
                              <div className="analytics-time-field analytics-time-field--compact">
                                <span className="analytics-time-field-label">С</span>
                                <input
                                  className="input-main analytics-time-input"
                                  type="time"
                                  step={300}
                                  value={range.starts_at}
                                  onChange={(e) => handleUpdateShiftRange(idx, 'starts_at', e.target.value)}
                                />
                              </div>
                              <div className="analytics-time-field analytics-time-field--compact">
                                <span className="analytics-time-field-label">До</span>
                                <input
                                  className="input-main analytics-time-input"
                                  type="time"
                                  step={300}
                                  value={range.ends_at}
                                  onChange={(e) => handleUpdateShiftRange(idx, 'ends_at', e.target.value)}
                                />
                              </div>
                              <button
                                type="button"
                                className="btn btn-outline"
                                onClick={() => handleRemoveShiftRange(idx)}
                                disabled={calendarShiftDraft.ranges.length <= 1}
                              >
                                Удалить
                              </button>
                            </div>
                          ))}
                        </div>

                        <div className="analytics-admin-day-modal-actions">
                          <button type="button" className="btn btn-outline" onClick={handleAddShiftRange}>
                            + Интервал
                          </button>
                          <button type="button" className="btn btn-black" onClick={handleCreateCalendarShifts}>
                            Сохранить график
                          </button>
                        </div>

                        <div className="analytics-ops-list">
                          {selectedDaySchedules.length ? (
                            selectedDaySchedules.map((item) => (
                              <div key={`calendar-schedule-${item.id}`} className="analytics-ops-row">
                                <div className="analytics-ops-row-main">
                                  <strong>{formatDateTime(item.starts_at)} - {formatDateTime(item.ends_at)}</strong>
                                  <span>{staffNameById.get(item.staff_id) || 'Без сотрудника'}</span>
                                </div>
                                <div className="analytics-ops-row-actions">
                                  <button
                                    type="button"
                                    className="btn btn-outline"
                                    onClick={() => handleDeleteScheduleSlot(item.id)}
                                  >
                                    Удалить
                                  </button>
                                </div>
                              </div>
                            ))
                          ) : (
                            <p className="analytics-note">На этот день график еще не назначен.</p>
                          )}
                        </div>
                      </section>
                    </div>
                  </article>
                </div>
              ) : null}
            </section>
          ) : selectedSection === ANALYTICS_SECTIONS.REFUNDS ? (
            <section className="analytics-operations">
              <h3>Заявки на возврат</h3>
              <p className="analytics-note">
                Заявки создаются при отмене оплаченной записи менее чем за 24 часа до визита (или после визита).
                Возврат более чем за 24 часа оформляется автоматически через ЮKassa.
              </p>
              {opsLoading ? (
                <p className="analytics-note">Загрузка...</p>
              ) : refundRequestItems.length === 0 ? (
                <p className="analytics-note">Нет заявок на возврат.</p>
              ) : (
                <div className="analytics-ops-list">
                  {refundRequestItems.map((item) => (
                    <div key={item.id} className="analytics-ops-row analytics-ops-row--refund">
                      <div className="analytics-ops-row-main">
                        <strong>{item.client_full_name || item.client_external_id}</strong>
                        <span>
                          {item.client_phone ? `Тел.: ${item.client_phone} · ` : ''}
                          ID чата: {item.client_external_id} · {refundChannelLabel(item.source_channel)}
                        </span>
                        <span>
                          {item.appointment_starts_at ? formatDateTime(item.appointment_starts_at) : '—'}
                          {item.service_title ? ` · ${item.service_title}` : ''}
                          {' · '}
                          {item.amount_rub} ₽ · {refundStatusLabel(item.status)}
                          {item.refund_mode === 'auto' ? ' · автовозврат' : ''}
                        </span>
                        {item.cancel_reason ? <span>Причина отмены: {item.cancel_reason}</span> : null}
                      </div>
                      {item.status === 'pending' ? (
                        <div className="analytics-ops-row-actions">
                          <button type="button" className="btn btn-black" onClick={() => handleApproveRefundRequest(item)}>
                            Одобрить
                          </button>
                          <button type="button" className="btn btn-outline" onClick={() => handleRejectRefundRequest(item)}>
                            Отказать
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </section>
          ) : (
            <>
            <section className="analytics-broadcast analytics-broadcast--whatsapp">
              <h3>Рассылка в Telegram</h3>
              <p className="analytics-note">
                Одно и то же сообщение от вашего лица (как в чатах) получат пользователи из Telegram bot и Telegram
                userbot диалогов.
              </p>

              {broadcastStatsLoading ? (
                <p className="analytics-broadcast-muted">Загрузка аудитории...</p>
              ) : broadcastStats ? (
                <div className="analytics-broadcast-stats">
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(broadcastStats.telegram_users_total || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Всего в Telegram (по аналитике)</span>
                  </article>
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(broadcastStats.frozen_among_telegram || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Заморожено среди них</span>
                  </article>
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(broadcastStats.eligible_when_skip_frozen || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Доступно при пропуске замороженных</span>
                  </article>
                </div>
              ) : (
                <p className="analytics-broadcast-muted">Не удалось загрузить аудиторию</p>
              )}

              <div className="analytics-broadcast-warning" role="note">
                Рассылка может занять время: между отправками есть небольшая пауза, чтобы не перегружать Telegram. За один
                раз отправляется не больше выбранного лимита; при большой базе повторите рассылку позже (уже отправленным
                придёт дубликат — используйте осмотрительно).
              </div>

              <div className="analytics-broadcast-options">
                <label className="analytics-broadcast-checkbox">
                  <input
                    type="checkbox"
                    checked={broadcastSkipFrozen}
                    onChange={(e) => setBroadcastSkipFrozen(e.target.checked)}
                    disabled={isBroadcasting || isWaBroadcasting}
                  />
                  Не отправлять замороженным пользователям
                </label>
                <label className="analytics-broadcast-limit">
                  <span className="analytics-broadcast-limit-label">Максимум за раз</span>
                  <BroadcastLimitSelect
                    value={broadcastMaxRecipients}
                    onChange={setBroadcastMaxRecipients}
                    disabled={isBroadcasting || isWaBroadcasting}
                    options={BROADCAST_LIMIT_OPTIONS}
                  />
                </label>
              </div>

              <p className="analytics-broadcast-planned">
                Будет отправлено сообщений (Telegram):{' '}
                <strong>{formatNumber(plannedBroadcastRecipients)}</strong>
              </p>

              <div className="analytics-broadcast-composer">
                <textarea
                  className="input-main analytics-broadcast-textarea"
                  rows={5}
                  placeholder="Текст рассылки..."
                  value={broadcastBody}
                  onChange={(e) => setBroadcastBody(e.target.value)}
                  disabled={isBroadcasting || isWaBroadcasting}
                />
                <button
                  type="button"
                  className="btn btn-black analytics-broadcast-send"
                  onClick={handleBroadcastSend}
                  disabled={isBroadcasting || isWaBroadcasting || plannedBroadcastRecipients <= 0}
                >
                  {isBroadcasting ? 'Отправка...' : 'Разослать в Telegram'}
                </button>
              </div>

              {broadcastResult && broadcastResult.errors?.length > 0 ? (
                <div className="analytics-broadcast-errors">
                  <h4>Ошибки доставки (фрагмент)</h4>
                  <ul>
                    {broadcastResult.errors.map((err, idx) => (
                      <li key={`${err.user_external_id}-${idx}`}>
                        <code>{err.user_external_id}</code> ({channelLabel(err.channel)}): {err.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>

            <section className="analytics-broadcast">
              <h3>Рассылка в WhatsApp (userbot)</h3>
              <p className="analytics-note">
                Сообщения уходят с того же WhatsApp userbot, который подключён к агенту. Нужен запущенный сервис
                userbot на сервере (как для входящих). Аудитория — пользователи, с которыми уже был диалог в этом
                канале (по аналитике).
              </p>

              {waBroadcastStatsLoading ? (
                <p className="analytics-broadcast-muted">Загрузка аудитории WhatsApp...</p>
              ) : waBroadcastStats ? (
                <div className="analytics-broadcast-stats">
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(waBroadcastStats.whatsapp_userbot_users_total || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Всего в WhatsApp userbot (по аналитике)</span>
                  </article>
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(waBroadcastStats.frozen_among_whatsapp_userbot || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Заморожено среди них</span>
                  </article>
                  <article className="analytics-broadcast-stat">
                    <span className="analytics-broadcast-stat-value">
                      {formatNumber(Number(waBroadcastStats.eligible_when_skip_frozen || 0))}
                    </span>
                    <span className="analytics-broadcast-stat-label">Доступно при пропуске замороженных</span>
                  </article>
                </div>
              ) : (
                <p className="analytics-broadcast-muted">Не удалось загрузить аудиторию WhatsApp</p>
              )}

              <div className="analytics-broadcast-warning" role="note">
                Между отправками в WhatsApp стоит пауза (~0,35 с), чтобы снизить риск ограничений со стороны WhatsApp.
              </div>

              <p className="analytics-broadcast-planned">
                Будет отправлено сообщений (WhatsApp):{' '}
                <strong>{formatNumber(plannedWaBroadcastRecipients)}</strong>
              </p>

              <div className="analytics-broadcast-composer">
                <textarea
                  className="input-main analytics-broadcast-textarea"
                  rows={5}
                  placeholder="Текст рассылки в WhatsApp..."
                  value={waBroadcastBody}
                  onChange={(e) => setWaBroadcastBody(e.target.value)}
                  disabled={isBroadcasting || isWaBroadcasting}
                />
                <button
                  type="button"
                  className="btn btn-black analytics-broadcast-send"
                  onClick={handleWaBroadcastSend}
                  disabled={isBroadcasting || isWaBroadcasting || plannedWaBroadcastRecipients <= 0}
                >
                  {isWaBroadcasting ? 'Отправка...' : 'Разослать в WhatsApp'}
                </button>
              </div>

              {waBroadcastResult && waBroadcastResult.errors?.length > 0 ? (
                <div className="analytics-broadcast-errors">
                  <h4>Ошибки доставки WhatsApp (фрагмент)</h4>
                  <ul>
                    {waBroadcastResult.errors.map((err, idx) => (
                      <li key={`wa-${err.user_external_id}-${idx}`}>
                        <code>{err.user_external_id}</code> ({channelLabel(err.channel)}): {err.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const AgentDetailedAnalyticsPage = () => {
  return (
    <MainLayout>
      <AgentDetailedAnalyticsPageContent />
    </MainLayout>
  );
};

export default AgentDetailedAnalyticsPage;
