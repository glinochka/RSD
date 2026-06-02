/**
 * useWebsite Hook
 * Hook for fetching and managing website data
 */
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export function useWebsite(websiteId, slug = null, domain = null) {
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSchema = useCallback(async () => {
    if (!websiteId && !slug && !domain) {
      setError('Website ID, slug, or domain is required');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let endpoint;
      if (domain) {
        // Custom domain access
        endpoint = `${API_BASE_URL}/api/v1/websites/by-domain/${domain}/schema`;
      } else if (slug) {
        // Slug-based access (for /w/{slug} paths)
        endpoint = `${API_BASE_URL}/api/v1/websites/by-slug/${slug}/schema`;
      } else {
        // ID-based access (for preview/constructor)
        endpoint = `${API_BASE_URL}/api/v1/websites/${websiteId}/schema`;
      }

      const response = await axios.get(endpoint);
      setSchema(response.data);
    } catch (err) {
      console.error('Failed to fetch website schema:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load website');
    } finally {
      setLoading(false);
    }
  }, [websiteId, slug, domain]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  // Auto-refresh every 30 seconds in preview mode
  useEffect(() => {
    if (!schema) return;

    const interval = setInterval(() => {
      fetchSchema();
    }, 30000);

    return () => clearInterval(interval);
  }, [schema, fetchSchema]);

  return {
    schema,
    loading,
    error,
    refetch: fetchSchema,
  };
}

/**
 * Hook to detect current domain and load website automatically
 * For use with custom domain deployments
 */
export function useWebsiteByCurrentDomain() {
  const [detectedDomain, setDetectedDomain] = useState(null);

  useEffect(() => {
    // Detect current domain from window.location
    const host = window.location.host;
    // Skip localhost and known development domains
    const devHosts = ['localhost', '127.0.0.1', '0.0.0.0'];
    const isDev = devHosts.some(h => host.includes(h));

    if (!isDev && host) {
      setDetectedDomain(host);
    }
  }, []);

  // Use the main hook with detected domain
  const result = useWebsite(null, null, detectedDomain);

  return {
    ...result,
    detectedDomain,
  };
}

export function useWebsiteEditor(websiteId) {
  const [website, setWebsite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const fetchWebsite = useCallback(async () => {
    if (!websiteId) return;

    try {
      setLoading(true);
      const token = localStorage.getItem('accessToken');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/websites/${websiteId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setWebsite(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load website');
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  const updateWebsite = useCallback(async (updates) => {
    if (!websiteId) return;

    try {
      setSaving(true);
      const token = localStorage.getItem('accessToken');
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/websites/${websiteId}`,
        updates,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setWebsite(response.data);
      return response.data;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Failed to update website');
    } finally {
      setSaving(false);
    }
  }, [websiteId]);

  const publish = useCallback(async () => {
    if (!websiteId) return;

    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/publish`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setWebsite(response.data);
      return response.data;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Failed to publish website');
    }
  }, [websiteId]);

  const unpublish = useCallback(async () => {
    if (!websiteId) return;

    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/unpublish`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setWebsite(response.data);
      return response.data;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Failed to unpublish website');
    }
  }, [websiteId]);

  useEffect(() => {
    fetchWebsite();
  }, [fetchWebsite]);

  return {
    website,
    loading,
    saving,
    error,
    refetch: fetchWebsite,
    updateWebsite,
    publish,
    unpublish,
  };
}

export default useWebsite;
