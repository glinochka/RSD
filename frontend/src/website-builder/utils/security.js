/**
 * Security utilities for Website Builder
 * HTML/CSS sanitization, XSS prevention, input validation
 */
import DOMPurify from 'dompurify';

// Allowed HTML tags for rich text editing
const ALLOWED_TAGS = [
  'p', 'br', 'span', 'div',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'strong', 'b', 'em', 'i', 'u', 'strike', 'del', 's',
  'a', 'img',
  'ul', 'ol', 'li',
  'blockquote', 'code', 'pre', 'hr',
  'table', 'thead', 'tbody', 'tr', 'td', 'th',
];

// Allowed attributes
const ALLOWED_ATTR = [
  'class', 'id', 'style',
  'href', 'title', 'target', 'rel',
  'src', 'alt', 'width', 'height', 'loading',
  'border', 'cellpadding', 'cellspacing',
];

// Allowed CSS properties (inline styles)
const ALLOWED_CSS_PROPERTIES = [
  'color', 'font-size', 'font-family', 'font-weight', 'font-style',
  'text-align', 'text-decoration', 'text-transform', 'line-height',
  'letter-spacing', 'word-spacing',
  'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'background', 'background-color',
  'border', 'border-radius', 'border-collapse',
  'width', 'height', 'max-width', 'max-height', 'min-width', 'min-height',
  'display', 'float', 'clear', 'position',
  'flex', 'flex-direction', 'justify-content', 'align-items',
  'grid', 'grid-template-columns', 'grid-template-rows',
  'gap', 'column-gap', 'row-gap',
  'cursor', 'pointer-events', 'user-select',
];

// XSS dangerous patterns
const DANGEROUS_PATTERNS = [
  /<script[^>]*>/gi,
  /<\/script>/gi,
  /javascript:/gi,
  /on\w+\s*=/gi, // onclick, onload, onerror, etc.
  /<iframe[^>]*>/gi,
  /<object[^>]*>/gi,
  /<embed[^>]*>/gi,
  /<applet[^>]*>/gi,
  /data:text\/html/gi,
];

/**
 * Configure DOMPurify instance
 */
const purifyConfig = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  ALLOW_DATA_ATTR: false,
  SANITIZE_DOM: true,
  // Hook to sanitize inline styles
  KEEP_CONTENT: true,
  // Remove any event handlers
  FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout', 'onfocus', 'onblur'],
  FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'applet', 'form'],
  // Allow CSS in style attributes but we'll validate separately
  ALLOWED_ATTR: [...ALLOWED_ATTR, 'style'],
};

/**
 * Sanitize HTML content
 * @param {string} dirty - Raw HTML content
 * @param {boolean} isBlockContent - Whether this is block-level content (allows more tags)
 * @returns {string} Sanitized HTML
 */
export function sanitizeHTML(dirty, isBlockContent = false) {
  if (!dirty || typeof dirty !== 'string') {
    return '';
  }

  const config = isBlockContent
    ? { ...purifyConfig }
    : { ...purifyConfig, ALLOWED_TAGS: ['span', 'b', 'i', 'u', 'em', 'strong', 'br', 'a'] };

  // Clean with DOMPurify
  let clean = DOMPurify.sanitize(dirty, config);

  // Additional manual checks for edge cases
  clean = additionalSanitization(clean);

  return clean;
}

/**
 * Additional sanitization for edge cases
 */
function additionalSanitization(html) {
  if (!html) return '';

  let clean = html;

  // Remove event handlers DOMPurify might have missed
  clean = clean.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '');
  clean = clean.replace(/\s+on\w+\s*=\s*[^\s>]+/gi, '');

  // Remove javascript: URLs
  clean = clean.replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"');
  clean = clean.replace(/src\s*=\s*["']javascript:[^"']*["']/gi, '');

  // Remove vbscript:
  clean = clean.replace(/href\s*=\s*["']vbscript:[^"']*["']/gi, 'href="#"');

  // Remove data:text/html
  clean = clean.replace(/href\s*=\s*["']data:text\/html[^"']*["']/gi, 'href="#"');

  // Remove expression() (IE CSS)
  clean = clean.replace(/expression\s*\([^)]*\)/gi, '');

  return clean;
}

