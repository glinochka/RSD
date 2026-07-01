/**
 * CreateChoiceModal Component
 * Modal for choosing what tool to create
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/create-choice-modal.css';

// Bot icon for AI Agent option
const BotIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" />
    <line x1="16" y1="16" x2="16" y2="16" />
  </svg>
);

// Briefcase icon for Project option
const BriefcaseIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

// Globe icon for Website option
const GlobeIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const CreateChoiceModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const modalRef = useRef(null);
  const closeButtonRef = useRef(null);
  const [createTarget, setCreateTarget] = useState(null);

  // Focus management and escape key handling
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    // Lock body scroll
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleEscape);

    // Focus close button initially
    setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 50);

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  // Handle click outside
  const handleBackdropClick = (e) => {
    if (e.target === modalRef.current) {
      onClose();
    }
  };

  useEffect(() => {
    if (!isOpen) {
      setCreateTarget(null);
    }
  }, [isOpen]);

  const handleCreateAgentManual = () => {
    onClose();
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  const handleCreateAgentAI = () => {
    onClose();
    navigate(NAVIGATION_ROUTES.CREATE_AGENT_AI);
  };

  const handleCreateProjectManual = () => {
    onClose();
    navigate(`${NAVIGATION_ROUTES.PROJECT_CREATE}?mode=manual`);
  };

  const handleCreateProjectAI = () => {
    onClose();
    navigate(`${NAVIGATION_ROUTES.PROJECT_CREATE}?mode=ai`);
  };

  const handleCreateWebsite = () => {
    onClose();
    navigate(`${NAVIGATION_ROUTES.PROJECTS_LIST}?create=website`);
  };

  if (!isOpen) return null;

  return (
    <div
      ref={modalRef}
      className="create-choice-modal-backdrop"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-choice-title"
    >
      <div className="create-choice-modal">
        <div className="create-choice-modal-header">
          <h2 id="create-choice-title" className="create-choice-modal-title">
            Новое решение
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="create-choice-modal-close"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </div>

        <div className="create-choice-modal-body">
          {createTarget ? (
            <div className="create-choice-options">
              <button
                type="button"
                className="create-choice-option"
                onClick={createTarget === 'agent' ? handleCreateAgentAI : handleCreateProjectAI}
              >
                <div className="create-choice-option-content">
                  <h3 className="create-choice-option-title">Создать с ИИ</h3>
                  <p className="create-choice-option-description">
                    {createTarget === 'agent'
                      ? 'Коротко описываете задачу, получаете готовый шаблон и промпт.'
                      : 'ИИ соберет проектный план: агенты, сайт и рекомендации по запуску.'}
                  </p>
                </div>
              </button>
              <button
                type="button"
                className="create-choice-option"
                onClick={createTarget === 'agent' ? handleCreateAgentManual : handleCreateProjectManual}
              >
                <div className="create-choice-option-content">
                  <h3 className="create-choice-option-title">Создать вручную</h3>
                  <p className="create-choice-option-description">
                    {createTarget === 'agent'
                      ? 'Пустой агент: полностью ручная настройка каналов, промпта и логики.'
                      : 'Пустой проект: добавляете сайт, агентов и базу знаний самостоятельно.'}
                  </p>
                </div>
              </button>
            </div>
          ) : (
            <div className="create-choice-options">
              <button
                type="button"
                className="create-choice-option create-choice-option--agent"
                onClick={() => setCreateTarget('agent')}
              >
                <div className="create-choice-option-icon">
                  <BotIcon />
                </div>
                <div className="create-choice-option-content">
                  <h3 className="create-choice-option-title">ИИ-агент</h3>
                  <p className="create-choice-option-description">
                    Один специализированный помощник: поддержка, продажи, администратор.
                  </p>
                </div>
              </button>

              <button
                type="button"
                className="create-choice-option create-choice-option--website"
                onClick={handleCreateWebsite}
              >
                <div className="create-choice-option-icon">
                  <GlobeIcon />
                </div>
                <div className="create-choice-option-content">
                  <h3 className="create-choice-option-title">Сайт</h3>
                  <p className="create-choice-option-description">
                    Лендинг или сайт компании с генерацией контента и публикацией.
                  </p>
                </div>
              </button>

              <button
                type="button"
                className="create-choice-option create-choice-option--project"
                onClick={() => setCreateTarget('project')}
              >
                <div className="create-choice-option-icon">
                  <BriefcaseIcon />
                </div>
                <div className="create-choice-option-content">
                  <h3 className="create-choice-option-title">Проект</h3>
                  <p className="create-choice-option-description">
                    Единое рабочее пространство: набор агентов, CRM, сайт и база знаний.
                  </p>
                </div>
              </button>
            </div>
          )}
        </div>

        <div className="create-choice-modal-footer">
          {createTarget ? (
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => setCreateTarget(null)}
            >
              Назад
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
            >
              Отмена
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CreateChoiceModal;
