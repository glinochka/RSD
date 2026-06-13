/**
 * useWebsite Hook
 * Hook for fetching and managing website data
 */
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  fetchWebsiteDetail,
  updateWebsite as updateWebsiteApi,
  publishWebsite,
  unpublishWebsite,
} from '../utils/api';

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
        endpoint = `${API_BASE_URL}/api/v1/websites/by-domain/${domain}/schema`;
      } else if (slug) {
        endpoint = `${API_BASE_URL}/api/v1/websites/by-slug/${slug}/schema`;
      } else {
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

  return {
    schema,
    loading,
    error,
    refetch: fetchSchema,
  };
}

export function useWebsiteByCurrentDomain() {
  const [detectedDomain, setDetectedDomain] = useState(null);

  useEffect(() => {
    const host = window.location.host;
    const devHosts = ['localhost', '127.0.0.1', '0.0.0.0'];
    const isDev = devHosts.some((h) => host.includes(h));

    if (!isDev && host) {
      setDetectedDomain(host);
    }
  }, []);

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
      const data = await fetchWebsiteDetail(websiteId);
      setWebsite(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load website');
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  const updateWebsite = useCallback(
    async (updates) => {
      if (!websiteId) return;

      try {
        setSaving(true);
        const data = await updateWebsiteApi(websiteId, updates);
        setWebsite(data);
        return data;
      } catch (err) {
        throw new Error(err.response?.data?.detail || 'Failed to update website');
      } finally {
        setSaving(false);
      }
    },
    [websiteId]
  );

  const publish = useCallback(async () => {
    if (!websiteId) return;

    try {
      const data = await publishWebsite(websiteId);
      setWebsite(data);
      return data;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Failed to publish website');
    }
  }, [websiteId]);

  const unpublish = useCallback(async () => {
    if (!websiteId) return;

    try {
      const data = await unpublishWebsite(websiteId);
      setWebsite(data);
      return data;
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
