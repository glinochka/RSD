/**
 * Authentication Service
 * Handles the full auth lifecycle per backend app/router_users/router.py.
 *
 * Backend returns on successful login/registration:
 *   { "access_token": "<jwt>", "refresh_token": "<token>", "token_type": "bearer" }
 * We normalize to { token, refreshToken, tokenType, user } and the token pair is stored for the
 * API client interceptor (Authorization: Bearer <access_token>).
 *
 * Payloads:
 * - login: { name, password } where name can be username or email
 * - register: { email, password }
 */

import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

/** Normalize backend auth response to a shape used by AuthContext and storage */
function normalizeAuthResponse(data, userName) {
  const token = data?.access_token ?? data?.token ?? null;
  const refreshToken = data?.refresh_token ?? null;
  const tokenType = data?.token_type ?? 'bearer';
  if (!token) {
    throw new Error('Сервер не вернул токен доступа');
  }
  if (!refreshToken) {
    throw new Error('Сервер не вернул refresh token');
  }
  return {
    token,
    refreshToken,
    tokenType,
    user: { name: userName },
  };
}

export const authService = {
  /**
   * Login: POST /api/users/login → { access_token, token_type }.
   * Returns { token, tokenType, user } for storage and UI.
   */
  login: async (name, password) => {
    const response = await apiClient.post(API_ROUTES.AUTH_LOGIN, {
      name: name.trim(),
      password,
    });
    return normalizeAuthResponse(response.data, name.trim());
  },

  loginWithGoogleIdToken: async (idToken, nonce) => {
    const response = await apiClient.post(API_ROUTES.AUTH_GOOGLE, {
      id_token: idToken,
      nonce,
    });
    return normalizeAuthResponse(response.data, 'google_user');
  },

  /**
   * Register step 1: sends verification code to email.
   */
  register: async (email, password) => {
    const response = await apiClient.post(API_ROUTES.AUTH_REGISTER, {
      email: email.trim(),
      password,
    });
    return response.data;
  },

  resendRegistrationCode: async (email) => {
    const response = await apiClient.post(API_ROUTES.AUTH_REGISTER_RESEND_CODE, {
      email: email.trim(),
    });
    return response.data;
  },

  /**
   * Register step 2: verifies code and receives tokens.
   */
  verifyRegistrationCode: async (email, code) => {
    const response = await apiClient.post(API_ROUTES.AUTH_REGISTER_VERIFY, {
      email: email.trim(),
      code: code.trim(),
    });
    return normalizeAuthResponse(response.data, email.trim());
  },

  requestPasswordResetCode: async (email) => {
    const response = await apiClient.post(API_ROUTES.AUTH_PASSWORD_RESET_REQUEST, {
      email: email.trim(),
    });
    return response.data;
  },

  verifyPasswordResetCode: async (email, code) => {
    const response = await apiClient.post(API_ROUTES.AUTH_PASSWORD_RESET_VERIFY, {
      email: email.trim(),
      code: code.trim(),
    });
    return response.data;
  },

  confirmPasswordReset: async (email, resetToken, newPassword) => {
    const response = await apiClient.post(API_ROUTES.AUTH_PASSWORD_RESET_CONFIRM, {
      email: email.trim(),
      reset_token: resetToken,
      new_password: newPassword,
    });
    return response.data;
  },

  /**
   * Logout: optional backend call. Local token/user are always cleared by AuthContext.
   * No-op if backend has no logout endpoint (404/405).
   */
  logout: async () => {
    try {
      await apiClient.post(API_ROUTES.AUTH_LOGOUT);
    } catch (err) {
      if (err?.status === 404 || err?.status === 405) {
        return;
      }
      throw err;
    }
  },

  /**
   * Refresh token (if backend implements it). Not used by default.
   */
  refreshToken: async () => {
    throw new Error('authService.refreshToken is deprecated. Use API client interceptor refresh flow.');
  },

  /**
   * Get current user (if backend implements GET /api/users/me).
   * Not used on app init because backend may not expose this route.
   */
  getCurrentUser: async () => {
    const response = await apiClient.get(API_ROUTES.USERS_ME);
    return response.data;
  },

  startTelegramLink: async (telegramUsername) => {
    const response = await apiClient.post(API_ROUTES.USERS_TELEGRAM_LINK_START, {
      telegram_username: telegramUsername.trim(),
    });
    return response.data;
  },
};

export default authService;
