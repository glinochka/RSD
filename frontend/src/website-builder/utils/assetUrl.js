const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

/**
 * Resolve website asset paths (/assets/websites/...) to a fetchable URL.
 * Assets are served by the API; when the SPA and API differ in origin, prefix API base.
 */
export function resolveWebsiteAssetUrl(assetPath) {
  if (!assetPath) return null;
  if (assetPath.startsWith('http://') || assetPath.startsWith('https://')) {
    return assetPath;
  }

  const normalized = assetPath.startsWith('/') ? assetPath : `/${assetPath}`;

  if (API_BASE_URL) {
    return `${API_BASE_URL}${normalized}`;
  }

  if (typeof window !== 'undefined') {
    return `${window.location.origin}${normalized}`;
  }

  return normalized;
}