/**
 * Sanitize CSS content
 * @param {string} css - Raw CSS content
 * @returns {string} Sanitized CSS
 */
export function sanitizeCSS(css) {
  if (!css || typeof css !== 'string') {
    return '';
  }

  let clean = css;

  // Remove CSS comments
  clean = clean.replace(/\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\//g, '');

  // Remove @import rules
  clean = clean.replace(/@import[^;]*;/gi, '');

  // Remove @keyframes, @font-face, @charset, @namespace
  clean = clean.replace(/@(?:keyframes|font-face|charset|namespace)[^{]*\{[^}]*\}/gi, '');

  // Remove CSS expressions (IE)
  clean = clean.replace(/expression\s*\([^)]*\)/gi, '');

  // Remove behavior (IE HTC)
  clean = clean.replace(/behavior\s*:[^;}]*/gi, '');

  // Remove -moz-binding
  clean = clean.replace(/-moz-binding\s*:[^;}]*/gi, '');

  // Remove binding
  clean = clean.replace(/binding\s*:[^;}]*/gi, '');

  // Remove JavaScript URLs in content property
  clean = clean.replace(/content\s*:\s*["']javascript:/gi, 'content:"');

  return clean.trim();
}

/**
 * Sanitize URL to prevent XSS
 * @param {string} url - URL to sanitize
 * @returns {string|null} Sanitized URL or null if dangerous
 */
export function sanitizeURL(url) {
  if (!url || typeof url !== 'string') {
    return null;
  }

  const trimmed = url.trim();
  const lower = trimmed.toLowerCase();

  // Block dangerous schemes
  const dangerousSchemes = [
    'javascript:',
    'vbscript:',
    'data:text/html',
    'data:application/x-javascript',
    'file:',
    'about:',
  ];

  for (const scheme of dangerousSchemes) {
    if (lower.startsWith(scheme)) {
      return null;
    }
  }

  // Block HTML entities that could decode to dangerous content
  if (/&#[x0-9]*;/i.test(trimmed) && /javascript/i.test(trimmed.replace(/&[#x0-9]*;/gi, ''))) {
    return null;
  }

  // Allow relative URLs and standard protocols
  const allowedProtocols = ['http:', 'https:', 'mailto:', 'tel:'];
  const hasProtocol = /^[a-z][a-z0-9+.-]*:/i.test(trimmed);

  if (hasProtocol) {
    const isAllowed = allowedProtocols.some(p => lower.startsWith(p));
    if (!isAllowed) {
      return null;
    }
  }

  return trimmed;
}

/**
 * Check if content contains suspicious patterns
 * @param {string} content - Content to check
 * @returns {{safe: boolean, issues: string[]}}
 */
export function checkSuspiciousContent(content) {
  if (!content || typeof content !== 'string') {
    return { safe: true, issues: [] };
  }

  const issues = [];

  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.test(content)) {
      issues.push(`Potentially dangerous pattern detected: ${pattern.source}`);
    }
  }

  // Check for HTML entities trying to hide malicious content
  if (/&#x?0{0,8}[0-9a-f]+;/gi.test(content)) {
    const decoded = content.replace(/&#x?0{0,8}([0-9a-f]+);/gi, (match, hex) => {
      return String.fromCharCode(parseInt(hex, hex.length > 2 ? 16 : 10));
    });
    if (/<script/i.test(decoded)) {
      issues.push('Encoded script tag detected');
    }
  }

  return {
    safe: issues.length === 0,
    issues,
  };
}

/**
 * Validate and sanitize block content
 * @param {object} content - Block content object
 * @returns {{valid: boolean, sanitized: object, issues: string[]}}
 */
