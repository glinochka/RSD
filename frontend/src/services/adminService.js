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
};

export default adminService;
