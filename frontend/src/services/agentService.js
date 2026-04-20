/**
 * Agents Service
 * Handles all agent-related API calls
 */

import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

/** Telethon + SOCKS can exceed default API timeout (30s); avoid axios abort → nginx 499. */
const USERBOT_TELETHON_TIMEOUT_MS = 120_000;

export const agentService = {
  /**
   * Get all agents for current user
   */
  getAll: async (params = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_LIST, { params });
    return response.data;
  },

  /**
   * Get agent by ID
   */
  getById: async (id) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_DETAIL, {
      params: { bot_id: id },
    });
    return response.data;
  },

  /**
   * Create new agent
   */
  create: async (agentData) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CREATE, agentData);
    return response.data;
  },

  createUserbot: async (agentData) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CREATE_USERBOT, agentData, {
      timeout: USERBOT_TELETHON_TIMEOUT_MS,
    });
    return response.data;
  },

  requestUserbotCode: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_USERBOT_REQUEST_CODE, data, {
      timeout: USERBOT_TELETHON_TIMEOUT_MS,
    });
    return response.data;
  },

  verifyUserbotCode: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_USERBOT_VERIFY_CODE, data, {
      timeout: USERBOT_TELETHON_TIMEOUT_MS,
    });
    return response.data;
  },

  /**
   * Update agent
   */
  update: async (botId, agentData) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_UPDATE, {
      bot_id: botId,
      ...agentData,
    });
    return response.data;
  },

  /**
   * Delete agent
   */
  delete: async (botId) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_DELETE, {
      params: { bot_id: botId },
    });
    return response.data;
  },

  toggleStatus: async (botId) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_TOGGLE, {
      bot_id: botId,
    });
    return response.data;
  },

  aiImprovePrompt: async (botId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_AI_IMPROVE_PROMPT, {
      bot_id: botId,
    });
    return response.data;
  },

  aiGenerateWelcome: async (botId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_AI_GENERATE_WELCOME, {
      bot_id: botId,
    });
    return response.data;
  },

  externalChat: async (message, apiKey) => {
    const response = await apiClient.post(
      API_ROUTES.AGENTS_EXTERNAL_CHAT,
      { message },
      {
        headers: {
          'X-Agent-API-Key': apiKey,
        },
      }
    );
    return response.data;
  },

  regenerateExternalKey: async (botId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_REGENERATE_EXTERNAL_KEY, {
      bot_id: botId,
    });
    return response.data;
  },

  getAnalyticsSummary: async (botId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_SUMMARY, {
      params: { bot_id: botId },
    });
    return response.data;
  },

  getAnalyticsChats: async (botId, params = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_CHATS, {
      params: { bot_id: botId, ...params },
    });
    return response.data;
  },

  getAnalyticsTimeseries: async (botId, days = 30) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_TIMESERIES, {
      params: { bot_id: botId, days },
    });
    return response.data;
  },

  setUserFrozen: async (botId, userExternalId, frozen) => {
    await apiClient.post(API_ROUTES.AGENTS_ANALYTICS_FROZEN, {
      bot_id: botId,
      user_external_id: userExternalId,
      frozen,
    });
  },

  sendTelegramMessageAsOwner: async (botId, userExternalId, message) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_TELEGRAM_SEND_TO_USER, {
      bot_id: botId,
      user_external_id: userExternalId,
      message,
    });
    return response.data;
  },

  getTelegramBroadcastRecipients: async (botId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_TELEGRAM_BROADCAST_RECIPIENTS, {
      params: { bot_id: botId },
    });
    return response.data;
  },

  sendTelegramBroadcast: async (botId, message, { skipFrozen = true, maxRecipients = 500 } = {}) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_TELEGRAM_BROADCAST, {
      bot_id: botId,
      message,
      skip_frozen: skipFrozen,
      max_recipients: maxRecipients,
    });
    return response.data;
  },

  uploadDocumentByBotId: async (botId, file) => {
    const formData = new FormData();
    formData.append('agent_data', JSON.stringify({ bot_id: botId }));
    formData.append('file', file);

    const response = await apiClient.post(
      API_ROUTES.DOCUMENTS_CREATE,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  uploadPublicLinkByBotId: async (botId, url) => {
    const response = await apiClient.post(API_ROUTES.DOCUMENTS_CREATE_LINK, {
      bot_id: botId,
      url,
    });
    return response.data;
  },

  getDocumentsByBotId: async (botId) => {
    const response = await apiClient.get(API_ROUTES.DOCUMENTS_LIST_BY_BOT, {
      params: { bot_id: botId },
    });
    return response.data;
  },

  deleteDocumentById: async (docId) => {
    const response = await apiClient.delete(API_ROUTES.DOCUMENTS_DELETE(docId));
    return response.data;
  },
};

export default agentService;
