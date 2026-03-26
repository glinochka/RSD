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
};

export default adminService;
