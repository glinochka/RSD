/**
 * Dynamic placeholder resolution for website content.
 */

const PLACEHOLDER_RE = /\{\{(\w+)\}\}/g;

export function buildPlaceholderVars(website = {}) {
  return {
    business_name: website.title || 'Мой бизнес',
    phone: website._placeholders?.phone || '',
    email: website._placeholders?.email || '',
    address: website._placeholders?.address || '',
  };
}

export function resolvePlaceholders(text, vars = {}) {
  if (!text || typeof text !== 'string') return text || '';
  return text.replace(PLACEHOLDER_RE, (_, key) => {
    const val = vars[key];
    return val != null && val !== '' ? val : `{{${key}}}`;
  });
}

export const PLACEHOLDER_HINTS = [
  { key: 'business_name', label: 'Название бизнеса' },
  { key: 'phone', label: 'Телефон' },
  { key: 'email', label: 'Email' },
  { key: 'address', label: 'Адрес' },
];
