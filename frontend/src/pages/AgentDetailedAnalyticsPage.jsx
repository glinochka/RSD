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

const formatNumber = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0';
  return new Intl.NumberFormat('ru-RU').format(value);
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
    id: user.user_external_id,
    name: user.user_display_name || `Пользователь ${user.user_external_id}`,
    questions: Number(user.questions_count || 0),
    lastMessageAt: formatDateTime(user.last_message_at),
    isFrozen: Boolean(user.is_frozen),
    messages: (Array.isArray(user.messages) ? user.messages : []).map((item, index) => ({
      id: `${user.user_external_id}-${index}-${item.created_at || 'time'}`,
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
  const [timeline, setTimeline] = useState([]);
  const [selectedDays, setSelectedDays] = useState(30);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [chatUsers, setChatUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [ownerReplyText, setOwnerReplyText] = useState('');
  const [isSendingOwnerReply, setIsSendingOwnerReply] = useState(false);
  const [isTogglingFreeze, setIsTogglingFreeze] = useState(false);
  const [broadcastStats, setBroadcastStats] = useState(null);
  const [broadcastStatsLoading, setBroadcastStatsLoading] = useState(false);
  const [broadcastBody, setBroadcastBody] = useState('');
  const [broadcastSkipFrozen, setBroadcastSkipFrozen] = useState(true);
  const [broadcastMaxRecipients, setBroadcastMaxRecipients] = useState(500);
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [broadcastResult, setBroadcastResult] = useState(null);

  const botId = useMemo(() => Number(id), [id]);

  const plannedBroadcastRecipients = useMemo(() => {
    if (!broadcastStats) return 0;
    const base = broadcastSkipFrozen
      ? Number(broadcastStats.eligible_when_skip_frozen || 0)
      : Number(broadcastStats.telegram_users_total || 0);
    return Math.min(base, broadcastMaxRecipients);
  }, [broadcastStats, broadcastSkipFrozen, broadcastMaxRecipients]);

  useEffect(() => {
    if (!Number.isFinite(botId) || botId <= 0) {
      showError('Некорректный id агента');
      navigate(NAVIGATION_ROUTES.AGENTS);
      return;
    }

    const loadData = async () => {
      setIsLoading(true);
      try {
        const [agentData, docs, summary, chats] = await Promise.all([
          agentService.getById(botId),
          agentService.getDocumentsByBotId(botId),
          agentService.getAnalyticsSummary(botId),
          agentService.getAnalyticsChats(botId, { limit_users: 100, messages_per_user: 100 }),
        ]);
        const mappedUsers = mapChatsPayload(chats);
        setAgent(agentData);
        setChatUsers(mappedUsers);
        setSelectedUserId(mappedUsers[0]?.id || null);
        setMetrics(buildOverviewMetrics(summary, docs?.length || 0));
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
        showError(error?.message || 'Не удалось загрузить данные рассылки');
      } finally {
        setBroadcastStatsLoading(false);
      }
    };

    loadBroadcastStats();
  }, [selectedSection, botId, showError]);

  const selectedUser = useMemo(
    () => chatUsers.find((user) => user.id === selectedUserId) || null,
    [chatUsers, selectedUserId]
  );

  const canSendTelegramToUser = Boolean(selectedUser && /^\d+$/.test(String(selectedUser.id)));

  useEffect(() => {
    setOwnerReplyText('');
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
      await agentService.setUserFrozen(botId, selectedUser.id, nextFrozen);
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

  const handleSendOwnerMessage = async () => {
    if (!selectedUser) return;
    const text = ownerReplyText.trim();
    if (!text) {
      showError('Введите текст сообщения');
      return;
    }
    if (!canSendTelegramToUser) {
      showError('Отправка доступна только пользователям из Telegram (числовой id)');
      return;
    }
    setIsSendingOwnerReply(true);
    try {
      await agentService.sendTelegramMessageAsOwner(botId, selectedUser.id, text);
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
        `Отправить сообщение ${n} ${noun}? Сообщения уйдут от имени бота в Telegram. Отменить рассылку будет нельзя.`
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
                          <p>Вопросов: {selectedUser.questions}</p>
                        </div>
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
                      </header>
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
                      <div className="analytics-chat-composer">
                        <p className="analytics-chat-composer-hint">
                          {canSendTelegramToUser
                            ? 'Сообщение будет доставлено пользователю в Telegram от имени бота.'
                            : 'Отправка только для диалогов из Telegram (числовой id пользователя).'}
                        </p>
                        <div className="analytics-chat-composer-row">
                          <textarea
                            className="input-main analytics-chat-composer-input"
                            rows={2}
                            placeholder="Текст от вашего лица..."
                            value={ownerReplyText}
                            onChange={(e) => setOwnerReplyText(e.target.value)}
                            disabled={!canSendTelegramToUser || isSendingOwnerReply}
                          />
                          <button
                            type="button"
                            className="btn btn-black analytics-chat-composer-send"
                            onClick={handleSendOwnerMessage}
                            disabled={!canSendTelegramToUser || isSendingOwnerReply}
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
            <section className="analytics-broadcast">
              <h3>Рассылка в Telegram</h3>
              <p className="analytics-note">
                Одно и то же сообщение от вашего лица (как в чатах) получат выбранные пользователи, которые писали боту
                в Telegram. Пользователи из других каналов сюда не попадают.
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
                    disabled={isBroadcasting}
                  />
                  Не отправлять замороженным пользователям
                </label>
                <label className="analytics-broadcast-limit">
                  <span className="analytics-broadcast-limit-label">Максимум за раз</span>
                  <BroadcastLimitSelect
                    value={broadcastMaxRecipients}
                    onChange={setBroadcastMaxRecipients}
                    disabled={isBroadcasting}
                    options={BROADCAST_LIMIT_OPTIONS}
                  />
                </label>
              </div>

              <p className="analytics-broadcast-planned">
                Будет отправлено сообщений:{' '}
                <strong>{formatNumber(plannedBroadcastRecipients)}</strong>
              </p>

              <div className="analytics-broadcast-composer">
                <textarea
                  className="input-main analytics-broadcast-textarea"
                  rows={5}
                  placeholder="Текст рассылки..."
                  value={broadcastBody}
                  onChange={(e) => setBroadcastBody(e.target.value)}
                  disabled={isBroadcasting}
                />
                <button
                  type="button"
                  className="btn btn-black analytics-broadcast-send"
                  onClick={handleBroadcastSend}
                  disabled={isBroadcasting || plannedBroadcastRecipients <= 0}
                >
                  {isBroadcasting ? 'Отправка...' : 'Разослать'}
                </button>
              </div>

              {broadcastResult && broadcastResult.errors?.length > 0 ? (
                <div className="analytics-broadcast-errors">
                  <h4>Ошибки доставки (фрагмент)</h4>
                  <ul>
                    {broadcastResult.errors.map((err, idx) => (
                      <li key={`${err.user_external_id}-${idx}`}>
                        <code>{err.user_external_id}</code>: {err.detail}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
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
