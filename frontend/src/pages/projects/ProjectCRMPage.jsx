/**
 * Project CRM Page
 * Unified view of leads and contacts from all project agents
 */

import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import projectService from '../../services/projectService';
import '../../styles/projectCRMPage.css';

// Icons
const UsersIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

const CalendarIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const PhoneIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
  </svg>
);

const TABS = [
  { id: 'bookings', label: 'Записи', icon: CalendarIcon },
  { id: 'contacts', label: 'Контакты', icon: UsersIcon },
  { id: 'leads', label: 'Лиды', icon: PhoneIcon },
];

const ProjectCRMPage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();

  const [activeTab, setActiveTab] = useState('bookings');
  const [crmData, setCrmData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadCRMData();
  }, [projectId]);

  const loadCRMData = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectCRM(projectId);
      setCrmData(data);
    } catch (error) {
      console.error('Failed to load CRM data:', error);
      showError('Не удалось загрузить CRM данные');
    } finally {
      setIsLoading(false);
    }
  };

  const hasCrmAgents = crmData?.has_crm_admin || false;
  const hasSalesAgents = crmData?.has_sales_manager || false;

  const renderEmptyState = (message, actionText, actionLink) => (
    <div className="crm-empty-state">
      <div className="crm-empty-icon">
        <UsersIcon />
      </div>
      <h4>{message}</h4>
      <p>Добавьте соответствующего агента для управления этими данными</p>
      {actionLink && (
        <a href={actionLink} className="btn btn-black">
          {actionText}
        </a>
      )}
    </div>
  );

  const renderBookingsTab = () => {
    if (!hasCrmAgents) {
      return renderEmptyState(
        'Нет ИИ-администратора',
        'Добавить администратора',
        `#/projects/${projectId}/agents?add=crm_admin`
      );
    }

    const bookings = crmData?.bookings || [];

    return (
      <div className="crm-tab-content">
        {bookings.length === 0 ? (
          <div className="crm-empty-list">
            <p>Пока нет записей</p>
            <span>Записи появятся, когда клиенты начнут бронировать через агента</span>
          </div>
        ) : (
          <div className="crm-list">
            {bookings.map((booking) => (
              <div key={booking.id} className="crm-item">
                <div className="crm-item-header">
                  <span className={`crm-status crm-status--${booking.status}`}>
                    {booking.status}
                  </span>
                  <span className="crm-date">{booking.created_at}</span>
                </div>
                <h5 className="crm-item-title">{booking.client_name || 'Клиент'}</h5>
                <p className="crm-item-subtitle">{booking.service_title}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderContactsTab = () => {
    if (!hasSalesAgents) {
      return renderEmptyState(
        'Нет менеджера по продажам',
        'Добавить менеджера',
        `#/projects/${projectId}/agents?add=sales_manager`
      );
    }

    const contacts = crmData?.contacts || [];

    return (
      <div className="crm-tab-content">
        {contacts.length === 0 ? (
          <div className="crm-empty-list">
            <p>Пока нет контактов</p>
            <span>Контакты добавляются при взаимодействии с агентом продаж</span>
          </div>
        ) : (
          <div className="crm-list">
            {contacts.map((contact) => (
              <div key={contact.id} className="crm-item">
                <h5 className="crm-item-title">{contact.name || 'Контакт'}</h5>
                <p className="crm-item-subtitle">{contact.phone || contact.email}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderLeadsTab = () => (
    <div className="crm-tab-content">
      <div className="crm-empty-list">
        <p>Лиды из ИИ-менеджера</p>
        <span>Этот раздел будет доступен при наличии ai_manager агента</span>
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <div className="project-crm-page project-crm-page--loading">
        <div className="crm-loading">
          <div className="spinner" />
          <p>Загрузка CRM данных...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h2 className="crm-title">CRM проекта</h2>
          <p className="crm-subtitle">Все заявки и контакты в одном месте</p>
        </div>
        <div className="crm-stats">
          <div className="crm-stat">
            <span className="crm-stat-value">{crmData?.total_bookings || 0}</span>
            <span className="crm-stat-label">Записей</span>
          </div>
          <div className="crm-stat">
            <span className="crm-stat-value">{crmData?.total_contacts || 0}</span>
            <span className="crm-stat-label">Контактов</span>
          </div>
        </div>
      </div>

      <div className="crm-tabs">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              className={`crm-tab ${activeTab === tab.id ? 'crm-tab--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      <div className="crm-content">
        {activeTab === 'bookings' && renderBookingsTab()}
        {activeTab === 'contacts' && renderContactsTab()}
        {activeTab === 'leads' && renderLeadsTab()}
      </div>
    </div>
  );
};

export default ProjectCRMPage;