export function validateAndSanitizeBlockContent(content) {
  const issues = [];

  function sanitizeValue(value, path = '') {
    if (typeof value === 'string') {
      // Check for suspicious patterns
      const check = checkSuspiciousContent(value);
      if (!check.safe) {
        issues.push(...check.issues.map(i => `${i} at ${path}`));
      }

      // Sanitize HTML content
      if (/<[a-z][\s\S]*>/i.test(value)) {
        return sanitizeHTML(value, true);
      }

      return value;
    }

    if (Array.isArray(value)) {
      return value.map((item, index) => sanitizeValue(item, `${path}[${index}]`));
    }

    if (value && typeof value === 'object') {
      const sanitized = {};
      for (const [key, val] of Object.entries(value)) {
        sanitized[key] = sanitizeValue(val, path ? `${path}.${key}` : key);
      }
      return sanitized;
    }

    return value;
  }

  const sanitized = sanitizeValue(content);

  return {
    valid: issues.length === 0,
    sanitized,
    issues,
  };
}

/**
 * Generate scoped CSS class name for website
 * @param {number} websiteId - Website ID
 * @param {string} originalClass - Original class name
 * @returns {string} Scoped class name
 */
export function generateScopedClass(websiteId, originalClass) {
  // Simple hash function
  let hash = 0;
  const str = `${websiteId}:${originalClass}`;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  const hashStr = Math.abs(hash).toString(36).slice(0, 6);
  return `wb-${websiteId}-${hashStr}`;
}

/**
 * Add scope wrapper to CSS selectors
 * @param {string} css - CSS content
 * @param {string} scopeClass - Scope class to add
 * @returns {string} Scoped CSS
 */
export function scopeCSS(css, scopeClass) {
  if (!css || !scopeClass) return css;

  // Simple regex-based scoping
  // This is a basic implementation - for production, use a proper CSS parser

  // Remove comments
  let scoped = css.replace(/\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\//g, '');

  // Handle @media and other at-rules
  scoped = scoped.replace(
    /@(media|supports|container)[^{]*\{/gi,
    (match) => `${match}${scopeClass} `,
  );

  // Scope regular selectors
  // This regex finds selector groups before { and adds scope
  scoped = scoped.replace(
    /([^{}@]+)\{/g,
    (match, selector) => {
      const trimmed = selector.trim();
      if (!trimmed) return match;

      // Don't scope :root, :host, @keyframes, etc.
      if (/^:(root|host)\b/.test(trimmed) || /^@/.test(trimmed)) {
        return match;
      }

      // Split by comma for multiple selectors
      const selectors = trimmed.split(',').map(s => {
        const t = s.trim();
        if (!t) return '';

        // Universal selector
        if (t === '*') {
          return `.${scopeClass} *`;
        }

        // Regular selector - add scope
        // Handle combinators by only scoping the first part
        const combinators = ['>', '+', '~'];
        const parts = t.split(/(\s*[>+~]\s*|\s+)/);
        if (parts[0] && !parts[0].startsWith('.')) {
          parts[0] = `.${scopeClass} ${parts[0]}`;
        } else if (parts[0]) {
          parts[0] = `.${scopeClass} ${parts[0]}`;
        }
        return parts.join('');
      });

      return `${selectors.join(', ')} {`;
    }
  );

  return scoped;
}

/**
 * Create sandbox configuration for iframe
 * @param {boolean} allowScripts - Whether to allow scripts
 * @returns {string} Sandbox attribute value
 */
export function getSandboxConfig(allowScripts = true) {
  const permissions = [
    'allow-same-origin',
    allowScripts ? 'allow-scripts' : '',
    'allow-popups',
    'allow-popups-to-escape-sandbox',
    'allow-forms',
  ].filter(Boolean);

  return permissions.join(' ');
}

/**
 * Content Security Policy for preview iframe
 * @returns {string} CSP for iframe
 */
export function getPreviewCSP() {
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "frame-src 'none'",
    "object-src 'none'",
    "base-uri 'self'",
  ].join('; ');
}

// Default export
export default {
  sanitizeHTML,
  sanitizeCSS,
  sanitizeURL,
  checkSuspiciousContent,
  validateAndSanitizeBlockContent,
  generateScopedClass,
  scopeCSS,
  getSandboxConfig,
  getPreviewCSP,
};
