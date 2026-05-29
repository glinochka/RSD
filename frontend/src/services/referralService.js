import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

const referralService = {
  async getPartnerDashboard() {
    const response = await apiClient.get(API_ROUTES.REFERRALS_PARTNER_DASHBOARD);
    return response.data;
  },

  async createPartnerPromoCode({ code, discountPercent }) {
    const response = await apiClient.post(API_ROUTES.REFERRALS_PARTNER_PROMO_CODES, {
      code,
      discount_percent: discountPercent,
    });
    return response.data;
  },

  async patchPartnerPromoCode(promoCodeId, payload) {
    const response = await apiClient.patch(
      API_ROUTES.REFERRALS_PARTNER_PROMO_CODE(promoCodeId),
      payload,
    );
    return response.data;
  },

  async deletePartnerPromoCode(promoCodeId) {
    const response = await apiClient.delete(
      API_ROUTES.REFERRALS_PARTNER_PROMO_CODE(promoCodeId),
    );
    return response.data;
  },

  async getPayoutBalance() {
    const response = await apiClient.get(API_ROUTES.REFERRALS_PARTNER_PAYOUT_BALANCE);
    return response.data;
  },

  async getPayouts() {
    const response = await apiClient.get(API_ROUTES.REFERRALS_PARTNER_PAYOUTS);
    return response.data;
  },

  async createPayout({ amountRub, paymentDetails }) {
    const response = await apiClient.post(API_ROUTES.REFERRALS_PARTNER_PAYOUTS, {
      amount_rub: amountRub,
      payment_details: paymentDetails,
    });
    return response.data;
  },
};

export default referralService;
