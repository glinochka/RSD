import axios from 'axios';
import { API_ROUTES } from '../config/constants';
import { ENV_CONFIG } from '../config/environment';

const adminClient = axios.create({
  baseURL: ENV_CONFIG.API.BASE_URL,
  timeout: ENV_CONFIG.API.TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

const adminService = {
  async login(login, password) {
    const response = await adminClient.post(API_ROUTES.ADMIN_LOGIN, { login, password });
    return response.data;
  },

  async getStats(token) {
    const response = await adminClient.get(API_ROUTES.ADMIN_STATS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  },

  async getUsers(token, { page = 1, pageSize = 10, search = '' } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_USERS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
      },
    });
    return response.data;
  },

  async getAgents(token, { page = 1, pageSize = 10, search = '' } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_AGENTS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
      },
    });
    return response.data;
  },

  async getChats(
    token,
    {
      page = 1,
      pageSize = 25,
      search = '',
      messagesPerChat = 50,
      agentId = null,
      agentUsername = '',
    } = {}
  ) {
    const response = await adminClient.get(API_ROUTES.ADMIN_CHATS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
        messages_per_chat: messagesPerChat,
        agent_id: agentId || undefined,
        agent_username: agentUsername || undefined,
      },
    });
    return response.data;
  },

  async getTurnkeyRequests(token, { page = 1, pageSize = 10, search = '' } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_TURNKEY_REQUESTS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
      },
    });
    return response.data;
  },

  async getErrorReports(token, { page = 1, pageSize = 10, search = '' } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_ERROR_REPORTS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
      },
    });
    return response.data;
  },

  async getPlans(token) {
    const response = await adminClient.get(API_ROUTES.ADMIN_PLANS, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  },

  async updatePlans(token, plans) {
    const response = await adminClient.put(
      API_ROUTES.ADMIN_PLANS,
      { plans },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );
    return response.data;
  },

  async getPromoCodes(token) {
    const response = await adminClient.get(API_ROUTES.ADMIN_PROMO_CODES, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    return response.data;
  },

  async createPromoCode(token, { code, discount_percent }) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_PROMO_CODES,
      { code, discount_percent },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );
    return response.data;
  },

  async deletePromoCode(token, promoCodeId) {
    const response = await adminClient.delete(
      API_ROUTES.ADMIN_DELETE_PROMO_CODE(promoCodeId),
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );
    return response.data;
  },

  async banUser(token, userId) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_BAN_USER(userId),
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async unbanUser(token, userId) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_UNBAN_USER(userId),
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async giftSubscription(token, userId, planCode) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_GIFT_SUBSCRIPTION(userId),
      { plan_code: planCode },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async sendEmailBroadcast(token, { subject, body, interval_seconds }) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_EMAIL_BROADCAST,
      { subject, body, interval_seconds },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async previewEmailTargeted(token, { groups, selected_titles }) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_EMAIL_TARGETED_PREVIEW,
      { groups, selected_titles },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async sendEmailTargetedBroadcast(token, { groups, selected_titles, subject, body, interval_seconds }) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_EMAIL_TARGETED_BROADCAST,
      { groups, selected_titles, subject, body, interval_seconds },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async getEmailTargetedBroadcastJob(token, jobId) {
    const response = await adminClient.get(API_ROUTES.ADMIN_EMAIL_TARGETED_JOB(jobId), {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  // --- Article Publisher ---

  async apGetSettings(token) {
    const response = await adminClient.get(API_ROUTES.ADMIN_AP_SETTINGS, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async apUpdateSettings(token, settings) {
    const response = await adminClient.put(API_ROUTES.ADMIN_AP_SETTINGS, settings, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async apGetTopics(token, { page = 1, pageSize = 50, unusedOnly = false } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_AP_TOPICS, {
      headers: { Authorization: `Bearer ${token}` },
      params: { page, page_size: pageSize, unused_only: unusedOnly },
    });
    return response.data;
  },

  async apAddTopics(token, topics) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_AP_TOPICS,
      { topics },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async apGenerateTopics(token, { categories, count = 10 } = {}) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_AP_TOPICS_GENERATE,
      { categories, count },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async apDeleteTopic(token, topicId) {
    const response = await adminClient.delete(API_ROUTES.ADMIN_AP_TOPIC_DELETE(topicId), {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async apGetImages(token) {
    const response = await adminClient.get(API_ROUTES.ADMIN_AP_IMAGES, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async apUploadImage(token, file) {
    const form = new FormData();
    form.append('file', file);
    const response = await adminClient.post(API_ROUTES.ADMIN_AP_IMAGES, form, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async apDeleteImage(token, imageId) {
    const response = await adminClient.delete(API_ROUTES.ADMIN_AP_IMAGE_DELETE(imageId), {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async apGetJobs(token, { page = 1, pageSize = 20 } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_AP_JOBS, {
      headers: { Authorization: `Bearer ${token}` },
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  async apRunNow(token, { platform, topic } = {}) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_AP_RUN_NOW,
      { platform: platform || null, topic: topic || null },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async apPreviewArticle(token, { topic, platform = 'vcru' }) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_AP_PREVIEW,
      { topic, platform },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async salesGetTeam(token, { includeInactive = false } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_SALES_TEAM, {
      headers: { Authorization: `Bearer ${token}` },
      params: { include_inactive: includeInactive || undefined },
    });
    return response.data;
  },

  async salesCreateMember(token, body) {
    const response = await adminClient.post(API_ROUTES.ADMIN_SALES_TEAM, body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async salesUpdateMember(token, memberId, body) {
    const response = await adminClient.patch(API_ROUTES.ADMIN_SALES_TEAM_MEMBER(memberId), body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async salesGetFunnel(token, { period = 'all' } = {}) {
    const response = await adminClient.get(API_ROUTES.ADMIN_SALES_FUNNEL, {
      headers: { Authorization: `Bearer ${token}` },
      params: { period },
    });
    return response.data;
  },

  async salesUploadExcel(token, file) {
    const form = new FormData();
    form.append('file', file);
    const response = await adminClient.post(API_ROUTES.ADMIN_SALES_EXCEL_UPLOAD, form, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async salesAddContactManual(token, body) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_SALES_CONTACT_MANUAL,
      body,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async salesClearCrm(token) {
    const response = await adminClient.post(
      API_ROUTES.ADMIN_SALES_CRM_CLEAR,
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },
};

export default adminService;
