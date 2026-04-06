import React, { useEffect, useMemo, useState } from 'react';
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
};
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

const mapChatsPayload = (payload) => {
  const users = Array.isArray(payload?.users) ? payload.users : [];
  return users.map((user) => ({
    id: user.user_external_id,
    name: user.user_display_name || `Пользователь ${user.user_external_id}`,
    questions: Number(user.questions_count || 0),
    lastMessageAt: formatDateTime(user.last_message_at),
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
  const { showError } = useNotification();
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSection, setSelectedSection] = useState(ANALYTICS_SECTIONS.OVERVIEW);
  const [agent, setAgent] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [selectedDays, setSelectedDays] = useState(30);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [chatUsers, setChatUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState(null);

  const botId = useMemo(() => Number(id), [id]);

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

  const selectedUser = useMemo(
    () => chatUsers.find((user) => user.id === selectedUserId) || null,
    [chatUsers, selectedUserId]
  );

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
          ) : (
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
                        className={`analytics-user-item ${selectedUserId === user.id ? 'analytics-user-item--active' : ''}`}
                        onClick={() => setSelectedUserId(user.id)}
                      >
                        <strong>{user.name}</strong>
                        <span>{user.questions} вопросов</span>
                        <span>{user.lastMessageAt}</span>
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
                        <h4>{selectedUser.name}</h4>
                        <p>Вопросов: {selectedUser.questions}</p>
                      </header>
                      <div className="analytics-messages-list">
                        {selectedUser.messages.map((message) => (
                          <div
                            key={message.id}
                            className={`analytics-message-bubble analytics-message-bubble--${message.role}`}
                          >
                            <span className="analytics-message-role">
                              {message.role === 'user' ? selectedUser.name : 'Агент'}
                            </span>
                            <p>{message.text}</p>
                            <time>{message.timestamp}</time>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
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
