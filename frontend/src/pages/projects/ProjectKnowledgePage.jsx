/**
 * Project Knowledge Page
 * Shared knowledge base for all project agents
 */

import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import projectService from '../../services/projectService';
import { validateFile } from '../../utils/validation';
import '../../styles/projectKnowledgePage.css';

// Icons
const FileIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const UploadIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const LinkIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
);

const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const SpinnerIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spinner-animation">
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

// Status helpers
const getStatusLabel = (status) => {
  const labels = {
    processing: 'Обработка...',
    ready: 'Готов',
    error: 'Ошибка',
  };
  return labels[status] || status;
};

const getStatusClass = (status) => {
  const classes = {
    processing: 'status--processing',
    ready: 'status--ready',
    error: 'status--error',
  };
  return classes[status] || '';
};

const ProjectKnowledgePage = () => {
  const { projectId } = useParams();
  const { showError, showSuccess } = useNotification();
  const fileInputRef = useRef(null);

  const [documents, setDocuments] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const [isAddingLink, setIsAddingLink] = useState(false);

  useEffect(() => {
    loadDocuments();
    loadRecommendations();
  }, [projectId]);

  const loadDocuments = async () => {
    try {
      setIsLoading(true);
      const data = await projectService.getProjectDocuments(projectId);
      setDocuments(data);
    } catch (error) {
      console.error('Failed to load documents:', error);
      showError('Не удалось загрузить документы');
    } finally {
      setIsLoading(false);
    }
  };

  const loadRecommendations = async () => {
    try {
      const project = await projectService.getProject(projectId);
      if (project.ai_plan_json?.knowledge_recommendations) {
        setRecommendations(project.ai_plan_json.knowledge_recommendations);
      }
    } catch (error) {
      console.error('Failed to load recommendations:', error);
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const validation = validateFile(file);
    if (!validation.isValid) {
      showError(validation.errors[0]);
      return;
    }

    try {
      setIsUploading(true);
      await projectService.uploadProjectDocument(projectId, file);
      showSuccess('Документ загружен и обрабатывается');
      await loadDocuments();
    } catch (error) {
      console.error('Failed to upload document:', error);
      showError(error.message || 'Не удалось загрузить документ');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleAddLink = async () => {
    if (!linkUrl.trim()) return;

    try {
      setIsAddingLink(true);
      await projectService.uploadProjectLink(projectId, linkUrl.trim());
      showSuccess('Ссылка добавлена и обрабатывается');
      setLinkUrl('');
      await loadDocuments();
    } catch (error) {
      console.error('Failed to add link:', error);
      showError(error.message || 'Не удалось добавить ссылку');
    } finally {
      setIsAddingLink(false);
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Удалить документ? Это действие нельзя отменить.')) {
      return;
    }

    try {
      await projectService.deleteProjectDocument(projectId, docId);
      showSuccess('Документ удален');
      await loadDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      showError('Не удалось удалить документ');
    }
  };

  const handleReindex = async (docId) => {
    try {
      await projectService.reindexProjectDocument(projectId, docId);
      showSuccess('Переиндексация запущена');
      await loadDocuments();
    } catch (error) {
      console.error('Failed to reindex document:', error);
      showError('Не удалось запустить переиндексацию');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="project-knowledge-page">
      <div className="project-knowledge-header">
        <div>
          <h2 className="project-knowledge-title">База знаний проекта</h2>
          <p className="project-knowledge-subtitle">
            Документы доступны всем агентам проекта
          </p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="project-knowledge-upload">
        <div className="upload-section">
          <input
            ref={fileInputRef}
            type="file"
            id="document-upload"
            accept=".pdf,.docx,.doc,.txt,.md"
            onChange={handleFileSelect}
            disabled={isUploading}
            style={{ display: 'none' }}
          />
          <label htmlFor="document-upload" className="upload-file-label">
            <button
              type="button"
              className="btn btn-black"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {isUploading ? (
                <>
                  <SpinnerIcon />
                  Загрузка...
                </>
              ) : (
                <>
                  <UploadIcon />
                  Загрузить файл
                </>
              )}
            </button>
            <span className="upload-hint">PDF, DOCX, TXT (макс. 10MB)</span>
          </label>
        </div>

        <div className="upload-divider">или</div>

        <div className="upload-link-section">
          <div className="link-input-group">
            <div className="link-input-icon">
              <LinkIcon />
            </div>
            <input
              type="url"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://example.com/document.pdf"
              disabled={isAddingLink}
            />
            <button
              type="button"
              className="btn btn-outline"
              onClick={handleAddLink}
              disabled={!linkUrl.trim() || isAddingLink}
            >
              {isAddingLink ? <SpinnerIcon /> : 'Добавить'}
            </button>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="project-knowledge-recommendations">
          <h3 className="recommendations-title">Рекомендуем загрузить</h3>
          <ul className="recommendations-list">
            {recommendations.map((rec, index) => (
              <li key={index} className="recommendation-item">
                <CheckIcon />
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Documents List */}
      <div className="project-knowledge-documents">
        <h3 className="documents-title">
          Документы
          <span className="documents-count">{documents.length}</span>
        </h3>

        {isLoading ? (
          <div className="documents-loading">
            <SpinnerIcon />
            <p>Загрузка документов...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="documents-empty">
            <div className="documents-empty-icon">
              <FileIcon />
            </div>
            <h4>Документов пока нет</h4>
            <p>Загрузите файлы или добавьте ссылки на документы</p>
          </div>
        ) : (
          <div className="documents-list">
            {documents.map((doc) => (
              <div key={doc.id} className="document-card">
                <div className="document-icon">
                  <FileIcon />
                </div>
                <div className="document-info">
                  <h4 className="document-name" title={doc.file_name}>
                    {doc.file_name}
                  </h4>
                  <p className="document-meta">
                    Загружен: {formatDate(doc.created_at)}
                  </p>
                </div>
                <div className={`document-status ${getStatusClass(doc.status)}`}>
                  {doc.status === 'processing' && <SpinnerIcon />}
                  {doc.status === 'ready' && <CheckIcon />}
                  <span>{getStatusLabel(doc.status)}</span>
                </div>
                <div className="document-actions">
                  <button
                    type="button"
                    className="document-action"
                    onClick={() => handleReindex(doc.id)}
                    title="Переиндексировать"
                    disabled={doc.status === 'processing'}
                  >
                    <RefreshIcon />
                  </button>
                  <button
                    type="button"
                    className="document-action document-action--delete"
                    onClick={() => handleDelete(doc.id)}
                    title="Удалить"
                  >
                    <TrashIcon />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectKnowledgePage;
