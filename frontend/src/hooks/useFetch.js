/**
 * useFetch Hook
 * Convenient hook for fetching data from API
 */

import { useEffect, useCallback } from 'react';
import { useAsync } from './useAsync';

export const useFetch = (url, options = {}, immediate = true) => {
  const { cache = true } = options;
  const cachedData = useCallback(() => {
    if (cache) {
      const cacheKey = `fetch_cache_${url}`;
      const cached = localStorage.getItem(cacheKey);
      return cached ? JSON.parse(cached) : null;
    }
    return null;
  }, [url, cache]);

  const fetchData = useCallback(async () => {
    const cached = cachedData();
    if (cached) return cached;

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP Error: ${response.status}`);
    }

    const data = await response.json();
    if (cache) {
      const cacheKey = `fetch_cache_${url}`;
      localStorage.setItem(cacheKey, JSON.stringify(data));
    }

    return data;
  }, [url, cache, cachedData]);

  const async= useAsync(fetchData, immediate);

  const refetch = useCallback(async () => {
    if (cache) {
      const cacheKey = `fetch_cache_${url}`;
      localStorage.removeItem(cacheKey);
    }
    return async.execute();
  }, [url, cache, async]);

  return {
    ...async,
    refetch,
  };
};

export default useFetch;
