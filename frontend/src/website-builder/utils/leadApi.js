import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export async function submitWebsiteLead(agentId, payload) {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/agents/${agentId}/website/leads`,
    payload
  );
  return data;
}
