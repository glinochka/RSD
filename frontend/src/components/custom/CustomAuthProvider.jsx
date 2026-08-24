import React, { useCallback, useMemo, useState } from 'react';
import customService from '../../services/customService';
import { ENV_CONFIG } from '../../config/environment';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { CustomAuthContext } from './CustomAuthContext';

const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_TOKEN;
const AUTOMATION_ID_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_AUTOMATION_ID;
const IS_ADMIN_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_IS_ADMIN;

export const CustomAuthProvider = ({ children }) => {
  const [token, setToken, removeToken] = useLocalStorage(TOKEN_KEY, null);
  const [automationId, setAutomationId, removeAutomationId] = useLocalStorage(AUTOMATION_ID_KEY, null);
  const [isAdmin, setIsAdmin, removeIsAdmin] = useLocalStorage(IS_ADMIN_KEY, false);
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(
    async (username, password) => {
      const response = await customService.login(username, password);

      setToken(response.access_token);
      setIsAdmin(Boolean(response.custom_admin));
      setAutomationId(response.custom_automation_id || null);
      setIsLoading(false);
      return response;
    },
    [setAutomationId, setIsAdmin, setToken],
  );

  const logout = useCallback(() => {
    customService.clearCustomSession();
    removeToken();
    removeAutomationId();
    removeIsAdmin();
    setIsLoading(false);
  }, [removeAutomationId, removeIsAdmin, removeToken]);

  const isAuthenticated = Boolean(token);

  const value = useMemo(
    () => ({
      token,
      automationId,
      isAdmin,
      isAuthenticated,
      isLoading,
      login,
      logout,
    }),
    [token, automationId, isAdmin, isAuthenticated, isLoading, login, logout],
  );

  return <CustomAuthContext.Provider value={value}>{children}</CustomAuthContext.Provider>;
};

export default CustomAuthProvider;
