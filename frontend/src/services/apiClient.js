/**
 * API Service
 * Centralized API client. baseURL from ENV_CONFIG.API.BASE_URL; CORS: backend/app/origins.py.
 *
 * Auth lifecycle (backend router_users/router.py):
 * - Login/register return { access_token, token_type: "bearer" }. AuthContext stores
 *   access_token under ENV_CONFIG.STORAGE_KEYS.TOKEN.
 * - This request interceptor reads that token and sets Authorization: Bearer <access_token>
 *   on every request so protected routes receive the JWT.
 * - On 401, the response interceptor clears token/user and redirects to /auth.
 */

import axios from 'axios';
import { ENV_CONFIG } from '../config/environment';
import { HTTP_STATUS, ERROR_MESSAGES } from '../config/constants';
import { getStorageItem, removeStorageItem } from '../utils/storage';
import { normalizeDetail } from '../utils/errorUtils';

const TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.TOKEN;
const USER_KEY = ENV_CONFIG.STORAGE_KEYS.USER;

const isAuthRequest = (url) =>
  url != null && (url.includes('/login') || url.includes('/registration'));

class APIClient {
  constructor() {
    this.client = axios.create({
      baseURL: ENV_CONFIG.API.BASE_URL,
      timeout: ENV_CONFIG.API.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
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
  handleResponseError(error) {
    const status = error.response?.status;
    const data = error.response?.data;
    const requestUrl = error.response?.config?.url ?? error.config?.url;

    if (status === HTTP_STATUS.UNAUTHORIZED) {
      removeStorageItem(TOKEN_KEY);
      removeStorageItem(USER_KEY);
      // Only redirect when the 401 is from a protected request (e.g. expired token).
      // Login/register 401 (user not found, wrong password) stay on auth page so the user sees the message.
      if (!isAuthRequest(requestUrl)) {
        window.location.href = '/auth';
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
    if (rawDetail != null) {
      const normalized =
        typeof rawDetail === 'string' ? rawDetail : normalizeDetail(rawDetail);
      if (normalized) return normalized;
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
