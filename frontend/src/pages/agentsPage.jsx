/**
 * Agents Page
 * Display user's agents and manage them
 */

import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../components/Layout';
import Loading from '../components/Loading';
import { useAsync } from '../hooks/useAsync';
import agentService from '../services/agentService';
import { useNotification } from '../context/useNotification';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/agentsPage.css';

const MOCK_AGENTS = [
  { id: 1, name: 'МОП', role: 'support', status: 'active' },
  { id: 2, name: 'Консультант', role: 'sales', status: 'active' },
  { id: 3, name: 'Онлайн преподаватель', role: 'assistant', status: 'active' },
];

const AgentCard = ({ agent, onEdit, onDelete }) => {
  return (
    <div className="agent-item">
      <div className="agent-info">
        <span className="agent-status-dot" title={agent.status}></span>
        <div className="agent-details">
          <h3 className="agent-name">{agent.name}</h3>
          <p className="agent-role">{agent.role}</p>
        </div>
      </div>
      <div className="agent-actions">
        <button
          className="edit-btn"
          onClick={() => onEdit(agent.id)}
          title="Edit agent"
          aria-label="Edit agent"
        >
          <img src="https://img.icons8.com/material-rounded/24/000000/pencil.png" alt="edit" />
        </button>
        <button
          className="delete-btn"
          onClick={() => onDelete(agent.id)}
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
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    // Load agents - using mock data for now
    // execute(); // Uncomment when API is ready
    // For demo purposes:
    setTimeout(() => {}, 100);
  }, []);

  const handleCreateAgent = () => {
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  const handleEditAgent = (agentId) => {
    navigate(NAVIGATION_ROUTES.EDIT_AGENT(agentId));
  };

  const handleDeleteAgent = async (agentId) => {
    if (!window.confirm('Вы уверены, что хотите удалить агента?')) {
      return;
    }

    try {
      await agentService.delete(agentId);
      showSuccess('Агент успешно удален!');
      // Reload agents
      execute();
    } catch (error) {
      showError('Ошибка при удалении агента');
    }
  };

  if (isLoading) {
    return <Loading message="Загрузка агентов..." />;
  }

  const displayAgents = agents || MOCK_AGENTS;

  return (
    <div className="agents-page-content">
      <section className="agents-section">
        <div className="section-header">
          <h2 className="section-title">Ваши агенты:</h2>
          <button className="btn btn-black btn-add" onClick={handleCreateAgent}>
            + Новый агент
          </button>
        </div>

        {displayAgents.length === 0 ? (
          <div className="empty-state">
            <p>У вас еще нет агентов</p>
            <button className="btn btn-black" onClick={handleCreateAgent}>
              Создать первого агента
            </button>
          </div>
        ) : (
          <div className="agents-list">
            {displayAgents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onEdit={handleEditAgent}
                onDelete={handleDeleteAgent}
              />
            ))}
          </div>
        )}
      </section>
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