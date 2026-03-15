/**
 * API Service
 * Centralized API client with interceptors for authentication, error handling, and logging
 */

import axios from 'axios';
import { ENV_CONFIG } from '../config/environment';
import { HTTP_STATUS, ERROR_MESSAGES } from '../config/constants';
import { getStorageItem, removeStorageItem } from '../utils/storage';

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
   * Setup request and response interceptors
   */
  setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        const token = getStorageItem(ENV_CONFIG.STORAGE_KEYS.TOKEN);
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

    // Handle unauthorized - redirect to login
    if (status === HTTP_STATUS.UNAUTHORIZED) {
      removeStorageItem(ENV_CONFIG.STORAGE_KEYS.TOKEN);
      removeStorageItem(ENV_CONFIG.STORAGE_KEYS.USER);
      window.location.href = '/auth';
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
   * Get user-friendly error message based on status code
   */
  getErrorMessage(status, data) {
    // Use server message if available
    if (data?.detail) {
      return data.detail;
    }
    if (data?.message) {
      return data.message;
    }

    // Use predefined messages
    switch (status) {
      case HTTP_STATUS.BAD_REQUEST:
        return ERROR_MESSAGES.VALIDATION_ERROR;
      case HTTP_STATUS.UNAUTHORIZED:
        return ERROR_MESSAGES.UNAUTHORIZED;
      case HTTP_STATUS.FORBIDDEN:
        return ERROR_MESSAGES.FORBIDDEN;
      case HTTP_STATUS.NOT_FOUND:
        return ERROR_MESSAGES.NOT_FOUND;
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
