import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import agentService from '../services/agentService';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/agentDetailedAnalytics.css';

const ANALYTICS_SECTIONS = {
  OVERVIEW: 'overview',
  CHATS: 'chats',
  BROADCAST: 'broadcast',
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

const formatDateTime = (value) => {
  if (!value) return '';
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

const channelLabel = (channel) => {
  if (channel === 'telegram_userbot') return 'Telegram userbot';
  if (channel === 'telegram') return 'Telegram bot';
  if (channel === 'max_bot') return 'MAX bot';
  if (channel === 'max_userbot') return 'MAX userbot';
  if (channel === 'whatsapp_userbot') return 'WhatsApp userbot';
  if (channel === 'external_api') return 'External API';
  if (channel === 'whatsapp_business_api') return 'WhatsApp Business API';
  return channel || 'unknown';
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
  const [metrics, setMetrics] = useState([]);
  const [crmActionMetrics, setCrmActionMetrics] = useState([]);
  const [crmActions, setCrmActions] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [selectedDays, setSelectedDays] = useState(30);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [chatUsers, setChatUsers] = useState([]);
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

  const botId = useMemo(() => Number(id), [id]);

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

  const selectedUser = useMemo(
    () => chatUsers.find((user) => user.id === selectedUserId) || null,
    [chatUsers, selectedUserId]
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

  if (isLoading) {
    return <Loading message="Загрузка аналитики..." />;
  }

  return (
    <div className="agent-analytics-page">
      <div className="agent-analytics-header">
        <div className="agent-analytics-header-main">
          <h2>Детальная аналитика</h2>
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
            className={`analytics-section-btn ${selectedSection === ANALYTICS_SECTIONS.BROADCAST ? 'analytics-section-btn--active' : ''}`}
            onClick={() => setSelectedSection(ANALYTICS_SECTIONS.BROADCAST)}
          >
            Рассылка
          </button>
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
          ) : selectedSection === ANALYTICS_SECTIONS.CHATS ? (
            <section className="analytics-chats">
              <h3>Чаты</h3>
              <div className="analytics-chat-window">
                <aside className="analytics-users-list">
                  {chatUsers.length === 0 ? (
                    <p className="analytics-chat-empty">Пока нет сообщений от пользователей</p>
                  ) : (
                    chatUsers.map((user) => (
                      <button
                        key={user.id}
                        type="button"
                        className={`analytics-user-item ${selectedUserId === user.id ? 'analytics-user-item--active' : ''} ${user.isFrozen ? 'analytics-user-item--frozen' : ''}`}
                        onClick={() => setSelectedUserId(user.id)}
                      >
                        <strong>{user.name}</strong>
                        <span>{channelLabel(user.channel)}</span>
                        <span>{user.questions} вопросов</span>
                        <span>{user.lastMessageAt}</span>
                        {user.isFrozen ? <span className="analytics-user-frozen-badge">Заморожен</span> : null}
                      </button>
                    ))
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
