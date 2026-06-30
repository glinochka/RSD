/**
 * Project Service
 * Handles API calls for project management
 */

import { API_ROUTES } from '../config/constants';

/**
 * Get authentication headers
 */
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
};

/**
 * Handle API response
 */
const handleResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
};

const projectService = {
  /**
   * List all projects for current user
   */
  async listProjects() {
    const response = await fetch(API_ROUTES.PROJECTS_LIST, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project by ID
   */
  async getProject(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_DETAIL(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Create a new project
   */
  async createProject(data) {
    const response = await fetch(API_ROUTES.PROJECT_CREATE, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  /**
   * Update project
   */
  async updateProject(projectId, data) {
    const response = await fetch(API_ROUTES.PROJECT_UPDATE(projectId), {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  /**
   * Archive project
   */
  async archiveProject(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_ARCHIVE(projectId), {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return true;
  },

  /**
   * Get project dashboard data
   */
  async getProjectDashboard(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_DASHBOARD(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Generate AI plan for project
   */
  async generatePlan(brief) {
    const response = await fetch(API_ROUTES.PROJECT_AI_GENERATE_PLAN, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(brief),
    });
    return handleResponse(response);
  },

  /**
   * Apply AI plan and create project with agents
   */
  async applyPlan(brief, plan, idempotencyKey = null) {
    const payload = {
      brief,
      plan,
      idempotency_key: idempotencyKey,
    };
    const response = await fetch(API_ROUTES.PROJECT_AI_APPLY_PLAN, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  /**
   * Get project documents
   */
  async getProjectDocuments(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_DOCUMENTS(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Upload document to project
   */
  async uploadProjectDocument(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('token');
    const response = await fetch(API_ROUTES.PROJECT_DOCUMENTS(projectId), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
    return handleResponse(response);
  },

  /**
   * Upload public link to project
   */
  async uploadProjectLink(projectId, url) {
    const response = await fetch(API_ROUTES.PROJECT_DOCUMENTS_LINK(projectId), {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ url }),
    });
    return handleResponse(response);
  },

  /**
   * Delete project document
   */
  async deleteProjectDocument(projectId, documentId) {
    const response = await fetch(API_ROUTES.PROJECT_DOCUMENT(projectId, documentId), {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Reindex project document
   */
  async reindexProjectDocument(projectId, documentId) {
    const response = await fetch(API_ROUTES.PROJECT_DOCUMENT_REINDEX(projectId, documentId), {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project agents (for linking website, etc.)
   */
  async getProjectAgents(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_AGENTS(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project website info
   */
  async getProjectWebsite(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_WEBSITE(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project CRM data
   */
  async getProjectCRM(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_CRM(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project content agents and jobs
   */
  async getProjectContentAgents(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_CONTENT_DATA(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get project AI Manager data
   */
  async getProjectAiManager(projectId) {
    const response = await fetch(API_ROUTES.PROJECT_AI_MANAGER(projectId), {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },

  /**
   * Get settings (for feature flags)
   */
  async getSettings() {
    const response = await fetch('/api/settings', {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    return handleResponse(response);
  },
};

export default projectService;
