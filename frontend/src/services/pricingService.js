import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

export const pricingService = {
  getAgentTemplates: async () => {
    const response = await apiClient.get('/api/payments/agent-templates');
    return response.data;
  },
  getPlans: async () => {
    const response = await apiClient.get('/api/payments/plans');
    return response.data;
  },
  createAgentBillingPayment: async ({
    agent_id,
    payment_kind,
    return_url,
    promo_code,
    duration_months,
    enable_autopay,
  }) => {
    const response = await apiClient.post('/api/payments/yookassa/agent-billing/create', {
      agent_id,
      payment_kind,
      return_url,
      promo_code: promo_code || undefined,
      duration_months: duration_months || 1,
      enable_autopay: Boolean(enable_autopay),
    });
    return response.data;
  },
  createYooKassaPayment: async ({ plan_name, return_url, promo_code, duration_months }) => {
    const response = await apiClient.post('/api/payments/yookassa/create', {
      plan_name,
      return_url,
      promo_code: promo_code || undefined,
      duration_months: duration_months || 1,
    });
    return response.data;
  },
  getPaymentMethods: async () => {
    const response = await apiClient.get('/api/payments/payment-methods');
    return response.data;
  },
  deletePaymentMethod: async (methodId) => {
    const response = await apiClient.delete(`/api/payments/payment-methods/${methodId}`);
    return response.data;
  },
  getYooKassaPaymentStatus: async (paymentId) => {
    const response = await apiClient.get('/api/payments/yookassa/status', {
      params: { payment_id: paymentId },
    });
    return response.data;
  },
  createTurnkeyRequest: async ({ phone_number, email, requested_agent, purpose }) => {
    const response = await apiClient.post(API_ROUTES.TURNKEY_REQUESTS, {
      phone_number,
      email,
      requested_agent,
      purpose,
    });
    return response.data;
  },
};

export default pricingService;

