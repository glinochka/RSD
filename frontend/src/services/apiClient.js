/**
 * API Service
 * Centralized API client. baseURL from ENV_CONFIG.API.BASE_URL; CORS: backend/app/origins.py.
 *
 * Auth lifecycle (backend router_users/router.py):
 * - Login/register return { access_token, refresh_token, token_type: "bearer" }.
 * - AuthContext stores both tokens. This client sends Bearer access_token and, on 401,
 *   performs one silent refresh using refresh_token, then retries the original request.
 * - This request interceptor reads that token and sets Authorization: Bearer <access_token>
 *   on every request so protected routes receive the JWT.
 * - On 401, the response interceptor clears token/user and redirects to /auth.
 */

import axios from 'axios';
import { ENV_CONFIG } from '../config/environment';
import { API_ROUTES, HTTP_STATUS, ERROR_MESSAGES } from '../config/constants';
import { getStorageItem, removeStorageItem, setStorageItem } from '../utils/storage';
import { normalizeDetail } from '../utils/errorUtils';

const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.TOKEN;
const REFRESH_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.REFRESH_TOKEN;
const USER_KEY = ENV_CONFIG.STORAGE_KEYS.USER;
const REFRESH_RETRY_FLAG = '_retriedWithRefreshedToken';

const isAuthRequest = (url) =>
  url !== null &&
  url !== undefined &&
  (url.includes('/login') || url.includes('/registration') || url.includes('/refresh'));

