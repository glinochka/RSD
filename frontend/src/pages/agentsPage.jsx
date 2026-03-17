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
import { useAuth } from '../context/useAuth';
import '../styles/agentsPage.css';

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
  const { isAuthenticated } = useAuth();
  const { data: agents, isLoading, execute } = useAsync(
    () => agentService.getAll(),
    false
  );

  useEffect(() => {
    if (!isAuthenticated) return;
    execute();
  }, [isAuthenticated]);

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
      showError(error?.message || 'Ошибка при удалении агента');
    }
  };

  if (isLoading && isAuthenticated) {
    return <Loading message="Загрузка агентов..." />;
  }

  if (!isAuthenticated) {
    return (
      <div className="agents-page-content">
        <section className="agents-section">
          <div className="empty-state">
            <button className="btn btn-black" onClick={handleCreateAgent}>
              У вас еще нет ни одного ИИ-сотруднника, создайте прямо сейчас
            </button>
          </div>
        </section>
      </div>
    );
  }

  const displayAgents = agents || [];

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