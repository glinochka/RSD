/**
 * AuthContext
 * Full authentication lifecycle (aligned with backend app/router_users/router.py):
 * - On login/register: store access_token and user; token is attached to requests via apiClient.
 * - On load: trust stored token/user; any 401 from API clears storage and redirects to /auth.
 * - On logout: clear token and user (and optionally call backend logout if implemented).
 */

import React, { createContext, useCallback, useEffect, useState } from 'react';
import authService from '../services/authService';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { ENV_CONFIG } from '../config/environment';

export const AuthContext = createContext(null);

const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.TOKEN;
const REFRESH_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.REFRESH_TOKEN;
const USER_KEY = ENV_CONFIG.STORAGE_KEYS.USER;

export const AuthProvider = ({ children }) => {
  const [token, setToken, removeToken] = useLocalStorage(TOKEN_KEY, null);
  const [, setRefreshToken, removeRefreshToken] = useLocalStorage(REFRESH_TOKEN_KEY, null);
  const [user, setUser] = useLocalStorage(USER_KEY, null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  // On mount: no /users/me call (backend may not expose it). Token validity is checked
  // when the first protected request runs; 401 triggers interceptor to clear and redirect.
  useEffect(() => {
    setIsLoadingAuth(false);
  }, []);

  // Store access_token so apiClient interceptor can send Authorization: Bearer <token>
  const login = useCallback(
    async (name, password) => {
      const response = await authService.login(name, password);
      setToken(response.token);
      setRefreshToken(response.refreshToken);
      setUser(response.user);
      return response;
    },
    [setRefreshToken, setToken, setUser]
  );

  const loginWithGoogle = useCallback(
    async (idToken, nonce) => {
      const response = await authService.loginWithGoogleIdToken(idToken, nonce);
      setToken(response.token);
      setRefreshToken(response.refreshToken);
      setUser(response.user);
      return response;
    },
    [setRefreshToken, setToken, setUser]
  );

  const register = useCallback(
    async (email, password) => {
      const response = await authService.register(email, password);
      return response;
    },
    []
  );

  const verifyRegistrationCode = useCallback(
    async (email, code) => {
      const response = await authService.verifyRegistrationCode(email, code);
      setToken(response.token);
      setRefreshToken(response.refreshToken);
      setUser(response.user);
      return response;
    },
    [setRefreshToken, setToken, setUser]
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      removeToken();
      removeRefreshToken();
      setUser(null);
    }
  }, [removeRefreshToken, removeToken, setUser]);

  const isAuthenticated = !!token && !!user;

  const value = {
    token,
    user,
    isAuthenticated,
    isLoadingAuth,
    login,
    loginWithGoogle,
    register,
    verifyRegistrationCode,
    logout,
    setUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
