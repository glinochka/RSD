/**
 * FullpageRenderer Component
 * Renders AI-generated HTML in a sandboxed iframe with Tailwind CSS loaded.
 * This is the core renderer for the new AI-coder website generation approach.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { LANDING_INTERACTIVITY_RUNTIME, LANDING_FORM_RUNTIME } from '../utils/landingInteractivity';

const TAILWIND_CDN = 'https://cdn.tailwindcss.com';

const INTER_FONT_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
`;

function buildFullDocument(html, title = 'Website', faviconUrl = null, landingConfig = null) {
  const faviconTag = faviconUrl
    ? `<link rel="icon" type="image/x-icon" href="${faviconUrl}">`
    : '';
  const hasBackendMenuRuntime = html.includes('data-rsd-landing-runtime');
  const hasFormRuntime = html.includes('data-rsd-form-runtime');
  const formsEnabled = Boolean(landingConfig?.agentId);

  const menuRuntimeScript = !hasBackendMenuRuntime
    ? `<script data-rsd-landing-runtime="1">${LANDING_INTERACTIVITY_RUNTIME}</script>`
    : '';
  // Backend injects menu/carousel only — always add form handler at render time.
  const formRuntimeScript =
    formsEnabled && !hasFormRuntime && hasBackendMenuRuntime
      ? `<script data-rsd-form-runtime="1">${LANDING_FORM_RUNTIME}</script>`
      : '';
  const landingConfigScript = landingConfig?.agentId
    ? `<script>window.__RSD_LANDING__=${JSON.stringify(landingConfig)};</script>`
    : '';

  return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title || 'Website'}</title>
  ${faviconTag}
  <script src="${TAILWIND_CDN}"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
          },
        },
      },
    }
  </script>
  <style>
    ${INTER_FONT_CSS}
    *, *::before, *::after { box-sizing: border-box; }
    html {
      scroll-behavior: smooth;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    body {
      margin: 0;
      padding: 0;
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      min-height: 100vh;
    }
    img { max-width: 100%; height: auto; }
    a { text-decoration: none; }
    /* Decorative AI chat bubbles — real widget is injected by the platform */
    [class*="chat-widget"], [class*="live-chat"], [class*="chat-bubble"],
    [id*="chat-widget"], [id*="live-chat"] { display: none !important; }
  </style>
  ${landingConfigScript}
</head>
<body>
  ${html}
  ${menuRuntimeScript}
  ${formRuntimeScript}
</body>
</html>`;
}

const FullpageRenderer = ({
  htmlContent,
  websiteId,
  title,
  faviconUrl = null,
  agentId = null,
  apiBase = null,
  formsEnabled = true,
  editMode = false,
  previewMode = false,
  className = '',
}) => {
  const iframeRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [iframeHeight, setIframeHeight] = useState('100vh');

  const updateIframeContent = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe || !htmlContent) return;

    setIsLoading(true);

    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (doc) {
        const landingConfig =
          formsEnabled && agentId
            ? {
                agentId,
                apiBase:
                  apiBase ||
                  (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') ||
                  (typeof window !== 'undefined' ? window.location.origin : ''),
              }
            : null;
        const fullDoc = buildFullDocument(htmlContent, title, faviconUrl, landingConfig);
        doc.open();
        doc.write(fullDoc);
        doc.close();

        const adjustHeight = () => {
          try {
            const body = doc.body;
            if (body) {
              const height = Math.max(body.scrollHeight, body.offsetHeight);
              if (height > 100) {
                setIframeHeight(`${height}px`);
              }
            }
          } catch (e) {
            // Cross-origin safety
          }
        };

        setTimeout(() => { setIsLoading(false); adjustHeight(); }, 300);
        setTimeout(adjustHeight, 1000);
        setTimeout(adjustHeight, 2500);
      }
    } catch (error) {
      console.error('FullpageRenderer: failed to render', error);
      setIsLoading(false);
    }
  }, [htmlContent, title, faviconUrl, agentId, apiBase, formsEnabled]);

  useEffect(() => {
    updateIframeContent();
  }, [updateIframeContent]);

  if (!htmlContent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-400">Сайт ещё не сгенерирован</p>
      </div>
    );
  }

  return (
    <div
      className={`fullpage-renderer ${className}`}
      style={{ position: 'relative', width: '100%', minHeight: '100vh' }}
    >
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#f9fafb',
            zIndex: 10,
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                width: 40,
                height: 40,
                border: '3px solid #e5e7eb',
                borderTopColor: '#3b82f6',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
                margin: '0 auto 12px',
              }}
            />
            <p style={{ color: '#6b7280', fontSize: 14 }}>Загрузка сайта...</p>
          </div>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      <iframe
        ref={iframeRef}
        title={`website-${websiteId || 'preview'}`}
        sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
        allow="autoplay; encrypted-media; fullscreen"
        style={{
          width: '100%',
          height: previewMode ? iframeHeight : '100vh',
          minHeight: previewMode ? '600px' : '100vh',
          border: 'none',
          display: 'block',
          opacity: isLoading ? 0 : 1,
          transition: 'opacity 0.3s ease',
        }}
        allow=""
        allowFullScreen={false}
      />
    </div>
  );
};

FullpageRenderer.propTypes = {
  htmlContent: PropTypes.string,
  websiteId: PropTypes.number,
  title: PropTypes.string,
  faviconUrl: PropTypes.string,
  agentId: PropTypes.number,
  apiBase: PropTypes.string,
  formsEnabled: PropTypes.bool,
  editMode: PropTypes.bool,
  previewMode: PropTypes.bool,
  className: PropTypes.string,
};

export default FullpageRenderer;
