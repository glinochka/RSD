/**
 * Project Website Page
 * Website management dashboard for project with card layout.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import { NAVIGATION_ROUTES } from '../../config/constants';
import projectService from '../../services/projectService';
import '../../styles/projectWebsitePage.css';

// Icons
const GlobeIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const LayoutIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 9h18" />
    <path d="M9 21V9" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
);

const PlusIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const SpinnerIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spinner-animation">
    <line x1="12" y1="2" x2="12" y2="6" />
    <line x1="12" y1="18" x2="12" y2="22" />
    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
    <line x1="2" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="22" y2="12" />
    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
  </svg>
);

const getStatusLabel = (status) => {
  const labels = {
    draft: 'Черновик',
    published: 'Опубликован',
    archived: 'В архиве',
  };
  return labels[status] || status;
};

const getGenerationStatusLabel = (status) => {
  const labels = {
    idle: 'Ожидание',
    queued: 'В очереди',
    generating: 'Генерация...',
    completed: 'Готово',
    failed: 'Ошибка',
  };
  return labels[status] || status;
};

const ProjectWebsitePage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();

  const [websites, setWebsites] = useState([]);
  const [canCreate, setCanCreate] = useState(false);
  const [max, setMax] = useState(3);
  const [isLoading, setIsLoading] = useState(true);

  const createWebsiteUrl = `${NAVIGATION_ROUTES.WEBSITE_CREATE}?mode=ai&project_id=${projectId}`;

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const websitesData = await projectService
        .getProjectWebsites(projectId)
        .catch(() => ({ items: [], can_create: false, max: 3 }));
      setWebsites(websitesData.items || []);
      setCanCreate(websitesData.can_create !== false);
      setMax(websitesData.max || 3);
    } catch (error) {
      console.error('Failed to load websites:', error);
      showError('Не удалось загрузить сайты');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, showError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (isLoading) {
    return (
      <div className="project-website-page project-website-page--loading">
        <div className="website-loading">
          <div className="spinner" />
          <p>Загрузка данных сайта...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-website-page">
      <div className="website-header">
        <div>
          <h2 className="website-title">Сайты</h2>
          <p className="website-subtitle">
            {websites.length} из {max} лендингов
          </p>
        </div>
      </div>

      <div className="website-cards-grid">
        {websites.map((website) => (
          <div key={website.id} className="website-card">
            <div className="website-card-preview">
              <div className="website-card-icon">
                <GlobeIcon />
              </div>
              <div className="website-card-info">
                <h3 className="website-card-title">{website.title || 'Сайт проекта'}</h3>
                <span className={`website-card-status website-card-status--${website.status}`}>
                  {getStatusLabel(website.status)}
                </span>
                {website.generation_status && website.generation_status !== 'idle' && (
                  <span className={`website-card-gen-status website-card-gen-status--${website.generation_status}`}>
                    {website.generation_status === 'generating' && <SpinnerIcon />}
                    {getGenerationStatusLabel(website.generation_status)}
                  </span>
                )}
              </div>
            </div>

            <div className="website-card-meta">
              {website.url ? (
                <code className="website-card-url">{website.url}</code>
              ) : (
                <span className="website-card-url-not-set">URL не назначен</span>
              )}
            </div>

            <div className="website-card-actions">
              <Link
                to={NAVIGATION_ROUTES.WEBSITE_EDITOR(website.id)}
                className="website-card-btn website-card-btn--primary"
                title="Конструктор"
              >
                <LayoutIcon />
                <span>Конструктор</span>
              </Link>
              {website.url ? (
                <a
                  href={website.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="website-card-btn"
                  title="Открыть сайт"
                >
                  <ExternalLinkIcon />
                  <span>Перейти</span>
                </a>
              ) : (
                <button type="button" className="website-card-btn" disabled>
                  <ExternalLinkIcon />
                  <span>Перейти</span>
                </button>
              )}
            </div>
          </div>
        ))}

        {canCreate && (
          <Link to={createWebsiteUrl} className="website-card website-card--new">
            <div className="website-new-card-inner">
              <div className="website-new-card-icon">
                <PlusIcon />
              </div>
              <span className="website-new-card-label">Новый сайт</span>
            </div>
          </Link>
        )}
      </div>

      {websites.length === 0 && !canCreate && (
        <div className="website-empty">
          <div className="website-empty-icon">
            <GlobeIcon />
          </div>
          <h3 className="website-empty-title">Сайтов еще нет</h3>
          <p className="website-empty-description">
            Для проекта достигнут лимит сайтов. Удалите существующий, чтобы создать новый.
          </p>
        </div>
      )}
    </div>
  );
};

export default ProjectWebsitePage;
