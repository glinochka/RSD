import apiClient from './apiClient';

export const pricingService = {
  getPlans: async () => {
    const response = await apiClient.get('/api/payments/plans');
    return response.data;
  },
};

export default pricingService;

