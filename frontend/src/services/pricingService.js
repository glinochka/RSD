import apiClient from './apiClient';

export const pricingService = {
  getPlans: async () => {
    const response = await apiClient.get('/api/payments/plans');
    return response.data;
  },
  createYooKassaPayment: async ({ plan_name, return_url }) => {
    const response = await apiClient.post('/api/payments/yookassa/create', {
      plan_name,
      return_url,
    });
    return response.data;
  },
  getYooKassaPaymentStatus: async (paymentId) => {
    const response = await apiClient.get('/api/payments/yookassa/status', {
      params: { payment_id: paymentId },
    });
    return response.data;
  },
};

export default pricingService;

