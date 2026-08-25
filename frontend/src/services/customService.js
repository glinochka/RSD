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
    throw new Error(error.detail || `HTTP ${response.status}`);
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

  async getAutomationAccounts(automationId, { status, accountClass, search, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (status) {
      params.set('status', status);
    }
    if (accountClass) {
      params.set('account_class', accountClass);
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

  async bulkUploadAccounts(automationId, file, assignClass = 'one_day') {
    const formData = new FormData();
    formData.append('archive', file);
    formData.append('assign_class', assignClass);
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

  async bulkClassifyAccounts(automationId, accountIds = []) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/bulk-classify`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ account_ids: accountIds }),
      },
    );
    return handleResponse(response);
  },

  async updateAccountClass(automationId, accountId, assignedClass) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}/${accountId}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ assigned_class: assignedClass }),
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

  async getChats(automationId, { joinStatus, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (joinStatus) {
      params.set('join_status', joinStatus);
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

  async updateChatNeurocommentingConfig(automationId, chatId, { mode, neurocommentingConfig }) {
    const response = await fetch(
      `${getBaseUrl()}${API_ROUTES.CUSTOM_AUTOMATION_CHAT_NEUROCOMMENTING_CONFIG(automationId, chatId)}`,
      {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ mode, neurocommenting_config: neurocommentingConfig }),
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

  async getLeads(automationId, { status, limit, offset } = {}) {
    const params = new URLSearchParams();
    if (status) {
      params.set('status', status);
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

  async bulkUpdateProfiles(automationId, { avatar, accountIds, accountClass, status, bioTemplate, generateUnique }) {
    const formData = new FormData();
    if (avatar) {
      formData.append('avatar', avatar);
    }
    const payload = {
      account_ids: accountIds || [],
      account_class: accountClass || undefined,
      status: status || undefined,
      bio_template: bioTemplate || '',
      generate_unique: Boolean(generateUnique),
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
