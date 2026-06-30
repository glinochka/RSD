/**
 * CreateChoiceModal Component
 * Modal for choosing between creating an AI Agent or a Project
 */

import React, { useEffect, useRef } from 'react';
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

const CreateChoiceModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const modalRef = useRef(null);
  const closeButtonRef = useRef(null);

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

  const handleCreateAgent = () => {
    onClose();
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  };

  const handleCreateProject = () => {
    onClose();
    navigate(NAVIGATION_ROUTES.PROJECT_CREATE);
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
            Что вы хотите создать?
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
          <div className="create-choice-options">
            {/* AI Agent Option */}
            <button
              type="button"
              className="create-choice-option create-choice-option--agent"
              onClick={handleCreateAgent}
            >
              <div className="create-choice-option-icon">
                <BotIcon />
              </div>
              <div className="create-choice-option-content">
                <h3 className="create-choice-option-title">ИИ-агент</h3>
                <p className="create-choice-option-description">
                  Один специализированный помощник: поддержка, продажи, администратор.
                  Подключается к мессенджерам и сайту.
                </p>
              </div>
            </button>

            {/* Project Option */}
            <button
              type="button"
              className="create-choice-option create-choice-option--project"
              onClick={handleCreateProject}
            >
              <div className="create-choice-option-icon">
                <BriefcaseIcon />
              </div>
              <div className="create-choice-option-content">
                <h3 className="create-choice-option-title">Проект</h3>
                <p className="create-choice-option-description">
                  Цифровизация бизнеса целиком: набор агентов, CRM, сайт, база знаний и
                  дашборд в одном пространстве.
                </p>
              </div>
            </button>
          </div>
        </div>

        <div className="create-choice-modal-footer">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateChoiceModal;
