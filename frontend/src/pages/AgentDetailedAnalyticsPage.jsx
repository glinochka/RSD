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

const buildOverviewMetrics = (summary, docsCount) => {
  const totalUsers = Number(summary?.unique_users || 0);
  const totalQuestions = Number(summary?.total_questions || 0);
  const returningUsers = Number(summary?.returning_users || 0);
  const dayOneReturningUsers = Number(summary?.returned_next_day_users || 0);
  const avgQuestionsPerUser = Number(summary?.avg_questions_per_user || 0);
  const conversionToQualified = Number(summary?.qualified_leads_share_percent || 0);

  return [
    { id: 'users', label: 'Написало агенту', value: formatNumber(totalUsers) },
    { id: 'questions', label: 'Всего вопросов', value: formatNumber(totalQuestions) },
    { id: 'returning', label: 'Вернулось к агенту', value: formatNumber(returningUsers) },
    { id: 'day1', label: 'Вернулось на следующий день', value: formatNumber(dayOneReturningUsers) },
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

const AgentDetailedAnalyticsPageContent = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showError } = useNotification();
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSection, setSelectedSection] = useState(ANALYTICS_SECTIONS.OVERVIEW);
  const [agent, setAgent] = useState(null);
  const [metrics, setMetrics] = useState([]);
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
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => navigate(NAVIGATION_ROUTES.AGENTS)}
        >
          ← Назад к управлению агентами
        </button>
        <div>
          <h2>Детальная аналитика</h2>
          <p>
            {agent?.bot_username ? `@${agent.bot_username}` : `Агент #${botId}`}
          </p>
        </div>
      </div>

      <div className="agent-analytics-layout">
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
