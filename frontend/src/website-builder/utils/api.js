import axios from 'axios';
import { API_ROUTES } from '../../config/constants';
import { getAuthHeaders } from '../../utils/authToken';
import { toApiStyles } from './styleUtils';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

function authHeaders() {
  return getAuthHeaders();
}

export async function fetchWebsiteDetail(websiteId) {
  const { data } = await axios.get(`${API_BASE_URL}${API_ROUTES.WEBSITE_DETAIL(websiteId)}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function updateWebsite(websiteId, payload) {
  const body = { ...payload };
  if (body.custom_styles) {
    body.custom_styles = toApiStyles(body.custom_styles);
  }
  const { data } = await axios.put(`${API_BASE_URL}${API_ROUTES.WEBSITE_UPDATE(websiteId)}`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function updateBlock(websiteId, blockId, payload) {
  const { data } = await axios.put(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK(websiteId, blockId)}`,
    payload,
    { headers: authHeaders() }
  );
  return data;
}

export async function createBlock(websiteId, payload) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCKS(websiteId)}`,
    payload,
    { headers: authHeaders() }
  );
  return data;
}

export async function deleteBlock(websiteId, blockId) {
  await axios.delete(`${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK(websiteId, blockId)}`, {
    headers: authHeaders(),
  });
}

export async function duplicateBlockApi(websiteId, blockId) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK_DUPLICATE(websiteId, blockId)}`,
    {},
    { headers: authHeaders() }
  );
  return data;
}

export async function reorderBlocksApi(websiteId, blocks) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCKS_REORDER(websiteId)}`,
    { blocks },
    { headers: authHeaders() }
  );
  return data;
}

export async function editBlockWithPromptApi(websiteId, blockId, prompt, images = []) {
  // If images provided, use FormData for multipart upload
  if (images && images.length > 0) {
    const formData = new FormData();
    formData.append('prompt', prompt);
    images.forEach((img, idx) => {
      formData.append(`image_${idx}`, img.file);
    });
    formData.append('image_count', images.length.toString());

    const { data } = await axios.post(
      `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK_EDIT_PROMPT(websiteId, blockId)}`,
      formData,
      {
        headers: {
          ...authHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return waitForEditTask(websiteId, data.task_id);
  }

  // Simple prompt without images
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK_EDIT_PROMPT(websiteId, blockId)}`,
    { prompt },
    { headers: authHeaders() }
  );
  return waitForEditTask(websiteId, data.task_id);
}

async function waitForEditTask(websiteId, taskId, timeoutMs = 180000) {
  const startedAt = Date.now();
  const pollIntervalMs = 1500;

  while (Date.now() - startedAt < timeoutMs) {
    const { data } = await axios.get(
      `${API_BASE_URL}${API_ROUTES.WEBSITE_BLOCK_EDIT_PROMPT_TASK(websiteId, taskId)}`,
      { headers: authHeaders() }
    );

    if (data.status === 'completed') {
      return {
        content: data.content || {},
        styles: data.styles || {},
        message: data.message || 'Изменения применены',
        improved_prompt: data.improved_prompt || null,
      };
    }

    if (data.status === 'failed') {
      throw new Error(data.error || data.message || 'AI edit failed');
    }

    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }

  throw new Error('Превышено время ожидания результата редактирования');
}

export async function publishWebsite(websiteId) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_PUBLISH(websiteId)}`,
    {},
    { headers: authHeaders() }
  );
  return data;
}

export async function unpublishWebsite(websiteId) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_UNPUBLISH(websiteId)}`,
    {},
    { headers: authHeaders() }
  );
  return data;
}

export async function deleteWebsite(websiteId) {
  await axios.delete(`${API_BASE_URL}${API_ROUTES.WEBSITE_DELETE(websiteId)}`, {
    headers: authHeaders(),
  });
}

// Domain management
export async function fetchDomains(websiteId) {
  const { data } = await axios.get(`${API_BASE_URL}${API_ROUTES.WEBSITE_DOMAINS(websiteId)}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function addDomain(websiteId, domain) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_DOMAINS(websiteId)}`,
    { domain },
    { headers: authHeaders() }
  );
  return data;
}

export async function verifyDomain(websiteId, domainId) {
  const { data } = await axios.post(
    `${API_BASE_URL}${API_ROUTES.WEBSITE_DOMAIN_VERIFY(websiteId, domainId)}`,
    {},
    { headers: authHeaders() }
  );
  return data;
}

export async function removeDomain(websiteId, domainId) {
  await axios.delete(`${API_BASE_URL}${API_ROUTES.WEBSITE_DOMAIN(websiteId, domainId)}`, {
    headers: authHeaders(),
  });
}

// SEO / Meta Data
export async function fetchSEOMeta(websiteId) {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/seo/meta`,
    { headers: authHeaders() }
  );
  return data;
}

export async function updateSEOMeta(websiteId, payload) {
  const { data } = await axios.put(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/meta`,
    payload,
    { headers: authHeaders() }
  );
  return data;
}

export async function fetchSEOPreview(websiteId) {
  const { data } = await axios.get(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/seo/preview`,
    { headers: authHeaders() }
  );
  return data;
}

export async function uploadFavicon(websiteId, file) {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/favicon`,
    formData,
    {
      headers: {
        ...authHeaders(),
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return data;
}

export async function uploadOGImage(websiteId, file) {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/og-image/upload`,
    formData,
    {
      headers: {
        ...authHeaders(),
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return data;
}

export async function generateOGImage(websiteId, payload) {
  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/websites/${websiteId}/og-image/generate`,
    payload,
    { headers: authHeaders() }
  );
  return data;
}
