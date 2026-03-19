/**
 * Agents Service
 * Handles all agent-related API calls
 */

import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

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
    const response = await apiClient.get(API_ROUTES.AGENTS_DETAIL(id));
    return response.data;
  },

  /**
   * Create new agent
   */
  create: async (agentData) => {
    const response = await apiClient.post(API_ROUTES.AGENTS_CREATE, agentData);
    return response.data;
  },

  /**
   * Update agent
   */
  update: async (id, agentData) => {
    const response = await apiClient.put(
      API_ROUTES.AGENTS_UPDATE(id),
      agentData
    );
    return response.data;
  },

  /**
   * Delete agent
   */
  delete: async (id) => {
    const response = await apiClient.delete(API_ROUTES.AGENTS_DELETE(id));
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
};

export default agentService;
