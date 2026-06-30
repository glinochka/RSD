/**
 * Agents Redirect Page
 * Redirects /agents to /projects/:lastProjectId/agents or /projects
 */

import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../config/constants';

const AgentsRedirect = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const lastProjectId = localStorage.getItem('rsd_last_project_id');
    if (lastProjectId) {
      navigate(NAVIGATION_ROUTES.PROJECT_AGENTS(lastProjectId), { replace: true });
    } else {
      navigate(NAVIGATION_ROUTES.PROJECTS_LIST, { replace: true });
    }
  }, [navigate]);

  return (
    <div className="agents-redirect">
      <div className="agents-redirect-loading">
        <div className="spinner" />
        <p>Перенаправление...</p>
      </div>
    </div>
  );
};

export default AgentsRedirect;
