/**
 * AgentWidget — embeds RSD chat widget (reuses external widget.js).
 */
import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { injectAgentWidgetScript } from '../utils/widget';

const AgentWidget = ({
  apiKey,
  apiBase,
  position = 'bottom-right',
  title,
  greeting,
  theme = 'dark',
  enabled = true,
}) => {
  useEffect(() => {
    if (!enabled || !apiKey) return undefined;
    return injectAgentWidgetScript({
      apiKey,
      apiBase,
      position,
      title: title || 'Онлайн-консультант',
      greeting: greeting || 'Здравствуйте! Чем могу помочь?',
      theme,
    });
  }, [apiKey, apiBase, position, title, greeting, theme, enabled]);

  return null;
};

AgentWidget.propTypes = {
  apiKey: PropTypes.string,
  apiBase: PropTypes.string,
  position: PropTypes.string,
  title: PropTypes.string,
  greeting: PropTypes.string,
  theme: PropTypes.oneOf(['dark', 'light']),
  enabled: PropTypes.bool,
};

export default AgentWidget;
