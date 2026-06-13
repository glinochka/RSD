import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export async function fetchBookingSlots(agentId, serviceId, date) {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/agents/${agentId}/booking/slots`,
    { params: { service_id: serviceId, date } }
  );
  return data.items || [];
}

export async function createBooking(agentId, payload) {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/agents/${agentId}/booking/appointments`,
    payload
  );
  return data;
}
