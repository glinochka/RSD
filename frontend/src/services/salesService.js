import axios from 'axios';
import { API_ROUTES } from '../config/constants';
import { ENV_CONFIG } from '../config/environment';

const salesClient = axios.create({
  baseURL: ENV_CONFIG.API.BASE_URL,
  timeout: ENV_CONFIG.API.TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

const salesService = {
  async login(login, password) {
    const response = await salesClient.post(API_ROUTES.SALES_LOGIN, { login, password });
    return response.data;
  },

  async getMe(token) {
    const response = await salesClient.get(API_ROUTES.SALES_ME, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async getContacts(token, { page = 1, pageSize = 20 } = {}) {
    const response = await salesClient.get(API_ROUTES.SALES_CONTACTS, {
      headers: { Authorization: `Bearer ${token}` },
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  async patchContact(token, contactId, body) {
    const response = await salesClient.patch(API_ROUTES.SALES_CONTACT(contactId), body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async downloadInvoice(token, contactId) {
    const response = await salesClient.get(API_ROUTES.SALES_CONTACT_INVOICE(contactId), {
      headers: { Authorization: `Bearer ${token}` },
      responseType: 'blob',
    });
    return response.data;
  },

  async mgmtGetTeam(token) {
    const response = await salesClient.get(API_ROUTES.SALES_MGMT_TEAM, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async mgmtCreateMember(token, body) {
    const response = await salesClient.post(API_ROUTES.SALES_MGMT_TEAM, body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async mgmtUpdateMember(token, memberId, body) {
    const response = await salesClient.patch(API_ROUTES.SALES_MGMT_TEAM_MEMBER(memberId), body, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async mgmtGetFunnel(token) {
    const response = await salesClient.get(API_ROUTES.SALES_MGMT_FUNNEL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  },

  async mgmtUploadExcel(token, file, assigneeId) {
    const form = new FormData();
    form.append('assignee_id', String(assigneeId));
    form.append('file', file);
    const response = await salesClient.post(API_ROUTES.SALES_MGMT_EXCEL_UPLOAD, form, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export default salesService;
