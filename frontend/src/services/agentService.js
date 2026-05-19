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

  addMaxBotChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_MAX_BOT, data);
    return response.data;
  },

  addMaxUserbotChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_MAX_USERBOT, data);
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

  addTelephonyChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_ADD_TELEPHONY, data);
    return response.data;
  },

  validateTelephonyChannel: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CHANNELS_VALIDATE_TELEPHONY, data);
    return response.data;
  },

  getTelephonyCalls: async (agentId, params = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ANALYTICS_TELEPHONY_CALLS, {
      params: { agent_id: agentId, ...params },
    });
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

  sendExternalMessageAsOwner: async (agentId, userExternalId, message) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_EXTERNAL_SEND_TO_USER, {
      agent_id: agentId,
      user_external_id: userExternalId,
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

  sendMaxUserbotMessageAsOwner: async (agentId, userExternalId, message) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_MAX_USERBOT_SEND_TO_USER, {
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

  listAdminTemplateStaff: async ({ agent_id = null, bot_id = null, role = null, active_only = true } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_STAFF, {
      params: { agent_id: agent_id ?? undefined, bot_id: bot_id ?? undefined, role: role ?? undefined, active_only },
    });
    return response.data;
  },
  getAdminDomainRegistry: async () => {
    const response = await apiClient.get('/api/agents/admin_template/domain-registry');
    return response.data;
  },
  createAdminTemplateStaff: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_STAFF, data);
    return response.data;
  },
  updateAdminTemplateStaff: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_STAFF, data);
    return response.data;
  },
  deleteAdminTemplateStaff: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_STAFF, { data });
    return response.data;
  },

  listAdminTemplateServices: async ({ agent_id = null, bot_id = null, target_role = null, active_only = true } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SERVICES, {
      params: { agent_id: agent_id ?? undefined, bot_id: bot_id ?? undefined, target_role: target_role ?? undefined, active_only },
    });
    return response.data;
  },
  createAdminTemplateService: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SERVICES, data);
    return response.data;
  },
  updateAdminTemplateService: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SERVICES, data);
    return response.data;
  },
  deleteAdminTemplateService: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SERVICES, { data });
    return response.data;
  },

  listAdminTemplateResources: async ({ agent_id = null, bot_id = null, resource_type = null, active_only = true } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_RESOURCES, {
      params: { agent_id: agent_id ?? undefined, bot_id: bot_id ?? undefined, resource_type: resource_type ?? undefined, active_only },
    });
    return response.data;
  },
  createAdminTemplateResource: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_RESOURCES, data);
    return response.data;
  },
  updateAdminTemplateResource: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_RESOURCES, data);
    return response.data;
  },
  deleteAdminTemplateResource: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_RESOURCES, { data });
    return response.data;
  },

  listAdminTemplateSchedule: async ({ agent_id = null, bot_id = null, starts_at = null, ends_at = null, staff_id = null, resource_id = null, active_only = true } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SCHEDULE, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        starts_at: starts_at ?? undefined,
        ends_at: ends_at ?? undefined,
        staff_id: staff_id ?? undefined,
        resource_id: resource_id ?? undefined,
        active_only,
      },
    });
    return response.data;
  },
  listAdminTemplateAvailableSlots: async ({ agent_id = null, bot_id = null, starts_at, ends_at, staff_id = null, resource_id = null, service_id = null } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SCHEDULE_AVAILABLE, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        starts_at,
        ends_at,
        staff_id: staff_id ?? undefined,
        resource_id: resource_id ?? undefined,
        service_id: service_id ?? undefined,
      },
    });
    return response.data;
  },
  createAdminTemplateSchedule: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SCHEDULE, data);
    return response.data;
  },
  deleteAdminTemplateSchedule: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_SCHEDULE, { data });
    return response.data;
  },

  listAdminTemplateAppointments: async ({ agent_id = null, bot_id = null, starts_at = null, ends_at = null, staff_id = null, resource_id = null, service_id = null, status = null } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        starts_at: starts_at ?? undefined,
        ends_at: ends_at ?? undefined,
        staff_id: staff_id ?? undefined,
        resource_id: resource_id ?? undefined,
        service_id: service_id ?? undefined,
        status: status ?? undefined,
      },
    });
    return response.data;
  },
  createAdminTemplateAppointment: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS, data);
    return response.data;
  },
  rescheduleAdminTemplateAppointment: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_RESCHEDULE, data);
    return response.data;
  },
  cancelAdminTemplateAppointment: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_CANCEL, data);
    return response.data;
  },
  confirmAdminTemplateAppointment: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS_CONFIRM, data);
    return response.data;
  },
  deleteAdminTemplateAppointment: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_APPOINTMENTS, { data });
    return response.data;
  },
  getAdminTemplateOccupancy: async ({ agent_id = null, bot_id = null, starts_at, ends_at, staff_id = null, service_id = null, resource_id = null, granularity_minutes = 30 } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_OCCUPANCY, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        starts_at,
        ends_at,
        staff_id: staff_id ?? undefined,
        service_id: service_id ?? undefined,
        resource_id: resource_id ?? undefined,
        granularity_minutes,
      },
    });
    return response.data;
  },
  listAdminTemplateWaitlist: async ({ agent_id = null, bot_id = null, status_filter = null } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_WAITLIST, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        status_filter: status_filter ?? undefined,
      },
    });
    return response.data;
  },
  createAdminTemplateWaitlist: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_WAITLIST, data);
    return response.data;
  },
  updateAdminTemplateWaitlist: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_WAITLIST, data);
    return response.data;
  },
  deleteAdminTemplateWaitlist: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_WAITLIST, { data });
    return response.data;
  },
  listAdminTemplateClientProfiles: async ({ agent_id = null, bot_id = null, client_external_id = null } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_CLIENT_PROFILES, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        client_external_id: client_external_id ?? undefined,
      },
    });
    return response.data;
  },
  updateAdminTemplateClientProfile: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_CLIENT_PROFILES, data);
    return response.data;
  },
  listAdminTemplateQuickReplies: async ({ agent_id = null, bot_id = null, active_only = true } = {}) => {
    const response = await apiClient.get(API_ROUTES.AGENTS_ADMIN_TEMPLATE_QUICK_REPLIES, {
      params: {
        agent_id: agent_id ?? undefined,
        bot_id: bot_id ?? undefined,
        active_only,
      },
    });
    return response.data;
  },
  createAdminTemplateQuickReply: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_QUICK_REPLIES, data);
    return response.data;
  },
  updateAdminTemplateQuickReply: async (data) => {
    const response = await apiClient.patch(API_ROUTES.AGENTS_ADMIN_TEMPLATE_QUICK_REPLIES, data);
    return response.data;
  },
  deleteAdminTemplateQuickReply: async (data) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_ADMIN_TEMPLATE_QUICK_REPLIES, { data });
    return response.data;
  },
  runAdminTemplateReminders: async (data) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_ADMIN_TEMPLATE_REMINDERS_RUN, data);
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
