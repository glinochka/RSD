/**
 * Preview Page
 * Preview mode for website with device switcher
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { ArrowLeft, Monitor, Smartphone, Tablet, ExternalLink, Edit2 } from 'lucide-react';
import axios from 'axios';
import WebsiteRenderer from '../components/WebsiteRenderer';
import AgentWidget from '../components/AgentWidget';
import QuickContactButtons from '../components/QuickContactButtons';
import { DEVICES } from '../components/DeviceSwitcher';
import { WebsiteAgentProvider } from '../context/WebsiteAgentContext';
import { NAVIGATION_ROUTES, API_ROUTES } from '../../config/constants';
import { getAuthHeaders } from '../../utils/authToken';
import { fetchWebsiteDetail } from '../utils/api';
import { toRendererStyles } from '../utils/styleUtils';
import { PreviewMetaTags } from '../components/WebsiteMetaTags';
import ProtectedRoute from '../../components/ProtectedRoute';
import '../styles/preview.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Device icons mapping
const DeviceIcon = ({ device }) => {
  switch (device) {
    case 'mobile':
      return <Smartphone className="w-4 h-4" />;
    case 'tablet':
      return <Tablet className="w-4 h-4" />;
    case 'desktop':
    default:
      return <Monitor className="w-4 h-4" />;
  }
};

const PreviewPage = () => {
  const { websiteId } = useParams();
  const navigate = useNavigate();

  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentDevice, setCurrentDevice] = useState('desktop');
  const [lastUpdated, setLastUpdated] = useState(null);

  // Fetch website schema
  const fetchSchema = async () => {
    try {
      const website = await fetchWebsiteDetail(websiteId);
      let agent = null;
      if (website.agent_id) {
        try {
          const embed = website.status === 'published' ? 'true' : 'false';
          const agentRes = await axios.get(
            `${API_BASE_URL}${API_ROUTES.AGENT_PUBLIC_DATA(website.agent_id)}?embed=${embed}`,
            { headers: getAuthHeaders() }
          );
          agent = agentRes.data;
        } catch (agentErr) {
          console.warn('Agent public data unavailable:', agentErr);
        }
      }
      setSchema({
        ...website,
        styles: toRendererStyles(website.custom_styles || {}),
        blocks: website.blocks || [],
        agent,
        agent_id: website.agent_id,
      });
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch website:', err);
      setError(err.response?.data?.detail || 'Failed to load website preview');
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchSchema();
  }, [websiteId]);

  // Handle publish/unpublish
  const handlePublish = async () => {
    try {
      await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/publish`,
        {},
        { headers: getAuthHeaders() }
      );
      fetchSchema();
    } catch (err) {
      alert('Failed to publish: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUnpublish = async () => {
    try {
      await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/unpublish`,
        {},
        { headers: getAuthHeaders() }
      );
      fetchSchema();
    } catch (err) {
      alert('Failed to unpublish: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleOpenPublic = () => {
    if (schema?.slug) {
      window.open(NAVIGATION_ROUTES.WEBSITE_PUBLIC(schema.slug), '_blank', 'noopener,noreferrer');
    }
  };

  const handleEdit = () => {
    navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(websiteId));
  };

  // Get device dimensions
  const deviceStyle = {
    width: DEVICES[currentDevice].width,
    maxWidth: '100%',
  };

  if (loading) {
    return (
      <div className="preview-loading">
        <div className="preview-loading-spinner"></div>
        <p className="preview-loading-text">Загрузка превью...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="preview-error">
        <div className="preview-error-card">
          <svg className="preview-error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h2 className="preview-error-title">Ошибка загрузки</h2>
          <p className="preview-error-message">{error}</p>
          <button onClick={fetchSchema} className="preview-error-btn">
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }

  return (
    <HelmetProvider>
      <PreviewMetaTags title={schema?.title} description="Preview mode" />
      <div className="preview-page">
        {/* Toolbar */}
        <div className="preview-toolbar">
          <div className="preview-toolbar-content">
            {/* Left: Back & Info */}
            <div className="preview-info">
              <button
                onClick={() => navigate(-1)}
                className="preview-back-btn"
                title="Назад"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>

              <div className="preview-title-group">
                <h1 className="preview-title">{schema?.title || 'Превью сайта'}</h1>
                <div className="preview-status">
                  <span
                    className={`preview-status-dot ${
                      schema?.status === 'published'
                        ? 'preview-status-dot--published'
                        : 'preview-status-dot--draft'
                    }`}
                  />
                  <span
                    className={
                      schema?.status === 'published'
                        ? 'preview-status-text--published'
                        : ''
                    }
                  >
                    {schema?.status === 'published' ? 'Опубликован' : 'Черновик'}
                  </span>
                  {lastUpdated && (
                    <span className="preview-updated">
                      • Обновлено: {lastUpdated.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Center: Device Switcher */}
            <div className="preview-device-switcher">
              {Object.entries(DEVICES).map(([key, { label }]) => (
                <button
                  key={key}
                  onClick={() => setCurrentDevice(key)}
                  className={`preview-device-btn ${
                    currentDevice === key ? 'preview-device-btn--active' : ''
                  }`}
                  title={label}
                >
                  <DeviceIcon device={key} />
                  <span>{label}</span>
                </button>
              ))}
            </div>

            {/* Right: Actions */}
            <div className="preview-actions">
              <button onClick={handleEdit} className="preview-action-btn">
                <Edit2 className="w-4 h-4" />
                <span className="hidden sm:inline">Редактировать</span>
              </button>

              {schema?.status === 'published' ? (
                <button
                  onClick={handleUnpublish}
                  className="preview-action-btn preview-action-btn--warning"
                >
                  <span>Снять с публикации</span>
                </button>
              ) : (
                <button
                  onClick={handlePublish}
                  className="preview-action-btn preview-action-btn--success"
                >
                  <span>Опубликовать</span>
                </button>
              )}

              {schema?.status === 'published' && (
                <button
                  onClick={handleOpenPublic}
                  className="preview-action-btn preview-action-btn--primary"
                >
                  <span className="hidden md:inline">Открыть сайт</span>
                  <ExternalLink className="w-4 h-4 md:hidden" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Preview Container */}
        <div className="preview-container">
          <div className="preview-frame-wrapper">
            {/* Device Frame */}
            <div
              className={`preview-device-frame preview-device-frame--${currentDevice}`}
              style={deviceStyle}
            >
              {/* Device Header (for mobile/tablet simulation) */}
              {currentDevice !== 'desktop' && (
                <div className="preview-device-header">
                  {DEVICES[currentDevice].label} • {DEVICES[currentDevice].width}
                </div>
              )}

              {/* Website Content */}
              <div className="preview-device-content">
                <WebsiteAgentProvider agent={schema?.agent} agentId={schema?.agent_id}>
                  <WebsiteRenderer
                    schema={schema}
                    previewMode={true}
                    templateStyles={schema?.styles}
                  />
                  <AgentWidget
                    apiKey={schema?.agent?.widget_api_key}
                    enabled={Boolean(schema?.agent?.widget_api_key)}
                  />
                  <QuickContactButtons
                    contacts={schema?.agent?.contacts}
                    primaryColor={schema?.styles?.primaryColor}
                  />
                </WebsiteAgentProvider>
              </div>
            </div>
          </div>

          {/* Dimensions indicator */}
          <div className="preview-dimensions">
            {currentDevice === 'desktop' ? (
              <span>Desktop • Адаптивная ширина</span>
            ) : (
              <span>
                {DEVICES[currentDevice].label} • {DEVICES[currentDevice].width}
              </span>
            )}
          </div>
        </div>
      </div>
    </HelmetProvider>
  );
};

const PreviewPageWithAuth = () => (
  <ProtectedRoute>
    <PreviewPage />
  </ProtectedRoute>
);

export default PreviewPageWithAuth;
