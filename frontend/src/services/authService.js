/**
 * Authentication Service
 * Handles all authentication-related API calls
 */

import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

export const authService = {
  /**
   * Login user with email and password
   */
  login: async (email, password) => {
    const response = await apiClient.post(API_ROUTES.AUTH_LOGIN, {
      email,
      password,
    });
    return response.data;
  },

  /**
   * Register new user
   */
  register: async (email, password, name) => {
    const response = await apiClient.post(API_ROUTES.AUTH_REGISTER, {
      email,
      password,
      name,
    });
    return response.data;
  },

  /**
   * Logout user
   */
  logout: async () => {
    const response = await apiClient.post(API_ROUTES.AUTH_LOGOUT);
    return response.data;
  },

  /**
   * Refresh authentication token
   */
  refreshToken: async () => {
    const response = await apiClient.post(API_ROUTES.AUTH_REFRESH);
    return response.data;
  },

  /**
   * Get current user profile
   */
  getCurrentUser: async () => {
    const response = await apiClient.get(API_ROUTES.USERS_ME);
    return response.data;
  },
};

export default authService;
