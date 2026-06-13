/**
 * SecurePreview Component
 * Renders website content in an isolated iframe with sandbox
 * Provides security isolation between preview and parent window
 */
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { getSandboxConfig, getPreviewCSP, scopeCSS } from '../utils/security';

/**
 * Build isolated HTML document for iframe
 * @param {object} params
 * @returns {string} Complete HTML document
 */
function buildIsolatedDocument({
  html,
  css,
  websiteId,
  scripts = [],
  title = 'Preview',
}) {
  // Scope CSS for isolation
  const scopeClass = `site-${websiteId}`;
  const scopedCSS = scopeCSS(css, scopeClass);

  // CSP for the iframe
  const csp = getPreviewCSP();

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <title>${escapeHtml(title)}</title>
  <style>
    /* Reset for isolation */
    *, *::before, *::after {
      box-sizing: border-box;
    }
    html, body {
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    }
    body {
      min-height: 100vh;
    }
    
    /* Scoped styles */
    .${scopeClass} {
      display: block;
      font-family: inherit;
    }
    
    /* User-provided scoped CSS */
    ${scopedCSS}
  </style>
</head>
<body>
  <div class="${scopeClass}">
    ${html}
  </div>
  
  <!-- Scripts (if allowed) -->
  ${scripts.map(src => `<script src="${escapeHtml(src)}"></script>`).join('\n')}
  
  <!-- Isolation enforcement -->
  <script>
    // Disable dangerous APIs
    window.open = function() { 
      console.warn('window.open() is disabled in preview mode');
      return null;
    };
    
    // Allow form submissions but warn
    document.addEventListener('submit', function(e) {
      console.info('Form submission in preview mode');
    });
  </script>
</body>
</html>
  `.trim();
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * SecurePreview Component
 */
export function SecurePreview({
  websiteId,
  html,
  css = '',
  scripts = [],
  title = 'Preview',
  width = '100%',
  height = '100%',
  minHeight = '400px',
  className = '',
  onLoad,
  onError,
  allowScripts = true,
  resizable = false,
}) {
  const iframeRef = useRef(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [iframeHeight, setIframeHeight] = useState(minHeight);

  // Build document content
  const documentContent = buildIsolatedDocument({
    html,
    css,
    websiteId,
    scripts,
    title,
  });

  // Update iframe content
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    setIsLoading(true);
    setLoadError(null);

    try {
      // Write content to iframe
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (doc) {
        doc.open();
        doc.write(documentContent);
        doc.close();

        // Auto-adjust height
        if (!resizable) {
          const checkHeight = () => {
            try {
              const body = doc.body;
              const contentHeight = body?.scrollHeight || minHeight;
              setIframeHeight(Math.max(contentHeight + 50, parseInt(minHeight)));
            } catch (e) {
              // Cross-origin restriction
            }
          };

          // Check height after load
          setTimeout(checkHeight, 100);
          setTimeout(checkHeight, 500);
          setTimeout(checkHeight, 1000);
        }

        setIsLoading(false);
        onLoad?.();
      }
    } catch (error) {
      console.error('Failed to update preview:', error);
      setLoadError(error.message);
      setIsLoading(false);
      onError?.(error);
    }
  }, [documentContent, minHeight, resizable, onLoad, onError]);

  // Handle resize
  const handleResize = useCallback((delta) => {
    if (!resizable) return;

    const newHeight = Math.max(
      parseInt(minHeight),
      iframeRef.current?.offsetHeight + delta
    );
    setIframeHeight(newHeight);
  }, [resizable, minHeight]);

  const sandboxConfig = getSandboxConfig(allowScripts);

  return (
    <div className={`secure-preview-container ${className}`} style={{ position: 'relative' }}>
      {/* Loading indicator */}
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#f9fafb',
            zIndex: 10,
          }}
        >
          <div className="flex items-center gap-2 text-gray-500">
            <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
            <span className="text-sm">Loading preview...</span>
          </div>
        </div>
      )}

      {/* Error display */}
      {loadError && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            padding: '1rem',
            background: '#fee2e2',
            border: '1px solid #ef4444',
            color: '#b91c1c',
            fontSize: '0.875rem',
            zIndex: 20,
          }}
        >
          Preview error: {loadError}
        </div>
      )}

      {/* Isolated iframe */}
      <iframe
        ref={iframeRef}
        title={`preview-${websiteId}`}
        sandbox={sandboxConfig}
        style={{
          width,
          height: resizable ? iframeHeight : (height || iframeHeight),
          minHeight,
          border: '1px solid #e5e7eb',
          borderRadius: '0.5rem',
          background: 'white',
          ...(isLoading ? { opacity: 0 } : { opacity: 1 }),
        }}
        allow=""
        allowFullScreen={false}
        loading="lazy"
        importance="low"
      />

      {/* Resize handle */}
      {resizable && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '8px',
            cursor: 'ns-resize',
            background: 'transparent',
          }}
          onMouseDown={(e) => {
            const startY = e.clientY;
            const startHeight = iframeRef.current?.offsetHeight || parseInt(minHeight);

            const handleMouseMove = (moveEvent) => {
              const delta = moveEvent.clientY - startY;
              handleResize(delta);
            };

            const handleMouseUp = () => {
              document.removeEventListener('mousemove', handleMouseMove);
              document.removeEventListener('mouseup', handleMouseUp);
            };

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
          }}
        >
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '40px',
              height: '4px',
              background: '#d1d5db',
              borderRadius: '2px',
            }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * SecurePreviewWrapper - wraps content in security container
 * Use this when you need to render potentially unsafe content
 */
export function SecureContentWrapper({
  children,
  websiteId,
  className = '',
  style = {},
}) {
  const scopeClass = `site-${websiteId}`;

  return (
    <div
      className={`${scopeClass} ${className}`}
      style={{
        fontFamily: 'inherit',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export default SecurePreview;
