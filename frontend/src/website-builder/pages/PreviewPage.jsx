/**
 * Preview Page
 * Preview mode for website with device switcher and hot reload
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import axios from 'axios';
import WebsiteRenderer from '../components/WebsiteRenderer';
import AgentWidget from '../components/AgentWidget';
import QuickContactButtons from '../components/QuickContactButtons';
import DeviceSwitcher, { DEVICES } from '../components/DeviceSwitcher';
import { WebsiteAgentProvider } from '../context/WebsiteAgentContext';
import { NAVIGATION_ROUTES, API_ROUTES } from '../../config/constants';
import { ENV_CONFIG } from '../../config/environment';
import { toRendererStyles } from '../utils/styleUtils';
import { PreviewMetaTags } from '../components/WebsiteMetaTags';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.TOKEN;

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
      const token = localStorage.getItem(TOKEN_KEY);
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/websites/${websiteId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Merge blocks with the schema for rendering
      const website = response.data;
      let agent = null;
      if (website.agent_id) {
        try {
          const embed = website.status === 'published' ? 'true' : 'false';
          const agentRes = await axios.get(
            `${API_BASE_URL}${API_ROUTES.AGENT_PUBLIC_DATA(website.agent_id)}?embed=${embed}`,
            { headers: token ? { Authorization: `Bearer ${token}` } : {} }
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

  // Hot reload every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchSchema();
    }, 5000);

    return () => clearInterval(interval);
  }, [websiteId]);

  // Handle publish/unpublish
  const handlePublish = async () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/publish`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchSchema();
    } catch (err) {
      alert('Failed to publish: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUnpublish = async () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/unpublish`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchSchema();
    } catch (err) {
      alert('Failed to unpublish: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleOpenPublic = () => {
    if (schema?.slug) {
      window.open(`/w/${schema.slug}`, '_blank');
    }
  };

  const handleEdit = () => {
    navigate(NAVIGATION_ROUTES.WEBSITE_EDITOR(websiteId));
  };

  // Get device dimensions
  const deviceStyle = {
    width: DEVICES[currentDevice].width,
    height: DEVICES[currentDevice].height,
    maxWidth: '100%',
    margin: '0 auto',
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка превью...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold mb-2 text-gray-800">Ошибка загрузки</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={fetchSchema}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }

  return (
    <HelmetProvider>
      <PreviewMetaTags title={schema?.title} description="Preview mode" />
      <div className="min-h-screen bg-gray-100">
        {/* Preview Toolbar */}
        <div className="sticky top-0 z-50 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left: Back & Info */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate(-1)}
                className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                title="Назад"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>

              <div className="hidden sm:block">
                <h1 className="text-lg font-semibold text-gray-800 dark:text-white">
                  {schema?.title || 'Превью сайта'}
                </h1>
                <p className="text-xs text-gray-500">
                  {schema?.status === 'published' ? (
                    <span className="inline-flex items-center gap-1 text-green-600">
                      <span className="w-2 h-2 rounded-full bg-green-500"></span>
                      Опубликован
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-gray-500">
                      <span className="w-2 h-2 rounded-full bg-gray-400"></span>
                      Черновик
                    </span>
                  )}
                  {lastUpdated && ` • Обновлено: ${lastUpdated.toLocaleTimeString()}`}
                </p>
              </div>
            </div>

            {/* Center: Device Switcher */}
            <div className="flex-1 flex justify-center">
              <DeviceSwitcher
                currentDevice={currentDevice}
                onDeviceChange={setCurrentDevice}
              />
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleEdit}
                className="hidden sm:flex items-center gap-2 px-4 py-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                <span className="text-sm font-medium">Редактировать</span>
              </button>

              {schema?.status === 'published' ? (
                <button
                  onClick={handleUnpublish}
                  className="px-4 py-2 text-sm font-medium text-yellow-600 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition-colors"
                >
                  Снять с публикации
                </button>
              ) : (
                <button
                  onClick={handlePublish}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-500 hover:bg-green-600 rounded-lg transition-colors"
                >
                  Опубликовать
                </button>
              )}

              {schema?.status === 'published' && (
                <button
                  onClick={handleOpenPublic}
                  className="hidden md:flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg transition-colors"
                >
                  <span>Открыть сайт</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Preview Container */}
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          {/* Device Frame */}
          <div
            className={`
              relative mx-auto transition-all duration-300 ease-in-out
              ${currentDevice !== 'desktop' ? 'border-x border-gray-300' : ''}
            `}
            style={deviceStyle}
          >
            {/* Device Header (for mobile/tablet simulation) */}
            {currentDevice !== 'desktop' && (
              <div className="bg-gray-800 text-white text-center py-2 text-xs font-medium">
                {DEVICES[currentDevice].label} Preview ({DEVICES[currentDevice].width})
              </div>
            )}

            {/* Website Content */}
            <div className="bg-white">
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

            {/* Hot Reload Indicator */}
            <div className="absolute top-4 right-4 z-50">
              <div
                className="px-3 py-1 rounded-full text-xs font-medium bg-green-500 text-white shadow-md animate-pulse"
                title="Auto-refresh enabled (5s)"
              >
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Live
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Dimensions Info */}
        <div className="mt-4 text-center text-sm text-gray-500">
          {currentDevice === 'desktop' ? (
            <span>100% (Desktop)</span>
          ) : (
            <span>
              {DEVICES[currentDevice].width} × 100% — {DEVICES[currentDevice].label}
            </span>
          )}
        </div>
      </div>
    </div>
    </HelmetProvider>
  );
};

export default PreviewPage;
