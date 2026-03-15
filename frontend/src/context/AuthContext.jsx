/**
 * AuthContext
 * Manages authentication state globally across the app
 */

import React, { createContext, useCallback, useEffect, useState } from 'react';
import authService from '../services/authService';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { ENV_CONFIG } from '../config/environment';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken, removeToken] = useLocalStorage(ENV_CONFIG.STORAGE_KEYS.TOKEN, null);
  const [user, setUser] = useLocalStorage(ENV_CONFIG.STORAGE_KEYS.USER, null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  // Check if user is logged in on mount
  useEffect(() => {
    const initializeAuth = async () => {
      if (token) {
        try {
          const currentUser = await authService.getCurrentUser();
          setUser(currentUser);
        } catch (error) {
          // Token is invalid, clear it
          removeToken();
          setUser(null);
        }
      }
      setIsLoadingAuth(false);
    };

    initializeAuth();
  }, []);

  const login = useCallback(
    async (email, password) => {
      try {
        const response = await authService.login(email, password);
        setToken(response.token);
        setUser(response.user);
        return response;
      } catch (error) {
        throw error;
      }
    },
    [setToken, setUser]
  );

  const register = useCallback(
    async (email, password, name) => {
      try {
        const response = await authService.register(email, password, name);
        setToken(response.token);
        setUser(response.user);
        return response;
      } catch (error) {
        throw error;
      }
    },
    [setToken, setUser]
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      removeToken();
      setUser(null);
    }
  }, [removeToken, setUser]);

  const isAuthenticated = !!token && !!user;

  const value = {
    token,
    user,
    isAuthenticated,
    isLoadingAuth,
    login,
    register,
    logout,
    setUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
