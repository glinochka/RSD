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
      params: { agent_id: id },
    });
    return response.data;
  },

  /**
   * Create new agent
   */
  createEmpty: async (agentData) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CREATE_EMPTY, agentData);
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

  requestWhatsAppUserbotCode: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_WHATSAPP_USERBOT_REQUEST_CODE, data);
    return response.data;
  },

  verifyWhatsAppUserbotCode: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_WHATSAPP_USERBOT_VERIFY_CODE, data);
    return response.data;
  },

  whatsappUserbotAuthStatus: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_WHATSAPP_USERBOT_AUTH_STATUS, data);
    return response.data;
  },

  getChannels: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_CHANNELS_LIST, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  addBotChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_BOT, data);
    return response.data;
  },

  addUserbotChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_USERBOT, data, {
      timeout: USERBOT_TELETHON_TIMEOUT_MS,
    });
    return response.data;
  },

  addWhatsAppUserbotChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_WHATSAPP_USERBOT, data);
    return response.data;
  },

  addWhatsAppBusinessApiChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_WHATSAPP_BUSINESS_API, data);
    return response.data;
  },

  removeChannel: async ({ agent_id, connection_id }) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_CHANNELS_DELETE, {
      params: { agent_id, connection_id },
    });
    return response.data;
  },

  /**
   * Update agent
   */
  update: async (agentId, agentData) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_UPDATE, {
      agent_id: agentId,
      ...agentData,
    });
    return response.data;
  },

  /**
   * Delete agent
   */
  delete: async (agentId) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_DELETE, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  toggleStatus: async (agentId) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_TOGGLE, {
      agent_id: agentId,
    });
    return response.data;
  },

  aiImprovePrompt: async (agentId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_AI_IMPROVE_PROMPT, {
      agent_id: agentId,
    });
    return response.data;
  },

  aiGenerateWelcome: async (agentId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_AI_GENERATE_WELCOME, {
      agent_id: agentId,
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

  regenerateExternalKey: async (agentId) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_REGENERATE_EXTERNAL_KEY, {
      agent_id: agentId,
    });
    return response.data;
  },

  getAnalyticsSummary: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_SUMMARY, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  getAnalyticsChats: async (agentId, params = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_CHATS, {
      params: { agent_id: agentId, ...params },
    });
    return response.data;
  },

  getAnalyticsTimeseries: async (agentId, days = 30) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_TIMESERIES, {
      params: { agent_id: agentId, days },
    });
    return response.data;
  },

  getAnalyticsCrmActions: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_CRM_ACTIONS, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  setUserFrozen: async (agentId, userExternalId, frozen) => {
    await apiClient.post(API_ROUTES.AGENTS_ANALYTICS_FROZEN, {
      agent_id: agentId,
      user_external_id: userExternalId,
      frozen,
    });
  },

  sendTelegramMessageAsOwner: async (agentId, userExternalId, message, preferredChannel = null) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_TELEGRAM_SEND_TO_USER, {
      agent_id: agentId,
      user_external_id: userExternalId,
      preferred_channel: preferredChannel,
      message,
    });
    return response.data;
  },

  getTelegramBroadcastRecipients: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_TELEGRAM_BROADCAST_RECIPIENTS, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  sendTelegramBroadcast: async (agentId, message, { skipFrozen = true, maxRecipients = 500 } = {}) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_TELEGRAM_BROADCAST, {
      agent_id: agentId,
      message,
      skip_frozen: skipFrozen,
      max_recipients: maxRecipients,
    });
    return response.data;
  },

  sendWhatsappUserbotMessageAsOwner: async (agentId, userExternalId, message) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_WHATSAPP_USERBOT_SEND_TO_USER, {
      agent_id: agentId,
      user_external_id: userExternalId,
      message,
    });
    return response.data;
  },

  getWhatsappUserbotBroadcastRecipients: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_WHATSAPP_USERBOT_BROADCAST_RECIPIENTS, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  sendWhatsappUserbotBroadcast: async (agentId, message, { skipFrozen = true, maxRecipients = 500 } = {}) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_WHATSAPP_USERBOT_BROADCAST, {
      agent_id: agentId,
      message,
      skip_frozen: skipFrozen,
      max_recipients: maxRecipients,
    });
    return response.data;
  },

  connectCrm: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CRM_CONNECT, data);
    return response.data;
  },

  validateCrm: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CRM_VALIDATE, data);
    return response.data;
  },

  getCrmHealth: async ({ agent_id = null, bot_id = null, provider = null } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_CRM_HEALTH, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        provider: provider ?? undefined,
      },
    });
    return response.data;
  },

  uploadDocumentByBotId: async (agentId, file) => {
    const formData = new FormData();
    formData.append('agent_data', JSON.stringify({ agent_id: agentId }));
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

  uploadPublicLinkByBotId: async (agentId, url) => {
    const response = await apiClient.post(API_ROUTES.DOCUMENTS_CREATE_LINK, {
      agent_id: agentId,
      url,
    });
    return response.data;
  },

  getDocumentsByBotId: async (agentId) => {
    const response = await apiClient.get(API_ROUTES.DOCUMENTS_LIST_BY_BOT, {
      params: { agent_id: agentId },
    });
    return response.data;
  },

  deleteDocumentById: async (docId) => {
    const response = await apiClient.delete(API_ROUTES.DOCUMENTS_DELETE(docId));
    return response.data;
  },
};

export default agentService;