class APIClient {
  constructor() {
    this.client = axios.create({
      baseURL: ENV_CONFIG.API.BASE_URL,
      timeout: ENV_CONFIG.API.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.isRefreshing = false;
    this.refreshQueue = [];

    this.setupInterceptors();
  }

  queueRefreshWaiter() {
    return new Promise((resolve, reject) => {
      this.refreshQueue.push({ resolve, reject });
    });
  }

  flushRefreshQueue(error, nextAccessToken) {
    this.refreshQueue.forEach(({ resolve, reject }) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(nextAccessToken);
    });
    this.refreshQueue = [];
  }

  clearAuthStorage() {
    removeStorageItem(TOKEN_KEY);
    removeStorageItem(REFRESH_TOKEN_KEY);
    removeStorageItem(USER_KEY);
  }

  redirectToAuth() {
    if (window.location.pathname !== '/auth') {
      window.location.href = '/auth';
    }
  }

  async refreshAccessToken() {
    const refreshToken = getStorageItem(REFRESH_TOKEN_KEY);
    if (!refreshToken) {
      throw new Error('Refresh token is missing');
    }

    const refreshUrl = `${ENV_CONFIG.API.BASE_URL}${API_ROUTES.AUTH_REFRESH}`;
    const response = await axios.post(
      refreshUrl,
      { refresh_token: refreshToken },
      {
        timeout: ENV_CONFIG.API.TIMEOUT,
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const nextAccessToken = response?.data?.access_token;
    const nextRefreshToken = response?.data?.refresh_token;
    if (!nextAccessToken || !nextRefreshToken) {
      throw new Error('Token refresh response is invalid');
    }

    setStorageItem(TOKEN_KEY, nextAccessToken);
    setStorageItem(REFRESH_TOKEN_KEY, nextRefreshToken);
    return nextAccessToken;
  }

  /**
   * Request: attach Authorization: Bearer <access_token> from storage.
   * Response: on 401, clear token/user and redirect to /auth.
   */
  setupInterceptors() {
    this.client.interceptors.request.use(
      (config) => {
        const token = getStorageItem(TOKEN_KEY);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        this.handleRequestError(error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error) => this.handleResponseError(error)
    );
  }

  /**
   * Handle request errors
   */
  handleRequestError(error) {
    if (ENV_CONFIG.isDevelopment) {
      console.error('Request Error:', error);
    }
  }

  /**
   * Handle response errors with proper status code handling
   */
  async handleResponseError(error) {
    const status = error.response?.status;
    const data = error.response?.data;
    const requestUrl = error.response?.config?.url ?? error.config?.url;
    const originalRequest = error.response?.config ?? error.config;

    if (status === HTTP_STATUS.UNAUTHORIZED) {
      const canAttemptRefresh =
        !!originalRequest &&
        !isAuthRequest(requestUrl) &&
        !originalRequest[REFRESH_RETRY_FLAG] &&
        !!getStorageItem(REFRESH_TOKEN_KEY);

      if (canAttemptRefresh) {
        if (this.isRefreshing) {
          try {
            const queuedToken = await this.queueRefreshWaiter();
            originalRequest.headers = originalRequest.headers ?? {};
            originalRequest.headers.Authorization = `Bearer ${queuedToken}`;
            originalRequest[REFRESH_RETRY_FLAG] = true;
            return this.client(originalRequest);
          } catch {
            this.clearAuthStorage();
            this.redirectToAuth();
          }
        }

        this.isRefreshing = true;
        try {
          const nextAccessToken = await this.refreshAccessToken();
          this.flushRefreshQueue(null, nextAccessToken);
          originalRequest.headers = originalRequest.headers ?? {};
          originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
          originalRequest[REFRESH_RETRY_FLAG] = true;
          return this.client(originalRequest);
        } catch (refreshError) {
          this.flushRefreshQueue(refreshError, null);
          this.clearAuthStorage();
          this.redirectToAuth();
        } finally {
          this.isRefreshing = false;
        }
      } else if (!isAuthRequest(requestUrl)) {
        // Protected request failed and cannot be refreshed -> force clean re-login.
        this.clearAuthStorage();
        this.redirectToAuth();
      }
    }

    // Log error in development
    if (ENV_CONFIG.isDevelopment) {
      console.error('Response Error:', {
        status,
        data,
        message: error.message,
      });
    }

    // Return error with context
    const errorResponse = {
      status,
      message: this.getErrorMessage(status, data),
      data,
      originalError: error,
    };

    return Promise.reject(errorResponse);
  }

  /**
   * Get user-friendly message from FastAPI-style response (detail string or array).
   * Backend detail is preferred; fallbacks by status (e.g. 401, 409, 422).
   */
  getErrorMessage(status, data) {
    const rawDetail = data?.detail ?? data?.message;
    if (rawDetail !== null && rawDetail !== undefined) {
      const normalized =
        typeof rawDetail === 'string' ? rawDetail : normalizeDetail(rawDetail);
      if (normalized) {
        return normalized;
      }
    }

    switch (status) {
      case HTTP_STATUS.BAD_REQUEST:
        return ERROR_MESSAGES.VALIDATION_ERROR;
      case HTTP_STATUS.UNAUTHORIZED:
        return ERROR_MESSAGES.UNAUTHORIZED;
      case HTTP_STATUS.FORBIDDEN:
        return ERROR_MESSAGES.FORBIDDEN;
      case HTTP_STATUS.NOT_FOUND:
        return ERROR_MESSAGES.NOT_FOUND;
      case HTTP_STATUS.CONFLICT:
        return ERROR_MESSAGES.CONFLICT;
      case HTTP_STATUS.UNPROCESSABLE_ENTITY:
        return ERROR_MESSAGES.VALIDATION_ERROR;
      case HTTP_STATUS.INTERNAL_SERVER_ERROR:
      case HTTP_STATUS.SERVICE_UNAVAILABLE:
        return ERROR_MESSAGES.SERVER_ERROR;
      default:
        return ERROR_MESSAGES.NETWORK_ERROR;
    }
  }

  /**
   * GET request
   */
  async get(url, config = {}) {
    return this.client.get(url, config);
  }

  /**
   * POST request
   */
  async post(url, data = {}, config = {}) {
    return this.client.post(url, data, config);
  }

  /**
   * PUT request
   */
  async put(url, data = {}, config = {}) {
    return this.client.put(url, data, config);
  }

  /**
   * PATCH request
   */
  async patch(url, data = {}, config = {}) {
    return this.client.patch(url, data, config);
  }

  /**
   * DELETE request
   */
  async delete(url, config = {}) {
    return this.client.delete(url, config);
  }

  /**
   * Get the axios instance for advanced usage
   */
  getClient() {
    return this.client;
  }
}

// Export singleton instance
const apiClient = new APIClient();
export default apiClient;
