/**
 * Custom agents (/custom) API service.
 * Uses a separate JWT token stored under ENV_CONFIG.STORAGE_KEYS.CUSTOM_TOKEN.
 */

import { API_ROUTES } from '../config/constants';
import { ENV_CONFIG } from '../config/environment';
import { getStorageItem, setStorageItem, removeStorageItem } from '../utils/storage';

const CUSTOM_TOKEN_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_TOKEN;
const CUSTOM_AUTOMATION_ID_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_AUTOMATION_ID;
const CUSTOM_IS_ADMIN_KEY = ENV_CONFIG.STORAGE_KEYS.CUSTOM_IS_ADMIN;

const getBaseUrl = () => ENV_CONFIG.API.BASE_URL || '';

export const mediaUrl = (path, cacheKey) => {
  if (!path) {
    return '';
  }
  if (/^https?:\/\//i.test(path) || path.startsWith('data:')) {
    return path;
  }
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const url = `${getBaseUrl()}${normalized}`;
  if (!cacheKey) {
    return url;
  }
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}v=${encodeURIComponent(cacheKey)}`;
};

const getCustomToken = () => {
  const token = getStorageItem(CUSTOM_TOKEN_KEY);
  return typeof token === 'string' && token.trim() ? token.trim() : null;
};

const getAuthHeaders = () => {
  const token = getCustomToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const handleResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = error.detail;
    let message = `HTTP ${response.status}`;
    if (typeof detail === 'string') {
      message = detail;
    } else if (detail && typeof detail.message === 'string') {
      message = detail.message;
    }
    const err = new Error(message);
    err.status = response.status;
    err.detail = detail;
    throw err;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
};

const customService = {
  getCustomToken,

  setCustomSession({ access_token, custom_admin, custom_automation_id }) {
    setStorageItem(CUSTOM_TOKEN_KEY, access_token);
    setStorageItem(CUSTOM_IS_ADMIN_KEY, Boolean(custom_admin));
    setStorageItem(CUSTOM_AUTOMATION_ID_KEY, custom_automation_id || null);
  },

  clearCustomSession() {
    removeStorageItem(CUSTOM_TOKEN_KEY);
    removeStorageItem(CUSTOM_IS_ADMIN_KEY);
    removeStorageItem(CUSTOM_AUTOMATION_ID_KEY);
  },

  isCustomAdmin() {
    return Boolean(getStorageItem(CUSTOM_IS_ADMIN_KEY));
  },

  getCustomAutomationId() {
    return getStorageItem(CUSTOM_AUTOMATION_ID_KEY);
  },

  async login(username, password) {
    const body = JSON.stringify({ username, password });
    const headers = { 'Content-Type': 'application/json' };
    const adminResponse = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_LOGIN}`, {
      method: 'POST',
      headers,
      body,
    });
    if (adminResponse.ok) {
      const data = await adminResponse.json();
      this.setCustomSession(data);
      return data;
    }
    const automationResponse = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_LOGIN}`, {
      method: 'POST',
      headers,
      body,
    });
    if (automationResponse.ok) {
      const data = await automationResponse.json();
      this.setCustomSession(data);
      return data;
    }
    throw new Error('Неверный логин или пароль');
  },

  async loginAdmin(username, password) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_LOGIN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await handleResponse(response);
    this.setCustomSession(data);
    return data;
  },

  async loginAutomation(username, password) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_LOGIN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await handleResponse(response);
    this.setCustomSession(data);
    return data;
  },

  async getAdminDashboard() {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_DASHBOARD}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async listAutomations() {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATIONS}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomation(id) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION(id)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async createAutomation(data) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATIONS}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async updateAutomation(id, data) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION(id)}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async deleteAutomation(id) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION(id)}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async listCredentials(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION_CREDENTIALS(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async createCredential(automationId, data) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION_CREDENTIALS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async deleteCredential(automationId, credentialId) {
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_ADMIN_AUTOMATION_CREDENTIALS(automationId)}/${credentialId}`;
    const response = await fetch(url, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomationDashboard(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getUbtStats(automationId, {
    period,
    historyType,
    search,
    status,
    visibility,
    threshold,
    minAttempts,
    limit,
    offset,
  } = {}) {
    const params = new URLSearchParams();
    if (period) {
      params.set('period', period);
    }
    if (historyType) {
      params.set('history_type', historyType);
    }
    if (search) {
      params.set('search', search);
    }
    if (status) {
      params.set('status', status);
    }
    if (visibility) {
      params.set('visibility', visibility);
    }
    if (threshold !== undefined) {
      params.set('threshold', String(threshold));
    }
    if (minAttempts !== undefined) {
      params.set('min_attempts', String(minAttempts));
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_STATS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async addStatsBlacklist(automationId, { chatId, query, reason } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_STATS_BLACKLIST(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        chat_id: chatId || undefined,
        query: query || undefined,
        reason: reason || 'manual',
      }),
    });
    return handleResponse(response);
  },

  async getNeurocommentingModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveNeurocommentingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runNeurocommentingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addNeurocommentingChannels(automationId, links) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING_CHANNELS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links }),
    });
    return handleResponse(response);
  },

  async saveNeurocommentingPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async createNeurocommentingPrompt(automationId, { name, content } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING_PROMPTS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name, content }),
    });
    return handleResponse(response);
  },

  async blackboxNeurocommentingChat(automationId, { chatId, query } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCOMMENTING_BLACKLIST(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ chat_id: chatId, query }),
    });
    return handleResponse(response);
  },

  async getNeurochattingModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveNeurochattingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runNeurochattingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addNeurochattingGroups(automationId, links) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING_GROUPS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links }),
    });
    return handleResponse(response);
  },

  async saveNeurochattingPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async createNeurochattingPrompt(automationId, { name, content } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING_PROMPTS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name, content }),
    });
    return handleResponse(response);
  },

  async blackboxNeurochattingChat(automationId, { chatId, query } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROCHATTING_BLACKLIST(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ chat_id: chatId, query }),
    });
    return handleResponse(response);
  },

  async getMasslookingModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSLOOKING(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveMasslookingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSLOOKING(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runMasslookingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSLOOKING_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async saveMasslookingPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSLOOKING_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async getMassprimingModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSPRIMING(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveMassprimingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSPRIMING(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runMassprimingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSPRIMING_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async saveMassprimingPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_MASSPRIMING_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async getParserModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveParserModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runParserModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async saveParserPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async addParserTargets(automationId, links) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_TARGETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links }),
    });
    return handleResponse(response);
  },

  async importParserFile(automationId, file) {
    const formData = new FormData();
    formData.append('archive', file);
    const token = getCustomToken();
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_IMPORT(automationId)}`, {
      method: 'POST',
      headers,
      body: formData,
    });
    return handleResponse(response);
  },

  async getParserResults(automationId, { query, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (query) params.set('query', query);
    if (limit !== undefined) params.set('limit', String(limit));
    if (offset !== undefined) params.set('offset', String(offset));
    const suffix = params.toString() ? `?${params}` : '';
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_RESULTS(automationId)}${suffix}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async clearParserResults(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PARSER_RESULTS_CLEAR(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getChatBroadcastsModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveChatBroadcastsModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runChatBroadcastsModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addChatBroadcastsGroups(automationId, links) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS_GROUPS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links }),
    });
    return handleResponse(response);
  },

  async saveChatBroadcastsPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async blackboxChatBroadcastsChat(automationId, { chatId, query } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_BROADCASTS_BLACKLIST(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ chat_id: chatId, query }),
    });
    return handleResponse(response);
  },

  async getDmBroadcastsModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DM_BROADCASTS(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveDmBroadcastsModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DM_BROADCASTS(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runDmBroadcastsModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DM_BROADCASTS_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addDmBroadcastsRecipients(automationId, recipients) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DM_BROADCASTS_RECIPIENTS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ recipients }),
    });
    return handleResponse(response);
  },

  async saveDmBroadcastsPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DM_BROADCASTS_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async getNeuroshillingModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveNeuroshillingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runNeuroshillingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async checkNeuroshillingModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_CHECK(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addNeuroshillingTargets(automationId, links, kind = 'auto') {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_TARGETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links, kind }),
    });
    return handleResponse(response);
  },

  async saveNeuroshillingPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async generateNeuroshillingLines(automationId, topic) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_GENERATE(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ topic }),
    });
    return handleResponse(response);
  },

  async blackboxNeuroshillingChat(automationId, { chatId, query } = {}) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_NEUROSHILLING_BLACKLIST(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ chat_id: chatId, query }),
    });
    return handleResponse(response);
  },

  async getWarmupModule(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_WARMUP(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async saveWarmupModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_WARMUP(automationId)}`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  async runWarmupModule(automationId, payload) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_WARMUP_RUN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload || {}),
    });
    return handleResponse(response);
  },

  async addWarmupTargets(automationId, links) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_WARMUP_TARGETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ links }),
    });
    return handleResponse(response);
  },

  async saveWarmupPreset(automationId, name) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_WARMUP_PRESETS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });
    return handleResponse(response);
  },

  async getAutomationActivity(automationId, { activityType, sort, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (activityType) {
      params.set('activity_type', activityType);
    }
    if (sort) {
      params.set('sort', sort);
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACTIVITY(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomationErrors(automationId, { actionType, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (actionType) {
      params.set('action_type', actionType);
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ERRORS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomationAccounts(automationId, { status, search, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (status) {
      params.set('status', status);
    }
    if (search) {
      params.set('search', search);
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomationAccount(automationId, accountId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/${accountId}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getAutomationAccountBanStats(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_BAN_STATS(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async runAutomationAccountHealthCheck(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_HEALTH_CHECK(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async checkAccountSpamblock(automationId, accountId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNT_SPAMBLOCK_CHECK(automationId, accountId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async listAccountProxies(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/proxies`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async bulkUploadAccounts(automationId, file, { proxyId, proxyLine } = {}) {
    const formData = new FormData();
    formData.append('archive', file);
    const line = (proxyLine || '').trim();
    if (line) {
      formData.append('proxy_line', line);
    } else if (proxyId) {
      formData.append('proxy_id', String(proxyId));
    }
    const token = getCustomToken();
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/bulk-upload`,
      {
        method: 'POST',
        headers,
        body: formData,
      },
    );
    return handleResponse(response);
  },

  async getAccountSetupTemplates(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_SETUP_TEMPLATES(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async startAccountPrepare(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_PREPARE(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getAccountPrepareStatus(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_PREPARE_STATUS(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async startAccountQr(automationId, { proxyId, proxyLine } = {}) {
    const body = {};
    const line = (proxyLine || '').trim();
    if (line) {
      body.proxy_line = line;
    } else if (proxyId) {
      body.proxy_id = Number(proxyId);
    }
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_QR_START(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body),
      },
    );
    return handleResponse(response);
  },

  async accountQrStatus(automationId, authToken) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_QR_STATUS(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ auth_token: authToken }),
      },
    );
    return handleResponse(response);
  },

  async verifyAccountQr2fa(automationId, authToken, password) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_QR_2FA(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ auth_token: authToken, password }),
      },
    );
    return handleResponse(response);
  },

  async requestAccountSms(automationId, phoneNumber, { proxyId, proxyLine } = {}) {
    const body = { phone_number: phoneNumber };
    const line = (proxyLine || '').trim();
    if (line) {
      body.proxy_line = line;
    } else if (proxyId) {
      body.proxy_id = Number(proxyId);
    }
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_SMS_REQUEST(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(body),
      },
    );
    return handleResponse(response);
  },

  async verifyAccountSms(automationId, { authToken, code, password }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_SMS_VERIFY(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          auth_token: authToken,
          code,
          password: password || undefined,
        }),
      },
    );
    return handleResponse(response);
  },

  async getAccountTelegramCode(automationId, accountId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNT_TELEGRAM_CODE(automationId, accountId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

    async updateAccount(automationId, accountId, { displayName, bio } = {}) {
      const body = {};
      if (displayName !== undefined) {
        body.display_name = displayName;
      }
      if (bio !== undefined) {
        body.bio = bio;
      }
      const response = await fetch(
        `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/${accountId}`,
        {
          method: 'PATCH',
          headers: getAuthHeaders(),
          body: JSON.stringify(body),
        },
      );
      return handleResponse(response);
    },

    async deleteAccount(automationId, accountId) {
      const response = await fetch(
        `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/${accountId}`,
        {
          method: 'DELETE',
          headers: getAuthHeaders(),
        },
      );
    return handleResponse(response);
  },

  async startAccountWarmup(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS_WARMUP_START(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getTestLab(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async updateTestLab(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST(automationId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async joinTestLab(automationId, data = {}) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_JOIN(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async resetTestLab(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_RESET(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async runTestLabShilling(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_SHILLING(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async startTestLabChannelActivity(automationId, activity) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_CHANNEL_ACTIVITY(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ activity }),
      },
    );
    return handleResponse(response);
  },

  async getTestLabChannelActivity(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_CHANNEL_ACTIVITY(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async runTestLabNeurocommenting(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_NEUROCOMMENTING(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async runTestLabDmp(automationId, phone) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TEST_DMP(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ phone }),
      },
    );
    return handleResponse(response);
  },

  async getAutomationSettings(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_SETTINGS(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async updateAutomationSettings(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_SETTINGS(automationId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async getChats(automationId, {
    joinStatus,
    commentsOpen,
    commentsUnchecked,
    minMembers,
    maxMembers,
    activityWithinHours,
    folderId,
    limit,
    offset,
  } = {}) {
    const params = new URLSearchParams();
    if (joinStatus) {
      params.set('join_status', joinStatus);
    }
    if (commentsOpen === true || commentsOpen === false) {
      params.set('comments_open', commentsOpen ? 'true' : 'false');
    }
    if (commentsUnchecked) {
      params.set('comments_unchecked', 'true');
    }
    if (minMembers !== undefined && minMembers !== '' && minMembers !== null) {
      params.set('min_members', String(minMembers));
    }
    if (maxMembers !== undefined && maxMembers !== '' && maxMembers !== null) {
      params.set('max_members', String(maxMembers));
    }
    if (activityWithinHours) {
      params.set('activity_within_hours', String(activityWithinHours));
    }
    if (folderId) {
      params.set('folder_id', String(folderId));
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHATS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async createChat(automationId, data) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHATS(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async deleteChat(automationId, chatId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT(automationId, chatId)}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getChatFolders(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_FOLDERS(automationId)}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async deleteChatFolder(automationId, folderId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_FOLDER(automationId, folderId)}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getChatMessages(automationId, chatId, { limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_MESSAGES(automationId, chatId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async bulkImportChats(automationId, file) {
    const formData = new FormData();
    formData.append('archive', file);
    const token = getCustomToken();
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_IMPORT(automationId)}`, {
      method: 'POST',
      headers,
      body: formData,
    });
    return handleResponse(response);
  },

  async getImportJobs(automationId, { limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_IMPORT_JOBS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async inspectChatComments(automationId, force = false) {
    const params = force ? '?force=true' : '';
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_INSPECT_COMMENTS(automationId)}${params}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getChatInspectStatus(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_INSPECT_STATUS(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async runChatJoin(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_JOIN(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async runChatMonitor(automationId) {
    const response = await fetch(`${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_MONITOR(automationId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async updateChatNeurocommentingConfig(automationId, chatId, { mode, isActive, neurocommentingConfig }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_NEUROCOMMENTING_CONFIG(automationId, chatId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          mode,
          is_active: isActive,
          neurocommenting_config: neurocommentingConfig,
        }),
      },
    );
    return handleResponse(response);
  },

  async runNeurocommenting(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_NEUROCOMMENTING_RUN(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async updateChatDiscussionConfig(automationId, chatId, { mode, discussionConfig }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCUSSION_CONFIG(automationId, chatId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mode, discussion_config: discussionConfig }),
      },
    );
    return handleResponse(response);
  },

  async runDiscussion(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCUSSION_RUN(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async updateChatShillingConfig(automationId, chatId, { mode, shillingConfig }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_SHILLING_CONFIG(automationId, chatId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mode, shilling_config: shillingConfig }),
      },
    );
    return handleResponse(response);
  },

  async runShilling(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_SHILLING_RUN(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async createDiscoveryTask(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async getDiscoveryTasks(automationId, { limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async approveDiscoveryTask(automationId, taskId, indices, mode = null) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY_APPROVE(automationId, taskId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ indices, mode }),
      },
    );
    return handleResponse(response);
  },

  async rejectDiscoveryTask(automationId, taskId, indices) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY_REJECT(automationId, taskId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ indices }),
      },
    );
    return handleResponse(response);
  },

  async getAutomationJobs(automationId, { bucket, category, search, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (bucket) {
      params.set('bucket', bucket);
    }
    if (category) {
      params.set('category', category);
    }
    if (search) {
      params.set('search', search);
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_JOBS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async cancelAutomationJob(automationId, jobId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_JOB_CANCEL(automationId, jobId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async startChatInspect(automationId, force = false) {
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_INSPECT_COMMENTS(automationId)}${force ? '?force=true' : ''}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async runJoinChats(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_JOIN(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getLeads(automationId, { status, source, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (status) {
      params.set('status', status);
    }
    if (source) {
      params.set('source', source);
    }
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEADS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async getLead(automationId, leadId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEAD(automationId, leadId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getLeadMessages(automationId, leadId, { limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEAD_MESSAGES(automationId, leadId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async updateLeadStatus(automationId, leadId, status) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEAD_STATUS(automationId, leadId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ status }),
      },
    );
    return handleResponse(response);
  },

  async deleteLead(automationId, leadId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEAD(automationId, leadId)}`,
      {
        method: 'DELETE',
        headers: getAuthHeaders(),
      },
    );
    if (response.status === 204) {
      return true;
    }
    return handleResponse(response);
  },

  async transferLead(automationId, leadId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_LEAD_TRANSFER(automationId, leadId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getDmpImports(automationId, { limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit !== undefined) {
      params.set('limit', String(limit));
    }
    if (offset !== undefined) {
      params.set('offset', String(offset));
    }
    const query = params.toString();
    const url = `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DMP_IMPORTS(automationId)}${query ? `?${query}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  async createDmpOrder(automationId, { importType, sourceUrl, requestedCount }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DMP_ORDERS(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ import_type: importType, source_url: sourceUrl, requested_count: requestedCount }),
      },
    );
    return handleResponse(response);
  },

  async runDmpPoll(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DMP_POLL(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getAmocrmConnection(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_CONNECTION(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async saveAmocrmCredentials(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_CREDENTIALS(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async startAmocrmOAuth(automationId, returnUrl) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_OAUTH_START(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ return_url: returnUrl }),
      },
    );
    return handleResponse(response);
  },

  async saveAmocrmPipeline(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_CONNECTION(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async deleteAmocrmConnection(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_CONNECTION(automationId)}`,
      {
        method: 'DELETE',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async runAmocrmSync(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_AMOCRM_SYNC(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async rotateDmpWebhookSecret(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_DMP_WEBHOOK_ROTATE(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async saveTelegramBot(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_TELEGRAM_BOT(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async listIntegrationRoutes(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_INTEGRATION_ROUTES(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async saveIntegrationRoute(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_INTEGRATION_ROUTES(automationId)}`,
      {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async deleteIntegrationRoute(automationId, routeId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_INTEGRATION_ROUTE(automationId, routeId)}`,
      {
        method: 'DELETE',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async saveGoogleSheets(automationId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_GOOGLE_SHEETS(automationId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async getPrompts(automationId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PROMPTS(automationId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async getPrompt(automationId, promptId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PROMPT(automationId, promptId)}`,
      {
        method: 'GET',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async updatePrompt(automationId, promptId, data) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PROMPT(automationId, promptId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      },
    );
    return handleResponse(response);
  },

  async togglePrompt(automationId, promptId) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PROMPT_TOGGLE(automationId, promptId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
      },
    );
    return handleResponse(response);
  },

  async testPrompt(automationId, promptId, variables) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_PROMPT_TEST(automationId, promptId)}`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ variables: variables || {} }),
      },
    );
    return handleResponse(response);
  },

  async bulkUpdateProfiles(automationId, { avatar, accountIds, status, bioTemplate, generateUnique, saveAsTemplate }) {
    const formData = new FormData();
    if (avatar) {
      formData.append('avatar', avatar);
    }
    const payload = {
      account_ids: accountIds || [],
      status: status || undefined,
      bio_template: bioTemplate || '',
      generate_unique: Boolean(generateUnique),
      save_as_template: Boolean(saveAsTemplate),
    };
    formData.append('payload', JSON.stringify(payload));

    const token = getCustomToken();
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/bulk-update-profiles`,
      {
        method: 'POST',
        headers,
        body: formData,
      },
    );
    return handleResponse(response);
  },
};

export default customService;
