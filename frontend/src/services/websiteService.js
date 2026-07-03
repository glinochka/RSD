import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

export const websiteService = {
  list: async (params = {}) => {
    const response = await apiClient.get(API_ROUTES.WEBSITES_LIST, { params });
    return response.data;
  },

  create: async (payload) => {
    const response = await apiClient.post(API_ROUTES.WEBSITE_CREATE, payload);
    return response.data;
  },

  createAndGenerate: async (payload) => {
    const response = await apiClient.post(API_ROUTES.WEBSITE_GENERATE_CREATE, payload);
    return response.data;
  },

  getGenerationStatus: async (websiteId) => {
    const response = await apiClient.get(API_ROUTES.WEBSITE_GENERATION_STATUS(websiteId));
    return response.data;
  },

  getById: async (websiteId) => {
    const response = await apiClient.get(API_ROUTES.WEBSITE_DETAIL(websiteId));
    return response.data;
  },
};

export default websiteService;
