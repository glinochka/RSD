/**
 * useAsync Hook
 * Handles async operations with loading, error, and data states
 */

import { useState, useCallback, useEffect, useRef } from 'react';

export const useAsync = (asyncFunction, immediate = true) => {
  const [status, setStatus] = useState('idle');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Use ref to track if component is mounted
  const mounted = useRef(true);

  const execute = useCallback(async (...args) => {
    setStatus('pending');
    setData(null);
    setError(null);

    try {
      const response = await asyncFunction(...args);
      if (mounted.current) {
        setData(response);
        setStatus('success');
      }
      return response;
    } catch (err) {
      if (mounted.current) {
        setError(err);
        setStatus('error');
      }
      throw err;
    }
  }, [asyncFunction]);

  useEffect(() => {
    // Reset mount flag on each effect run (important for React StrictMode in dev)
    mounted.current = true;

    if (immediate) {
      execute();
    }

    return () => {
      mounted.current = false;
    };
  }, [execute, immediate]);

  return {
    execute,
    status,
    data,
    error,
    isLoading: status === 'pending',
    isError: status === 'error',
    isSuccess: status === 'success',
  };
};

export default useAsync;
