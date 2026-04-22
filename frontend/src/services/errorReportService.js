import apiClient from './apiClient';
import { API_ROUTES } from '../config/constants';

const errorReportService = {
  async submit(description) {
    await apiClient.post(API_ROUTES.USER_ERROR_REPORTS, { description });
  },
};

export default errorReportService;
