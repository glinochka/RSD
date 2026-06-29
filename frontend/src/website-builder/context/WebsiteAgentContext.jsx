import React, { createContext, useContext, useMemo } from 'react';
import PropTypes from 'prop-types';

const WebsiteAgentContext = createContext(null);

export function WebsiteAgentProvider({ agent, agentId, children }) {
  const value = useMemo(
    () => ({
      agent,
      agentId: agent?.id ?? agentId ?? null,
      isAdminTemplate: Boolean(agent?.is_admin_template),
      hasBooking: Boolean(agent?.has_booking),
      hasApplications: agent?.has_applications ?? Boolean(agent?.is_admin_template),
      services: agent?.services || [],
      contacts: agent?.contacts || {},
      widgetApiKey: agent?.widget_api_key || null,
    }),
    [agent, agentId]
  );

  return (
    <WebsiteAgentContext.Provider value={value}>{children}</WebsiteAgentContext.Provider>
  );
}

WebsiteAgentProvider.propTypes = {
  agent: PropTypes.object,
  agentId: PropTypes.number,
  children: PropTypes.node.isRequired,
};

export function useWebsiteAgent() {
  return useContext(WebsiteAgentContext);
}

export default WebsiteAgentContext;
